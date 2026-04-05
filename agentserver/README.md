# Agent Server

`agentserver` 是一个独立的智能体微服务，位于现有 `backend` 与 `frontend` 之间，专门负责：

- 保留 DeepSeek 原生聊天能力，并在其基础上增强书籍检索
- 多轮对话上下文维护
- 购物车操作确认语句生成
- 受控的购物车增删改执行
- 安全防护、审计日志、限流、OpenAPI 文档

## 目录

```text
agentserver/
├─ app/
│  ├─ api.py
│  ├─ config.py
│  ├─ container.py
│  ├─ db.py
│  ├─ logging_config.py
│  ├─ main.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ security.py
│  ├─ services/
│  │  ├─ conversations.py
│  │  ├─ deepseek.py
│  │  ├─ filters.py
│  │  ├─ rate_limit.py
│  │  └─ skills.py
│  └─ repositories/
│     ├─ cart.py
│     └─ catalog.py
├─ tests/
│  └─ test_api.py
├─ .env.example
└─ requirements.txt
```

## 运行

```bat
cd F:\Online_Bookstore-ING-master\agentserver
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8011
```

默认文档：

- Swagger UI: `http://localhost:8011/docs`
- OpenAPI JSON: `http://localhost:8011/openapi.json`

## DeepSeek 配置

在 `agentserver/.env` 中设置：

```env
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-chat
```

未配置 API Key 时，服务仍可运行，但会自动切换到本地降级逻辑，方便联调与测试。

## HTTPS

本地开发可直接 HTTP 运行；如果要严格启用 HTTPS，可在本地证书存在时使用：

```bat
uvicorn app.main:app --host 0.0.0.0 --port 8011 --ssl-keyfile certs\localhost-key.pem --ssl-certfile certs\localhost.pem
```

并在 `.env` 中设置：

```env
AGENTSERVER_ENFORCE_HTTPS=true
```

## 权限隔离

- 微服务对“读侧”开放书籍检索、模糊匹配、基于简介/作者/出版社的推荐检索
- 微服务对“写侧”仍只实现购物车增删改
- 代码层面没有暴露支付、用户敏感信息、admin 管理接口
- PostgreSQL 场景建议额外配置：
  - `AGENT_DB_READ_URL` 绑定 `agent_reader`
  - `AGENT_DB_WRITE_URL` 绑定 `agent_cart_writer`
- SQLite 场景依赖本地文件权限与仓储层白名单控制

说明：当前策略是“放宽读权限、严格限制写权限”。也就是说，助手可以更自由地读取商品标题、作者、出版社、简介等字段用于推荐与多轮检索，但购物车变更仍保留 JWT、CSRF、限流、事务、确认 token 与日志审计。

进一步说明：当前聊天模型是“Chatbot + Tools”的智能体模式，即：DeepSeek 官方 API 负责自然语言理解、意图规划、上下文会话与回复生成；API 负责执行数据库只读检索与购物车操作。

- 普通对话（如问候、自我介绍、能力说明）保留 DeepSeek chat 能力
- 书籍相关对话会额外注入本地数据库检索结果与书库快照，帮助模型做基于事实的回答与推荐
- 购物车相关变更不通过聊天直接执行，只通过独立 cart API 执行
- 多轮上下文由 `ConversationStore` 维护，模型基于上下文决定是继续聊天、延续推荐，还是触发只读检索

当前工作流：

1. 用户消息先交给 DeepSeek 做意图规划（general chat / catalog lookup / recommendation / cart help / cart action）
2. 若需要书库数据，微服务调用本地只读查询接口
3. DeepSeek 结合上下文 + 规划结果 + 数据库结果生成自然语言回复
4. 若涉及购物车修改，由前端再调用独立 cart API 执行确认与提交

当前购物车能力限定为“当前会话用户自己的购物车增删改查”：

- `GET /cart`：查看当前登录用户购物车
- `POST /cart/add`：向当前登录用户购物车加购
- `PUT /cart/update`：修改当前登录用户购物车项数量
- `DELETE /cart/remove`：删除当前登录用户购物车项

安全边界：

- 所有 cart 接口都以 JWT 中的当前用户 `sub` 为准
- 对话会话也绑定到当前用户或当前匿名 IP，禁止跨用户复用 conversation_id
- 不接受任意指定其他用户 ID
- 只允许购物车 CRUD，不允许支付、订单结算、admin 等敏感操作
- add / update / remove 都必须先生成确认语句，再由前端确认后提交

前端确认 UX：

- 所有 agent 触发的 cart 增删改都以居中弹窗展示
- 不自动消失，不自动执行，必须由用户手动点击“确认”或“取消”
- 提示信息使用更大的可读字号，避免 toast 短时间闪过

当前对话行为规则：

- 当用户表达明确购书意愿时，智能体先回复理解信息，再弹出确认框
- 如果一句话中包含多个 SKU 意图（例如同一本书的精装一本、平装一本），会为当前会话用户生成批量确认，并在一次确认后顺序加入购物车
- 用户点击“确认”后，才会对当前会话用户的购物车执行新增/删改查
- 用户点击“取消”后，不执行任何 cart 变更
- 如果不是 cart 意图，则保持纯聊天/推荐模式，不触发数据写操作

已支持的聊天式 cart 操作示例：

- `我想买一本精装的人类简史和一本平装的人类简史` -> add + 弹窗确认
- `把购物车里的人类简史精装改成两本` -> update + 弹窗确认
- `把购物车里那本平装删掉` -> remove + 弹窗确认
- `看看我的购物车` -> list

## 前端对接

在 `frontend/.env.local` 中增加：

```env
VITE_AGENT_API_BASE_URL=http://localhost:8011
```

## MCP / Skills 设计

该微服务内部采用 MCP 风格的“工具 + Skills”结构：

- `book_lookup` skill：负责对话理解、书籍检索、答案生成
- `cart_guard` skill：负责购物车操作确认文案生成
- skill 只允许调用仓储层白名单工具，不允许访问 admin / payment 能力

这使后续替换模型、接入新的数据库、迁移到其他项目时，只需替换 skill 或 repository，而不需要推翻 API 设计。
