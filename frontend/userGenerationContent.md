
# User Generated Content — 评分与评论（设计与实现）

本文档基于当前代码库对「用户产生内容（UGC）」——主要是商品评分（rating）与商品评论（comments / replies / likes）——的设计与实现做系统性说明。忽略已废弃的旧逻辑（旧表 `reviews` 及其相关关系/方法），仅覆盖当前在用的数据结构、后端路由与前端展示/交互实现。

## 概览

- 主要功能点：
  - 评分：用户对已购买并完成的订单（`status == "completed"`）中包含的商品，按订单消耗评分配额（每个订单对同一商品允许评分一次）。
  - 评论：仅允许已完成购买该商品的用户发表评论／回复（回复仅支持顶层评论的一级回复）。
  - 点赞：用户可以对评论（顶层或回复）点赞；目前仅支持点赞，不支持取消点赞。
  - 聚合视图：商品详情页聚合并展示评分统计（平均分、评分数）与评论树（root + replies），并提供按「点赞数」或「时间」排序。

核心文件：

- 后端路由与逻辑： `backend/app/routers/reviews.py`
- 后端模型： `backend/app/models.py`
- 数据库初始化（保证 review 相关表存在）： `backend/app/db.py`
- 请求/响应 schema： `backend/app/schemas.py`
- 前端展示与交互： `frontend/src/views/ProductDetail.vue`
- 前端 API 封装（鉴权处理）： `frontend/src/api/http.ts`

每个文件引用均为可点击路径（见上）。

---

## 数据模型（当前有效）

后端通过 SQLAlchemy（见 `backend/app/models.py`）定义了三个主要表：

- `product_ratings`（模型：`ProductRating`）
  - 字段：`id, user_id, product_id, order_id, rating, created_at`
  - 说明：记录每次按订单产生的商品评分；`order_id` 用来保证同一订单对同一商品只评分一次（即计入评分配额）。

- `product_comments`（模型：`ProductComment`）
  - 字段：`id, user_id, product_id, parent_id, content, created_at, updated_at`
  - 说明：支持树形（但代码只允许一级回复）：`parent_id` 为 `NULL` 表示根评论；回复的 `parent_id` 指向根评论的 `id`。

- `product_comment_likes`（模型：`ProductCommentLike`）
  - 字段：`id, user_id, comment_id, created_at`
  - 说明：记录用户对某条评论的点赞。当前实现没有数据库层唯一约束来强制 `user_id+comment_id` 唯一，而是在路由层做存在性检查以避免重复点赞。

这些表如果不存在，会由 `backend/app/db.py::_ensure_product_review_tables` 在应用启动/初始化时创建（轻量的 SQLite 自迁移逻辑）。

注意：项目中仍存在旧的 `Review` 表（`backend/app/models.py` 中的 `Review` 模型），该表与旧逻辑相关。本说明故意忽略 `reviews` 及其相关旧逻辑。

---

## 后端实现要点（行为与路由）

主要路由归档在 `backend/app/routers/reviews.py`：

- `GET /api/products/{product_id}/reviews` — 列表视图
  - 返回：`ProductReviewPageOut`（包含 `summary`, `ratings[]`, `comments[]`）。
  - 功能：计算平均分、评分数、评论数、当前用户的评分配额与可用订单 id（供评分下拉使用）、并序列化评论树（根 + 回复），同时为每条评论附带 `like_count` 与 `liked_by_me`。
  - 当前用户可选（匿名访问仍可查看，但 `liked_by_me` 只在登录时才会被标记）。

- `POST /api/products/{product_id}/ratings` — 提交评分
  - 输入：`{ order_id: str, rating: int }`（`1`–`5`）
  - 权限：必须登录（`Depends(get_current_user)`）
  - 校验逻辑：
    1. 通过 `_eligible_order_ids` 查询用户已完成并包含该商品的订单 id 列表（`status == 'completed'` 且 `OrderItem.sku_id` 对应的 `ProductSKU.product_id == product_id`）。
    2. 通过 `_rating_quota` 计算尚未用于评分的订单 id（eligible - 已评分 order_id）。
    3. 检查 `payload.order_id` 是否在可用订单里；若不在则拒绝。
    4. 插入 `ProductRating` 记录（order_id 用于防止重复评分）。

- `POST /api/products/{product_id}/comments` — 新增评论（顶层）
  - 输入：`{ content: string }`
  - 权限：必须登录，且必须为购买过该商品的用户（`_can_comment` 基于 `_eligible_order_ids` 判定）。

