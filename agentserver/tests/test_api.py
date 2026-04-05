from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.container import build_container
from app.main import create_app
from app.models import Base, CartItem, Product, ProductSKU, User


class FakeDeepSeek:
    enabled = False

    async def extract_book_query(self, message, history):
        return message

    async def compose_book_answer(self, message, history, books):
        return "暂无相关信息" if not books else f"《{books[0]['title']}》"

    async def compose_cart_confirmation(self, action, product_title, quantity, option_summary):
        return f"确认处理《{product_title}》吗？"


def build_token(secret: str, user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(hours=2)}
    return jwt.encode(payload, secret, algorithm="HS256")


def make_client(tmp_path: Path):
    db_path = tmp_path / "agent_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        user = User(id=1, full_name="Demo User", email="user@demo.com", is_admin=False)
        product = Product(id=10, title="三体", title_en="The Three-Body Problem", author="刘慈欣", description="科幻小说", base_price=88.0, is_active=True)
        sku = ProductSKU(id=100, product_id=10, option_values='{"版本":"精装"}', stock_quantity=10, is_available=True)
        db.add_all([user, product, sku])
        db.commit()

    app = create_app()
    container = build_container(app.state.container.settings, TestingSession, TestingSession)
    container.deepseek = FakeDeepSeek()
    app.state.container = container
    return TestClient(app), container


def test_chat_returns_book(tmp_path: Path):
    client, _ = make_client(tmp_path)
    response = client.post("/chat", json={"message": "请介绍三体"})
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "《三体》"


def test_cart_add_confirmation_then_commit(tmp_path: Path):
    client, container = make_client(tmp_path)
    token = build_token(container.settings.jwt_secret, 1)
    csrf_resp = client.get("/csrf-token", headers={"Authorization": f"Bearer {token}"})
    csrf_token = csrf_resp.json()["csrf_token"]

    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}
    first = client.post("/cart/add", headers=headers, json={"sku_id": 100, "quantity": 2, "confirmed": False})
    assert first.status_code == 200
    confirmation_token = first.json()["confirmation_token"]

    second = client.post("/cart/add", headers=headers, json={"sku_id": 100, "quantity": 2, "confirmed": True, "confirmation_token": confirmation_token})
    assert second.status_code == 200
    assert second.json()["success"] is True

    with container.write_sessionmaker() as db:
        item = db.query(CartItem).filter(CartItem.user_id == 1, CartItem.sku_id == 100).first()
        assert item is not None
        assert item.quantity == 2
