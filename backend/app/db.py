from sqlalchemy import create_engine, text
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

    # --- 轻量 SQLite 自迁移（无需 Alembic）---
    # 目的：在不删除现有 app.db 的情况下，允许我们逐步给表加新列。
    # 说明：只做 ADD COLUMN，不做危险的 drop/rename，以保证学习项目的可用性。
    with engine.begin() as conn:
        # products 表新增英文信息列（商品信息仅要求 zh/en）
        _ensure_column(conn, "products", "title_en", "VARCHAR(200)")
        _ensure_column(conn, "products", "author_en", "VARCHAR(100)")
        _ensure_column(conn, "products", "publisher", "VARCHAR(200)")
        _ensure_column(conn, "products", "publisher_en", "VARCHAR(200)")
        _ensure_column(conn, "products", "description_en", "TEXT")

        # product_skus: SKU 多图（B1/A16）
        _ensure_column(conn, "product_skus", "photos", "TEXT")

        # orders: 地址快照 + 状态时间点（A13/B4）
        _ensure_column(conn, "orders", "ship_receiver_name", "VARCHAR(100)")
        _ensure_column(conn, "orders", "ship_phone", "VARCHAR(20)")
        _ensure_column(conn, "orders", "ship_province", "VARCHAR(50)")
        _ensure_column(conn, "orders", "ship_city", "VARCHAR(50)")
        _ensure_column(conn, "orders", "ship_district", "VARCHAR(50)")
        _ensure_column(conn, "orders", "ship_detail_address", "VARCHAR(255)")
        _ensure_column(conn, "orders", "completed_at", "DATETIME")
        _ensure_column(conn, "orders", "cancelled_at", "DATETIME")

        _ensure_product_review_tables(conn)


def _ensure_column(conn, table: str, column: str, ddl_type: str):
    """若 SQLite 表中不存在 column，则执行 ALTER TABLE ADD COLUMN。

    参数:
      - ddl_type: 形如 "TEXT" / "VARCHAR(200)" / "INTEGER" ...
    """

    cols = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
    existing = {c["name"] for c in cols}
    if column in existing:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def _ensure_product_review_tables(conn):
    existing = {
        row[0]
        for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }

    if "product_ratings" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE product_ratings (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    order_id VARCHAR(20) NOT NULL,
                    rating INTEGER NOT NULL,
                    created_at DATETIME,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(product_id) REFERENCES products(id),
                    FOREIGN KEY(order_id) REFERENCES orders(order_id)
                )
                """
            )
        )

    if "product_comments" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE product_comments (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    content TEXT NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(product_id) REFERENCES products(id),
                    FOREIGN KEY(parent_id) REFERENCES product_comments(id)
                )
                """
            )
        )

    if "product_comment_likes" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE product_comment_likes (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    comment_id INTEGER NOT NULL,
                    created_at DATETIME,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(comment_id) REFERENCES product_comments(id)
                )
                """
            )
        )