- `POST /api/products/{product_id}/comments/{comment_id}/replies` — 对顶层评论回复（仅允许回复顶层）
  - 权限：同上（必须为购买过该商品的用户）。
  - 校验：只允许回复 parent 的顶层评论（`parent.parent_id is None`），不支持多级嵌套。

- `POST /api/products/{product_id}/comments/{comment_id}/like` — 点赞
  - 权限：必须登录。
  - 实现：先查询当前用户是否已点赞；若存在则返回 400；否则插入 `ProductCommentLike` 并提交。

实现细节：

- 评论序列化（`_serialize_comments`）采用三步查询：
  1. 查询根评论（`parent_id IS NULL`）并按排序分组；
  2. 查询这些根评论的所有回复（按时间正序）；
  3. 聚合 `product_comment_likes` 得到每个评论的 `like_count`，并根据当前用户计算 `liked_by_me`。这样可以避免 N+1，但仍会对大评论量产生压力。

- 排序选项：`sort=likes|time`。
  - `time`：按 `created_at DESC, id DESC`。
  - `likes`：按 `like_count DESC, created_at DESC`（通过 `GROUP BY` + `COUNT` 实现）。

---

## 前端实现（用户交互）

核心页面为 `frontend/src/views/ProductDetail.vue`：

- 展示：
  - 顶部显示平均评分与评分人数（`reviewSummary.average_rating`, `reviewSummary.rating_count`），使用 `el-rate` 渲染星级。
  - 显示评分与评论汇总卡片（平均分、评论数、当前用户评分配额）。
  - 评分表单：用户必须选择一个可用的 `order_id`（下拉由 `reviewSummary.available_rating_orders` 填充）并选择星级后提交。
  - 评论表单：textarea 提交评论。
  - 评论列表：渲染 `comments` 数组，每个评论显示作者、时间、内容、点赞数与回复功能；回复仅支持一级。

- 前端 API 流程（关键函数）：
  - `loadReviews()` 调用 `GET /api/products/{id}/reviews?sort=<likes|time>` 并刷新 `reviewSummary`, `ratings`, `comments`。
  - `submitRating()` 调用 `POST /api/products/{id}/ratings`，参数为 `{ order_id, rating }`，提交成功后刷新列表。
  - `submitComment()` 调用 `POST /api/products/{id}/comments`，提交成功后刷新列表。
  - `submitReply(commentId)` 调用 `POST /api/products/{id}/comments/{commentId}/replies`，提交成功后刷新。
  - `likeComment(commentId)` 调用 `POST /api/products/{id}/comments/{commentId}/like` 并刷新。

前端重要参考：`frontend/src/views/ProductDetail.vue` 与通用 HTTP 封装 `frontend/src/api/http.ts`（处理 JWT、401/403 跳转）。

---

## 业务规则（逐条说明）

1. 评分资格与配额
   - 只有对该商品有已完成订单（`status == 'completed'`）的用户才有资格评分。
   - 每个完成订单对同一商品仅能用于评分一次：当用户用某个 `order_id` 提交评分后，该 `order_id` 就被视作已使用，`_rating_quota` 会从可用列表中移除。
   - 评分值强制在 1~5 范围内。

2. 评论资格
   - 只有曾购买并完成该商品的用户（至少存在一个 eligible order）才允许发表评论或回复。
   - 评论没有绑定到 `order_id`（与评分不同），也就是说有资格的用户可以发表多条评论（业务上可以根据需要做额外限制）。

3. 回复规则
   - 仅支持给顶层评论做一级回复（路由中会检查父评论的 `parent_id is None`）。
   - 不支持无限级嵌套以避免复杂 UI 与滥用。

4. 点赞规则
   - 点赞前后端都会检查是否已点赞，后端会阻止重复点赞并返回 400 错误。
   - 当前没有实现取消点赞（unlike）接口；若需要，建议实现 `DELETE` 或 `POST /unlike`。

5. 评论排序
   - 支持按 `likes`（点赞数降序）或 `time`（时间降序）排序，客户端通过 `sort` 参数控制。

---

## API 合约（简要示例）

GET /api/products/{product_id}/reviews  -> 200 OK

