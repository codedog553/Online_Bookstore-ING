from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..repositories import cart, catalog
from .deepseek import DeepSeekService


@dataclass
class SkillContext:
    deepseek: DeepSeekService
    user_id: int | None = None
    agent_lang: str = "zh"


def _is_en(agent_lang: str) -> bool:
    return str(agent_lang or "zh").lower().startswith("en")


def _lang_text(agent_lang: str, zh: str, en: str) -> str:
    return en if _is_en(agent_lang) else zh


def _pick_reference_title(reference: Dict[str, Any], agent_lang: str) -> str:
    if _is_en(agent_lang):
        return str(reference.get("title_en") or reference.get("title") or "").strip()
    return str(reference.get("title") or reference.get("title_en") or "").strip()


class BookLookupSkill:
    name = "book_lookup"

    async def run(self, ctx: SkillContext, db: Session, message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        plan = await ctx.deepseek.plan_chat(message, history, agent_lang=ctx.agent_lang)
        query = str(plan.get("query") or "")
        intent = str(plan.get("intent") or "general_chat")
        explicit_purchase_intent = ctx.deepseek.has_explicit_purchase_intent(message, agent_lang=ctx.agent_lang)

        books: List[Dict[str, Any]] = []
        if bool(plan.get("needs_catalog")) or explicit_purchase_intent:
            books = catalog.search_books(db, query or message, history=history)
            if not books and query and query != message:
                books = catalog.search_books(db, message, history=history)
        if not books and explicit_purchase_intent:
            books = catalog.resolve_books_from_message(db, message)
        if explicit_purchase_intent:
            intent = "cart_action"
            plan["intent"] = "cart_action"

        catalog_snapshot = catalog.list_catalog(db, limit=12)
        reference_payload = [
            {
                "product_id": item["product_id"],
                "sku_ids": item["sku_ids"],
                "skus": item.get("skus") or [],
                "title": item["title"],
                "title_en": item.get("title_en"),
                "author": item.get("author"),
                "author_en": item.get("author_en"),
            }
            for item in books
        ]
        action_suggestion = await ctx.deepseek.suggest_cart_action(message, history, reference_payload, agent_lang=ctx.agent_lang)
        cart_payload = []
        if ctx.user_id is not None:
            cart_payload = [
                {
                    "item_id": item.id,
                    "sku_id": item.sku_id,
                    "product_title": item.sku.product.title,
                    "option_summary": item.sku.option_values,
                    "quantity": item.quantity,
                }
                for item in cart.list_items(db, ctx.user_id)
            ]
        action_suggestion = ctx.deepseek.resolve_cart_item_action(message, action_suggestion, cart_payload, agent_lang=ctx.agent_lang)
        # If resolver could not determine target item but we have cart snapshot, expose candidate_items
        # so frontend can prompt user to choose. Only do this for update/remove actions —
        # do not inject candidate_items for add actions (add targets catalog skus, not existing cart items).
        missing = action_suggestion.get("missing_fields") or []
        action = action_suggestion.get("action")
        # Only consider existing-cart-item selection for update/remove actions
        if action in {"update", "remove"} and (action_suggestion.get("item_id") is None or "item_id" in missing):
            if ctx.user_id is not None and cart_payload:
                candidate_items = [
                    {
                        "item_id": it.get("item_id"),
                        "sku_id": it.get("sku_id"),
                        "product_title": it.get("product_title"),
                        "option_summary": it.get("option_summary"),
                        "quantity": it.get("quantity"),
                    }
                    for it in cart_payload
                ]
                # only attach if not already present
                if not action_suggestion.get("candidate_items"):
                    action_suggestion["candidate_items"] = candidate_items
                # ensure missing_fields includes item_id so frontend will prompt selection
                if "item_id" not in missing:
                    missing.append("item_id")
                    action_suggestion["missing_fields"] = missing
                # prevent auto action when ambiguous
                action_suggestion["should_act"] = False
        if explicit_purchase_intent and reference_payload and action_suggestion.get("action") == "none":
            first = reference_payload[0]
            sku_requests = action_suggestion.get("sku_requests") or []
            if not sku_requests:
                sku_requests = ctx.deepseek._extract_sku_requests(message, first)
            action_suggestion = {
                "should_act": bool(sku_requests),
                "action": "add" if sku_requests else "none",
                "requires_confirmation": bool(sku_requests),
                "product_title": _pick_reference_title(first, ctx.agent_lang),
                "sku_id": sku_requests[0]["sku_id"] if sku_requests else None,
                "sku_requests": sku_requests,
                "item_id": None,
                "quantity": sum(int(item["quantity"]) for item in sku_requests) if sku_requests else None,
                "user_message": _lang_text(
                    ctx.agent_lang,
                    "我已经识别到你的购书意图，接下来会通过弹窗请你确认加入购物车。" if sku_requests else "我还缺少具体版本信息，暂时无法加入购物车。",
                    "I detected your purchase intent. I will ask for confirmation in a dialog before adding to cart." if sku_requests else "I still need the exact edition/specification before adding to cart.",
                ),
                "missing_fields": [] if sku_requests else ["sku_id"],
            }

        if action_suggestion.get("should_act") and action_suggestion.get("action") in {"add", "update", "remove", "list"}:
            if action_suggestion.get("action") == "add":
                reply = _lang_text(
                    ctx.agent_lang,
                    "我已经识别到你的购书意图。系统会立即弹出确认框；只有你点击确认后，才会把这些书加入当前会话用户的购物车。",
                    "I detected your purchase intent. A confirmation dialog will appear, and books will be added only after you confirm.",
                )
            elif action_suggestion.get("action") == "list":
                reply = _lang_text(ctx.agent_lang, "我来为你查看当前会话用户的购物车。", "I will check the current user's cart for you.")
            elif action_suggestion.get("action") == "update":
                reply = _lang_text(
                    ctx.agent_lang,
                    "我已经识别到你要修改购物车。系统会立即弹出确认框；只有你点击确认后，才会更新当前会话用户的购物车。",
                    "I detected you want to update the cart. A confirmation dialog will appear, and the cart will be updated only after you confirm.",
                )
            else:
                reply = _lang_text(
                    ctx.agent_lang,
                    "我已经识别到你要删除购物车项。系统会立即弹出确认框；只有你点击确认后，才会修改当前会话用户的购物车。",
                    "I detected you want to remove an item from the cart. A confirmation dialog will appear, and removal happens only after you confirm.",
                )
        else:
            reply = await ctx.deepseek.compose_book_answer(message, history, plan, books, catalog_snapshot, agent_lang=ctx.agent_lang)

        if action_suggestion.get("action") == "add" and not reference_payload:
            action_suggestion = {
                "should_act": False,
                "action": "none",
                "requires_confirmation": False,
                "product_title": "",
                "sku_id": None,
                "item_id": None,
                "quantity": None,
                "user_message": _lang_text(
                    ctx.agent_lang,
                    "我理解你有购书意愿，但我还没定位到具体书目。你可以告诉我书名、作者或版本，我再为你发起确认。",
                    "I understand that you want to buy a book, but I still cannot identify the exact title. Please tell me the title, author, or edition and I will proceed with confirmation.",
                ),
                "missing_fields": ["product"],
            }
        return {
            "reply": reply,
            "references": [] if intent == "general_chat" else reference_payload,
            "action_suggestion": action_suggestion,
            "created_at": datetime.utcnow(),
        }


class CartGuardSkill:
    name = "cart_guard"

    async def run(self, ctx: SkillContext, action: str, product_title: str, quantity: int | None, option_summary: str | None) -> str:
        return await ctx.deepseek.compose_cart_confirmation(action, product_title, quantity, option_summary, agent_lang=ctx.agent_lang)


class SkillRegistry:
    def __init__(self) -> None:
        self.book_lookup = BookLookupSkill()
        self.cart_guard = CartGuardSkill()
