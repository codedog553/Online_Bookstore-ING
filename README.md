# 在线书店系统（本地运行版）

本项目为课程作业性质：**不需要部署，仅本地运行；不考虑性能，只实现业务功能与可追踪的需求实现。**

- 后端：FastAPI + SQLAlchemy + SQLite（`backend/app.db`）
- 前端：Vue 3 + Vite + Element Plus + Pinia + vue-i18n

> 说明：你可以在代码中通过全局搜索 `A1` / `B2` / `D5` / `W2` 等标记，快速定位对应需求的关键实现点。

---

## 1. 目录结构

```text
F:\ISPproject
├─ backend\                 # FastAPI 后端
│  ├─ app\
│  │  ├─ routers\          # 业务 API（auth/products/cart/orders/admin/...）
│  │  ├─ models.py          # ORM 模型（User/Product/SKU/Order/...）
│  │  ├─ schemas.py         # Pydantic schema（请求/响应）
│  │  ├─ uploads\          # 本地上传图片存储（按 sku_{id} 目录）
│  │  └─ main.py            # 应用入口（含 /uploads 静态文件挂载）
│  └─ requirements.txt
└─ frontend\                # Vue3 前端
   ├─ src\i18n\            # W1：UI 文案多语言 JSON
   ├─ src\utils\productI18n.ts  # W2：商品信息双语展示规则
   ├─ src\views\           # 页面（Products/Cart/Orders/Admin...）
   └─ package.json
```

---

## 2. 运行环境与启动方式

### 2.1 后端（FastAPI）

> 环境：你要求使用 `conda activate Qchat`。

```bat
cd F:\ISPproject
conda activate Qchat

cd backend
pip install -r requirements.txt

:: 重置/初始化示例数据（会清库重建）
:: 注意：该命令会：
:: 1) 清空数据库所有业务表数据（包括订单状态时间线 B4，避免重复）；
:: 2) 清空本地上传目录 backend/app/uploads（包括你手动上传的图片）。
:: 默认会生成 60 个商品，便于前端分页演示（A5，size=20 -> 至少 3 页）。
python -m app.seed

:: （可选）如需生成更多商品（例如 120 个），可通过环境变量调整：
:: 注意：再次运行仍然会“清库重建 + 清空 uploads”。
set SEED_PRODUCT_COUNT=120
python -m app.seed
set SEED_PRODUCT_COUNT=

:: 启动后端
uvicorn app.main:app --reload --port 8001
```

- 后端默认挂载：`http://localhost:8001`
- 图片静态路径：`http://localhost:8001/uploads/...`（见 `backend/app/main.py`）

### 2.2 前端（Vue3）

```bat
cd F:\ISPproject\frontend
npm install
npm run dev
```

前端默认：`http://localhost:5173`

#### 前端如何配置后端地址

当前前端代码（`frontend/src/api/http.ts`）默认指向：`http://localhost:8001`。

如果你把后端跑在别的端口/地址，请在 `frontend/.env.local` 中配置：

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 3. 内置账号

- 管理员（Vendor/Admin）：`admin@demo.com` / `Admin1234`
- 普通用户（Customer）：`user@demo.com` / `User1234`

---

## 4. 需求实现对照（按编号可追踪）

> 下面是“你给的需求编号”与“代码关键位置”的对照。更细节的说明已写入源码注释中（只加注释、不改逻辑）。

### 4.1 A（Customer：账号/浏览/购物车/订单）

- **A1 注册（姓名/邮箱/密码/收货地址） + last address 规则**
  - 后端：`backend/app/routers/auth.py`、`backend/app/routers/addresses.py`、`backend/app/routers/orders.py`
  - 前端：`frontend/src/views/Register.vue`、`frontend/src/views/Checkout.vue`

- **A2 未登录可浏览商品；登录后才可使用 cart/order/admin**
  - 前端路由守卫：`frontend/src/router/index.ts`
  - 后端鉴权依赖：`backend/app/deps.py`

- **A3 商品列表（书名/价格/缩略图）**
  - 前端：`frontend/src/views/Products.vue`
  - 后端：`backend/app/routers/products.py`（动态计算 `thumbnail_url`）

- **A4 搜索（按书名）**
  - 前端：`Products.vue` keyword
  - 后端：`GET /api/products?keyword=...`

- **A5 长列表导航（分页）**
  - 前端：`el-pagination`
  - 后端：`GET /api/products?page&size` 返回 `total`

- **A6 商品详情额外属性（作者/出版方/简介等）**
  - 前端：`frontend/src/views/ProductDetail.vue`
  - 后端模型：`backend/app/models.py::Product`

- **A7~A10 购物车增删改查**
  - 后端：`backend/app/routers/cart.py`
  - 前端：`frontend/src/views/Cart.vue`

- **A11 结算下单：创建订单并清空购物车**
  - 后端：`backend/app/routers/orders.py::create_order`
  - 前端：`frontend/src/views/Checkout.vue`

- **A12 订单列表（倒序）**
  - 后端：`backend/app/routers/orders.py::list_my_orders`
  - 前端：`frontend/src/views/Orders.vue`

- **A13 订单详情：地址快照 + 行项目快照 + 状态时间线**
  - 后端：`backend/app/models.py::Order(ship_*)`、`orders.py::get_order`
  - 前端：`frontend/src/views/OrderDetail.vue`

- **A14~A18 Vendor 商品管理（浏览/搜索/新增/编辑/上下架）**
  - 后端：`backend/app/routers/admin.py`
  - 前端：`frontend/src/views/admin/AdminProducts.vue`

- **A15 按商品 ID 子串搜索**
  - 后端：`admin.py::list_all_products`（`cast(Product.id, String).like`）

