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

    async def extract_book_query(self, message, history, agent_lang="zh"):
        return message

    async def compose_book_answer(self, message, history, plan, books, catalog_snapshot, agent_lang="zh"):
        if not books:
            return "No relevant information found." if str(agent_lang).startswith("en") else "暂无相关信息"
        if str(agent_lang).startswith("en"):
            return books[0].get("title_en") or books[0]["title"]
        return f"《{books[0]['title']}》"

    async def compose_cart_confirmation(self, action, product_title, quantity, option_summary, agent_lang="zh"):
        if str(agent_lang).startswith("en"):
            if action == "add":
                return f"Confirm adding '{product_title}' to cart?"
            if action == "update":
                return f"Confirm updating '{product_title}' quantity to {quantity}?"
            return f"Confirm removing '{product_title}' from cart?"
        return f"确认处理《{product_title}》吗？"

    async def plan_chat(self, message, history, agent_lang="zh"):
        lowered = str(message or "").lower()
        if any(word in lowered for word in ["cart", "add", "remove", "update", "buy", "购物车", "加入", "删除", "更新"]):
            return {
                "intent": "cart_action",
                "query": message,
                "tone": "friendly",
                "needs_catalog": True,
                "needs_follow_up": False,
                "follow_up_question": "",
                "reason": "fake-cart-action",
            }
        return {
            "intent": "catalog_lookup",
            "query": message,
            "tone": "friendly",
            "needs_catalog": True,
            "needs_follow_up": False,
            "follow_up_question": "",
            "reason": "fake-catalog",
        }

    def has_explicit_purchase_intent(self, message, agent_lang="zh"):
        lowered = str(message or "").lower()
        return any(word in lowered for word in ["想买", "加入购物车", "买", "buy", "add to cart", "purchase"])

    async def suggest_cart_action(self, message, history, references, agent_lang="zh"):
        lowered = str(message or "").lower()
        if any(word in lowered for word in ["what is in my cart", "show my cart", "购物车里有什么", "看看购物车"]):
            return {
                "should_act": True,
                "action": "list",
                "requires_confirmation": False,
                "product_title": "",
                "sku_id": None,
                "sku_requests": [],
                "item_id": None,
                "quantity": None,
                "user_message": "I will check your current cart." if str(agent_lang).startswith("en") else "我来帮你查看当前购物车。",
                "missing_fields": [],
            }

        if any(word in lowered for word in ["add to cart", "buy", "加入购物车", "想买"]):
            first = references[0] if references else {}
            title = (first.get("title_en") or first.get("title") or "").strip() if str(agent_lang).startswith("en") else (first.get("title") or first.get("title_en") or "").strip()
            return {
                "should_act": True,
                "action": "add",
                "requires_confirmation": True,
                "product_title": title,
                "sku_id": 100,
                "sku_requests": [{"sku_id": 100, "quantity": 2 if "2" in lowered else 1}],
                "item_id": None,
                "quantity": 2 if "2" in lowered else 1,
                "user_message": "I detected your purchase intent." if str(agent_lang).startswith("en") else "我已识别到你的购书意图。",
                "missing_fields": [],
            }

        return {
            "should_act": False,
            "action": "none",
            "requires_confirmation": False,
            "product_title": "",
            "sku_id": None,
            "sku_requests": [],
            "item_id": None,
            "quantity": None,
            "user_message": "",
            "missing_fields": [],
        }

    def resolve_cart_item_action(self, message, suggestion, cart_items, agent_lang="zh"):
        lowered = str(message or "").lower()
        if any(word in lowered for word in ["what is in my cart", "show my cart", "购物车里有什么", "看看购物车"]):
            return {
                "should_act": True,
                "action": "list",
                "requires_confirmation": False,
                "product_title": "",
                "sku_id": None,
                "sku_requests": [],
                "item_id": None,
                "quantity": None,
                "user_message": "I will check the current user's cart for you." if str(agent_lang).startswith("en") else "我来为你查看当前会话用户的购物车。",
                "missing_fields": [],
            }
        return suggestion

    def _extract_sku_requests(self, message, reference):
        lowered = str(message or "").lower()
        quantity = 2 if "2" in lowered or "two" in lowered or "两" in lowered else 1
        sku_ids = reference.get("sku_ids") or [100]
        return [{"sku_id": int(sku_ids[0]), "quantity": quantity}]


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


def test_chat_language_mapping_zh_tw_returns_chinese(tmp_path: Path):
    client, _ = make_client(tmp_path)
    response = client.post(
        "/chat",
        json={"message": "请介绍三体"},
        headers={"Accept-Language": "zh-TW"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "《三体》"


def test_chat_language_mapping_ja_returns_english(tmp_path: Path):
    client, _ = make_client(tmp_path)
    response = client.post(
        "/chat",
        json={"message": "Introduce The Three-Body Problem"},
        headers={"Accept-Language": "ja"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "The Three-Body Problem"


def test_chat_english_add_intent_generates_add_action(tmp_path: Path):
    client, _ = make_client(tmp_path)
    response = client.post(
        "/chat",
        json={"message": "Add 2 hardcover copies of The Three-Body Problem to my cart"},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    action = data.get("action_suggestion") or {}
    assert action.get("action") == "add"
    assert action.get("should_act") is True
    assert action.get("quantity") == 2
    assert str(action.get("user_message") or "").lower().startswith("i detected")


def test_chat_english_list_intent_generates_list_action(tmp_path: Path):
    client, _ = make_client(tmp_path)
    response = client.post(
        "/chat",
        json={"message": "What is in my cart?"},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    action = data.get("action_suggestion") or {}
    assert action.get("action") == "list"
    assert action.get("should_act") is True


def test_chat_history_keeps_plain_apostrophe_text(tmp_path: Path):
    client, _ = make_client(tmp_path)

    response = client.post(
        "/chat",
        json={"message": "I'd like to know what is in my cart"},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["reply"] == "I will check the current user's cart for you."
    history_contents = [item["content"] for item in data["history"]]
    assert "I'd like to know what is in my cart" in history_contents
    assert "I will check the current user's cart for you." in history_contents
    assert all("&#x27;" not in content for content in history_contents)
