from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import products as products_router
from .routers import cart as cart_router
from .routers import orders as orders_router
from .routers import reviews as reviews_router
from .routers import addresses as addresses_router
from .routers import admin as admin_router

app = FastAPI(title="Online Bookstore API", version="1.0")

# 开发环境 CORS（前端默认 5173）
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*",  # 简化开发
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 注册路由
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(products_router.router)
app.include_router(reviews_router.router)
app.include_router(cart_router.router)
app.include_router(orders_router.router)
app.include_router(addresses_router.router)
app.include_router(admin_router.router)


@app.get("/")
def root():
    return {"message": "Online Bookstore API running"}