```json
{
  "summary": {
    "average_rating": 4.5,
    "rating_count": 12,
    "comment_count": 5,
    "my_rating_quota": 1,
    "can_comment": true,
    "available_rating_orders": ["202604120001"]
  },
  "ratings": [ { "id": 1, "user_id": 2, "product_id": 10, "order_id": "202604120001", "rating": 5, "created_at": "..." } ],
  "comments": [
    {
      "id": 11,
      "user_id": 3,
      "user_name": "Alice",
      "product_id": 10,
      "parent_id": null,
      "content": "很棒的一本书",
      "created_at":"...",
      "updated_at":"...",
      "like_count": 2,
      "liked_by_me": false,
      "replies": [ { "id": 12, "user_id": 4, "user_name":"Bob", "content":"同感" , "like_count":0 } ]
    }
  ]
}
```

POST /api/products/{product_id}/ratings

```json
// body
{ "order_id": "202604120001", "rating": 5 }

// success -> returns created rating record
```

POST /api/products/{product_id}/comments

```json
// body
{ "content": "这是我的评论" }

// success -> created comment object
```

POST /api/products/{product_id}/comments/{comment_id}/like

```json
// no body; returns { message: "点赞成功" }
```

（具体返回的字段请参考 `backend/app/schemas.py` 中的 Pydantic 模型。）

---

## 安全、验证与依赖

- 鉴权：写操作（评分/评论/回复/点赞）均依赖 `get_current_user`，即必须携带有效 JWT。查看实现： `backend/app/deps.py`。
- 读接口：`GET /reviews` 支持可选鉴权（`get_current_user_optional`），以便标记 `liked_by_me`。
- 输入验证：Pydantic 在 `backend/app/schemas.py` 中定义请求格式（如 `RatingCreate`, `CommentCreate`），后端在路由中做额外业务校验（配额、订单归属、parent_id 校验等）。

---

## 已知限制与改进建议

1. 并发与重复点赞：路由层通过查询判断并阻止重复点赞，但在高并发下仍存在竞态。建议在数据库层添加唯一约束：

   - 在 `product_comment_likes` 上加唯一索引 `(user_id, comment_id)`，并在插入时处理 `IntegrityError`，以获得事务级保证。

2. 评论/点赞的性能：当前 `_serialize_comments` 会在短时间内运行多次查询（roots → replies → like aggregate → liked_by_me）。对于高流量或评论量大的产品，建议：

   - 在 `product` 表或单独统计表中缓存 `comment_count`、`like_count` 汇总值，并通过触发器或异步任务更新；
   - 为 `product_comments.product_id`、`product_comment_likes.comment_id` 创建索引；
   - 在需要时引入分页（根评论分页）以避免一次性加载全部评论。

3. 评论滥用与审核：目前无自动审核或人工举报机制。建议增加：

   - 评论机审（敏感词、垃圾检测）与人工审核流程；
   - 举报接口、管理员删除/屏蔽接口；
   - 评论审计日志（谁在何时做了哪些操作）。

4. UX 改进：

   - 支持取消点赞（UNLIKE）；
   - 可选地将评分与评论绑定到 `order_id`（用于证明和售后）；当前评论没有 order_id，若需强证据可扩展。

---

## 本地测试与调试

1. 启动后端并确保 DB 已初始化（`backend/app/db.py::init_db` 创建 `product_ratings` / `product_comments` / `product_comment_likes`）。
2. 使用示例用户下完成订单（或使用 `backend/app/seed.py` 的 demo 函数），获取可用于评分的 `order_id`。
3. 前端在 `ProductDetail.vue` 页面会自动加载 `/api/products/{id}/reviews` 并展示评分/评论；可通过浏览器开发者工具或 curl 调用 API 验证行为。

示例 curl：

```bash
# 查看评论与评分
curl "http://localhost:8001/api/products/10/reviews"

# 提交评分（需 Authorization: Bearer <JWT>）
curl -X POST -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"order_id":"202604120001","rating":5}' \
  http://localhost:8001/api/products/10/ratings

# 提交评论
curl -X POST -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"content":"很好！"}' \
  http://localhost:8001/api/products/10/comments
```

---

## 参考代码位置

- 后端模型与表初始化： `backend/app/models.py`  、 `backend/app/db.py`
- 后端路由与实现： `backend/app/routers/reviews.py`
- 请求与响应 schema： `backend/app/schemas.py`
- 前端主要实现： `frontend/src/views/ProductDetail.vue`
- 前端 API 封装（鉴权与错误处理）： `frontend/src/api/http.ts`

---

以上为当前项目中用户产生内容（评分与评论）功能的设计与实现要点、业务规则与改进建议。已明确忽略旧的 `reviews` 表及其相关旧逻辑；若需要保留历史数据或做迁移，请单独规划迁移脚本与兼容层。