- **A19~A20 Vendor 订单列表/详情**
  - 后端：`admin.py::admin_list_orders/admin_get_order`
  - 前端：`frontend/src/views/admin/AdminOrders.vue`、`AdminOrderDetail.vue`

### 4.2 B（多图 + 订单处理）

- **B1 每个 SKU 多图（本地上传/删除），详情页轮播展示**
  - 后端：`backend/app/routers/admin.py::upload_sku_photos/delete_sku_photo`
  - 静态挂载：`backend/app/main.py`（`/uploads`）
  - 前端：`ProductDetail.vue` + `ImageCarousel.vue`

- **B2 订单状态流转**
  - 状态：`pending -> shipped -> completed`；`pending -> cancelled`
  - 自动取消：pending 超过 3 天未发货自动转 cancelled
  - 后端：`backend/app/routers/orders.py`、`backend/app/routers/admin.py`
  - 前端：用户取消/确认收货（`OrderDetail.vue`），vendor 发货/取消（AdminOrders/AdminOrderDetail）

- **B3 按订单当前状态过滤**
  - 后端：`GET /api/orders?status=...`
  - 前端：`Orders.vue` 当前使用前端过滤（代码中有注释说明）

- **B4 状态时间线（状态名 + 时间点）**
  - 后端：`backend/app/models.py::OrderStatusEvent` + `status_events`
  - 前端：订单详情页 timeline 展示

### 4.3 D（可配置商品 / SKU / 库存）

- **D1 可配置商品（至少 1 个 option）**
  - `Product.options` 以 JSON 保存选项结构（例如版本）

- **D2 加购必须选择每个 option，并可用图片区分配置**
  - 前端：`ProductDetail.vue`（必须选择后才能匹配 SKU）
  - 后端：`GET /api/products/{id}/photos` 返回 by_sku 图片映射

- **D3 同一商品可买多个配置组合 + 数量可 > 1**
  - 购物车以 `sku_id` 为粒度：`CartItem.sku_id`

- **D4 每个配置组合是独立 SKU，独立库存/可售状态**
  - 后端：`ProductSKU(stock_quantity/is_available)` + 管理端 SKU CRUD

- **D5 缺货/不可售提示与拦截**
  - 后端：加入购物车/更新数量/下单都校验库存与可售
  - 前端：`Cart.vue`/`Checkout.vue` 有红色提示并禁用下单

### 4.4 W（国际化）

- **W1 非商品信息：多语言 JSON 映射 + UI 语言切换**
  - `frontend/src/i18n/zh.json/en.json/ja.json/zh-TW.json`
  - `frontend/src/App.vue` 提供切换按钮，写入 `localStorage(lang)`

- **W2 商品信息：双语录入 + 展示规则**
  - 后端：商品字段保存中英双语（`title/title_en/author/author_en/...`），并在创建/编辑时强制输入（schema 层约束）
  - 前端：`frontend/src/utils/productI18n.ts` 实现规则：
    - locale 为 `zh` 或 `zh-TW`：商品信息统一显示中文（简体字段）
    - 其他语言（en/ja/...）：商品信息统一显示英文

---

## 5. 关键业务规则说明（便于验收/讲解）

### 5.1 “只记忆上一次地址”(last address)（A1/A11）

- 注册时填写的收货地址会作为用户的 **首次 last address**。
- 结算页会调用 `GET /api/addresses/last` 预填地址。
- 用户每次下单提交的新地址，会覆盖保存为新的 last address，供下次预填。
- **订单中保存下单时的地址快照**（`Order.ship_*`），确保历史订单展示不受后续地址修改影响（A13）。

### 5.2 订单状态流转与时间线（B2/B4）

- `pending`：用户刚下单
- `shipped`：vendor 发货（pending -> shipped）
- `completed`：用户确认收货（shipped -> completed）
- `cancelled`：用户取消 pending 或 vendor 取消 pending
- 自动取消：pending 超过 3 天未发货会自动取消（在访问订单相关接口时触发扫描）

系统同时保存：
- `orders.status`：当前最后状态（用于列表/过滤）
- `order_status_events`：状态历史事件（用于详情页 timeline）

---

## 6. 手动验收流程（建议）

### 6.1 Customer 流程（A* + 部分 B/D/W）

1. 未登录访问 `/products`：可浏览列表/搜索/查看详情（A2/A3/A4/A5/A6）
2. 注册新用户并填写地址（A1）
3. 在详情页选择版本（若有）并加入购物车（A7/D2/D3/D5）
4. 购物车修改数量/删除（A8/A9/A10）
5. 结算页自动预填 last address，并下单（A11 + A1 地址覆盖）
6. 查看订单列表/详情、状态时间线（A12/A13/B4）
7. pending 状态下取消订单（B2）或 shipped 后确认收货（B2）
8. 切换语言：UI 文案变化（W1），商品信息按规则切换中/英（W2）

### 6.2 Vendor/Admin 流程（A14~A20 + B1/B2/D*）

1. 管理端商品列表搜索（A14/A15）
2. 新建商品：填写中英双语 + options（A16/W2/D1）
3. 为商品创建多个 SKU（不同配置）并设置库存/可售（D4/D5）
4. 为每个 SKU 上传多张图片（B1/A16）
5. 上/下架商品（A18）
6. 管理端查看订单列表/详情并发货/取消（A19/A20/B2/B4）

---

## 7. 开发说明

- SQLite 不支持原生 JSON/ENUM：本项目用 `TEXT` 存 JSON 字符串，在应用层解析。
- 图片上传为本地文件：`backend/app/uploads/sku_{id}/...`，通过 `/uploads/...` 访问。
