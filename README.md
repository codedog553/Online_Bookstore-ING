# 在线书店系统（本地运行版）

不需要部署，仅本地运行；不考虑性能，只实现功能。前端 Vue3 + Vite + Element Plus，后端 FastAPI + SQLite。

## 目录结构

- backend/
  - app/  FastAPI 应用（含模型、路由、认证、示例数据种子）
  - requirements.txt  后端依赖
- frontend/
  - 基于 Vite 的 Vue3 前端

## 一次性准备

1) 后端

```
cd f:\ISPproject\backend
pip install -r requirements.txt
# 初始化示例数据（可重复执行会清库并重建示例）
python -m app.seed
# 启动后端（默认为端口 8000）
uvicorn app.main:app --reload --port 8000
```

2) 前端（Node 16+）

```
cd f:\ISPproject\frontend
npm install
# (可选) 配置后端地址：新建 .env.local
# VITE_API_BASE_URL=http://localhost:8000
npm run dev
# 前端默认 http://localhost:5173
```

后端已允许 CORS，本地前端可直接访问；前端默认后端基址为 http://localhost:8000，也支持通过 Vite 环境变量覆盖：

```
VITE_API_BASE_URL=http://localhost:8000
```

## 账号

- 管理员：admin@demo.com / Admin1234
- 普通用户：user@demo.com / User1234

## 功能清单（已实现）

- 认证：注册、登录、获取/更新当前用户（JWT 存储于 localStorage）
- 商品：列表、详情、搜索（按书名关键字）、多图展示、版本（平装/精装）选择
- 购物车：增删改查、数量修改
- 订单：下单、我的订单列表、订单详情、取消待处理订单
- 地址：结算页填写“上一次地址”（系统仅保存最近一次地址用于下次预填）
- 评论：查看、已购买用户可发表评论与评分
- 管理端：
  - 商品管理：新增、上/下架
  - 商品管理：支持编辑（含中英文信息）
  - 订单管理：查看所有订单、标记发货
  - 评论管理：列表/隐藏/删除
  - 销售报表：按日/周/月 + 时间范围 + 图表展示 + 畅销榜

注：商品信息仅支持中/英文：当语言选择为繁中/日语时，商品字段按规则回退显示中文（仅 en 例外）。

## 常见问题

1) VS Code 报“找不到模块 vue / vue-router / axios ...”
- 说明还没有安装前端依赖，请先在 frontend 执行 `npm install`。

2) 端口冲突
- 如 8000 或 5173 被占用，可改用其他端口：
  - 后端：`uvicorn app.main:app --reload --port 8001`，然后把 `frontend/src/api/http.ts` 中 baseURL 改为 `http://localhost:8001`
  - 前端：`vite.config.ts` 修改 server.port

推荐做法：不改代码，直接在 `frontend/.env.local` 设置：

```
VITE_API_BASE_URL=http://localhost:8001
```

3) 数据库文件位置
- SQLite 默认位于 `backend/app.db`（由 SQLAlchemy 自动创建）。

4) 重置示例数据
- 运行 `python -m app.seed` 会清空并重建示例数据（包括管理员/用户、分类、商品、SKU、示例订单与评论）。

## 手动验证流程

- 用 `user@demo.com` 登录 → 浏览商品 → 进入详情选择“版本”与数量 → 加入购物车 → 购物车修改数量/删除 → 去结算（预填上次地址）→ 下单 → 我的订单/订单详情 → 取消待处理订单
- 用 `admin@demo.com` 登录 → 后台-商品：新增/编辑/上架/下架、管理 SKU → 后台-订单：标记发货 → 后台-评论：隐藏/删除 → 后台-报表：选择粒度/范围查看趋势与畅销榜

## 可访问性与国际化

- 图片提供 alt 文本、表单有标签、按钮可键盘操作；
- i18n：系统信息支持 zh / zh-TW / en / ja；头部可切换语言并同步更新 `<html lang>`。

## 开发说明

- ORM/模型与具体 API 请查看 backend/app 下的代码与路由；
- 数据简化：SQLite 不支持原生 ENUM/JSON，项目用 TEXT 存 JSON 字符串并在应用层解析。
