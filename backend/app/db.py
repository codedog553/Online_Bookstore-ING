from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# SQLite 数据库文件固定放在与本文件同目录下（backend/app/app.db）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 对于 SQLite + FastAPI（单进程开发），关闭线程检查
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # 导入 models 并创建表
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
