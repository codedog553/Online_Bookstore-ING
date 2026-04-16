from __future__ import annotations

import json
import re
import logging
from typing import Any, Dict, List

import httpx

from ..config import Settings
from .rate_limit import AsyncQpsGate


class DeepSeekService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.qps_gate = AsyncQpsGate(settings.deepseek_qps)
        self.logger = logging.getLogger(__name__)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    def diagnostics(self) -> Dict[str, Any]:
        masked = ""
        if self.settings.deepseek_api_key:
            key = self.settings.deepseek_api_key
            masked = f"{key[:6]}...{key[-4:]}" if len(key) >= 10 else "configured"
        return {
            "enabled": self.enabled,
            "api_url": self.settings.deepseek_api_url,
            "model": self.settings.deepseek_model,
            "api_key_masked": masked,
        }

    @staticmethod
    def _is_en_lang(agent_lang: str) -> bool:
        return str(agent_lang or "zh").lower().startswith("en")

    @classmethod
    def _lang_text(cls, agent_lang: str, zh: str, en: str) -> str:
        return en if cls._is_en_lang(agent_lang) else zh

    async def plan_chat(self, message: str, history: List[Dict[str, str]], agent_lang: str = "zh") -> Dict[str, Any]:
        if not self.enabled:
            return self._fallback_plan(message, agent_lang=agent_lang)
        prompt = (
            "你是在线书店智能体的意图规划器。"
            "请理解用户消息和上下文，决定这轮对话的意图。"
            "你不能执行操作，只能规划。"
            "输出严格 JSON，不要输出额外文字。"
            "JSON 结构："
            "{"
            '"intent":"general_chat|catalog_lookup|catalog_recommendation|cart_help|cart_action",'
            '"query":"用于数据库检索的自然语言关键词，没有则为空字符串",'
            '"tone":"friendly|calm|supportive|concise",'
            '"needs_catalog":true,'
            '"needs_follow_up":false,'
            '"follow_up_question":"如果需要追问，填一句自然语言，否则为空字符串",'
            '"reason":"简短说明"'
            "}。"
            "规则："
            "1. 问候、自我介绍、闲聊、情绪支持属于 general_chat；"
            "2. 问书名/作者/某本书详情属于 catalog_lookup；"
            "3. 求推荐、按题材/心情/用途找书属于 catalog_recommendation；"
            "4. 问购物车怎么做属于 cart_help；"
            "5. 明确要求加入/修改/删除购物车属于 cart_action；"
            "6. 只有 catalog_lookup/catalog_recommendation 才 needs_catalog=true。"
            + self._lang_text(
                agent_lang,
                " follow_up_question 与 reason 使用中文。",
                " follow_up_question and reason must be written in English.",
            )
        )
        payload = await self._chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({"history": history, "message": message}, ensure_ascii=False)},
            ],
            json_mode=True,
        )
        try:
            data = json.loads(payload)
            return {
                "intent": str(data.get("intent") or "general_chat"),
                "query": str(data.get("query") or "").strip(),
                "tone": str(data.get("tone") or "friendly"),
                "needs_catalog": bool(data.get("needs_catalog")),
                "needs_follow_up": bool(data.get("needs_follow_up")),
                "follow_up_question": str(data.get("follow_up_question") or "").strip(),
                "reason": str(data.get("reason") or "").strip(),
            }
        except Exception:
            return self._fallback_plan(message, agent_lang=agent_lang)

    def _fallback_plan(self, message: str, agent_lang: str = "zh") -> Dict[str, Any]:
        lowered = (message or "").lower()
        if self._is_identity_question(message) or self._is_greeting(message) or any(word in lowered for word in ["不开心", "难过", "烦", "心情", "sad", "upset", "stressed", "depressed"]):
            return {
                "intent": "general_chat",
                "query": "",
                "tone": "supportive" if any(word in lowered for word in ["不开心", "难过", "烦", "心情", "sad", "upset", "stressed", "depressed"]) else "friendly",
                "needs_catalog": False,
                "needs_follow_up": False,
                "follow_up_question": "",
                "reason": "fallback-general-chat",
            }
        if any(word in lowered for word in ["购物车", "加入", "加购", "删除", "移除", "修改数量", "更新数量", "cart", "add to cart", "remove", "delete", "update quantity", "change quantity"]):
            return {
                "intent": "cart_action",
                "query": "",
                "tone": "friendly",
                "needs_catalog": False,
                "needs_follow_up": False,
                "follow_up_question": "",
                "reason": "fallback-cart-action",
            }
        if any(word in lowered for word in ["推荐", "想看", "想要", "给我", "相关", "有没有", "适合", "recommend", "suggest", "any books", "suitable", "related"]):
            return {
                "intent": "catalog_recommendation",
                "query": message.strip(),
                "tone": "friendly",
                "needs_catalog": True,
                "needs_follow_up": False,
                "follow_up_question": "",
                "reason": "fallback-recommendation",
            }
        return {
            "intent": "catalog_lookup" if self._is_book_related(message) else "general_chat",
            "query": message.strip() if self._is_book_related(message) else "",
            "tone": "friendly",
            "needs_catalog": self._is_book_related(message),
            "needs_follow_up": False,
            "follow_up_question": "",
            "reason": "fallback-default",
        }

    async def suggest_cart_action(self, message: str, history: List[Dict[str, str]], references: List[Dict[str, Any]], agent_lang: str = "zh") -> Dict[str, Any]:
        if not self.enabled:
            return self._fallback_cart_action(message, references, agent_lang=agent_lang)
        prompt = (
            "你是购物车动作规划器。"
            "请根据用户当前消息、上下文和已知书籍 references，判断是否需要执行购物车相关动作。"
            "输出严格 JSON，不要输出额外文字。"
            "JSON 结构："
            "{"
            '"should_act":true,'
            '"action":"none|list|add|update|remove",'
            '"requires_confirmation":true,'
            '"product_title":"",'
            '"sku_id":null,'
            '"sku_requests":[], '
            '"item_id":null,'
            '"quantity":null,'
            '"user_message":"给用户看的自然语言说明或追问"'
            "}。"
            "规则："
            "1. 只能规划当前会话用户自己的购物车；"
            "2. add/update/remove/list 都只能针对当前会话用户自己的购物车；"
            "3. add/update/remove 必须 requires_confirmation=true；"
            "4. 如果信息不足，action 用 none，并在 user_message 中自然追问；"
            "5. 如果用户只是问购物车里有什么，用 action=list；"
            "6. 不允许涉及支付、订单、他人数据或 admin。"
            "7. 当用户表达了明确购书意愿（如 想买/要买/加入购物车/买一本，或 buy/purchase/add to cart）时，如果 references 中能定位到书，优先输出 add 动作；"
            "8. 当用户只是聊天、咨询、推荐，不要输出 cart 动作。"
            "9. 如果用户一次想买多个版本/规格，可在 sku_requests 中返回多个对象，格式为 [{\"sku_id\":123,\"quantity\":1}]。"
            + self._lang_text(agent_lang, " user_message 使用中文。", " user_message must be written in English.")
        )
        payload = await self._chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({"history": history, "message": message, "references": references}, ensure_ascii=False)},
            ],
            json_mode=True,
        )
        try:
            data = json.loads(payload)
            return {
                "should_act": bool(data.get("should_act")),
                "action": str(data.get("action") or "none"),
                "requires_confirmation": bool(data.get("requires_confirmation", True)),
                "product_title": str(data.get("product_title") or "").strip(),
                "sku_id": data.get("sku_id"),
                "sku_requests": data.get("sku_requests") or [],
                "item_id": data.get("item_id"),
                "quantity": data.get("quantity"),
                "user_message": str(data.get("user_message") or "").strip(),
                "missing_fields": data.get("missing_fields") or [],
            }
        except Exception:
            return self._fallback_cart_action(message, references, agent_lang=agent_lang)

    @classmethod
    def _reference_title(cls, reference: Dict[str, Any], agent_lang: str) -> str:
        if cls._is_en_lang(agent_lang):
            return str(reference.get("title_en") or reference.get("title") or "").strip()
        return str(reference.get("title") or reference.get("title_en") or "").strip()

    @staticmethod
    def _extract_numeric_quantity(lowered: str) -> int | None:
        if "两本" in lowered:
            return 2
        if "一本" in lowered:
            return 1

        zh_match = re.search(r"(\d{1,2})\s*本", lowered)
        if zh_match:
            return int(zh_match.group(1))

        en_match = re.search(r"\b(\d{1,2})\s*(?:copies|copy|books|book|pcs?|pieces?)\b", lowered)
        if en_match:
            return int(en_match.group(1))

        set_match = re.search(r"\b(?:set(?:\s+\w+){0,3}\s+to|change(?:\s+\w+){0,3}\s+to|to)\s*(\d{1,2})\b", lowered)
        if set_match:
            return int(set_match.group(1))

        word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
        for word, number in word_map.items():
            if re.search(rf"\b{word}\s+(?:copies|copy|books|book)\b", lowered):
                return number
        return None

    def _fallback_cart_action(self, message: str, references: List[Dict[str, Any]], agent_lang: str = "zh") -> Dict[str, Any]:
        lowered = (message or "").lower()
        if any(word in lowered for word in ["购物车", "看看购物车", "购物车里", "购物车有什么", "show my cart", "view my cart", "what is in my cart", "what's in my cart", "my cart"]):
            return {
                "should_act": True,
                "action": "list",
                "requires_confirmation": False,
                "product_title": "",
                "sku_id": None,
                "sku_requests": [],
                "item_id": None,
                "quantity": None,
                "user_message": self._lang_text(agent_lang, "我来帮你查看当前购物车。", "I will check your current cart."),
                "missing_fields": [],
            }
        if any(word in lowered for word in ["加入购物车", "加购", "买一", "买一本", "想买", "add to cart", "buy", "purchase", "put in cart"]):
            first = references[0] if references else {}
            sku_requests = self._extract_sku_requests(message, first)
            title = self._reference_title(first, agent_lang)
            if not sku_requests:
                return {
                    "should_act": False,
                    "action": "none",
                    "requires_confirmation": False,
                    "product_title": title,
                    "sku_id": None,
                    "sku_requests": [],
                    "item_id": None,
                    "quantity": None,
                    "user_message": self._lang_text(
                        agent_lang,
                        "我还缺少你要购买的具体版本或规格，请先告诉我选项后我再帮你确认。",
                        "I still need the exact edition/specification. Please tell me the option and then I can proceed with confirmation.",
                    ),
                    "missing_fields": ["sku_id"],
                }
            return {
                "should_act": True,
                "action": "add",
                "requires_confirmation": True,
                "product_title": title,
                "sku_id": sku_requests[0]["sku_id"] if sku_requests else None,
                "sku_requests": sku_requests,
                "item_id": None,
                "quantity": sum(int(item["quantity"]) for item in sku_requests),
                "user_message": self._lang_text(
                    agent_lang,
                    "我理解你想购买这本书。我会先弹出确认框，只有你确认后才会加入当前会话用户的购物车。",
                    "I understand you want to buy this book. I will show a confirmation dialog first, and it will be added only after you confirm.",
                ),
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

    def has_explicit_purchase_intent(self, message: str, agent_lang: str = "zh") -> bool:
        lowered = (message or "").lower()
        return any(
            word in lowered
            for word in [
                "想买",
                "要买",
                "买一本",
                "买一",
                "加入购物车",
                "加购",
                "放购物车",
                "buy",
                "purchase",
                "add to cart",
                "put in cart",
                "put into cart",
            ]
        )

    def resolve_cart_item_action(self, message: str, suggestion: Dict[str, Any], cart_items: List[Dict[str, Any]], agent_lang: str = "zh") -> Dict[str, Any]:
        lowered = (message or "").lower()
        if not cart_items:
            return suggestion

        def normalize(text: str) -> str:
            if not text:
                return ""
            s = str(text).lower()
            s = re.sub(r"[\s《》\"'：:（）()\-，。、,．]", "", s)
            return s

        def pick_target() -> Dict[str, Any] | None:
            hinted_title = normalize(str(suggestion.get("product_title") or ""))
            msg_norm = normalize(message)
            candidates: List[tuple[int, Dict[str, Any]]] = []
            for item in cart_items:
                title = str(item.get("product_title") or "")
                option_summary = str(item.get("option_summary") or "")
                title_norm = normalize(title)
                option_lower = option_summary.lower()
                score = 0

                if title_norm and hinted_title and title_norm == hinted_title:
                    score += 6
                if title_norm and title_norm in msg_norm:
                    score += 8
                if msg_norm and msg_norm in title_norm:
                    score += 4

                if ("精装" in lowered or "hardcover" in lowered) and ("精装" in option_summary or "hardcover" in option_lower):
                    score += 3
                if ("平装" in lowered or "paperback" in lowered) and ("平装" in option_summary or "paperback" in option_lower):
                    score += 3

                if title_norm and msg_norm:
                    for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", title_norm):
                        if token and token in msg_norm:
                            score += 1

                if score > 0:
                    candidates.append((score, item))

            if len(cart_items) == 1 and not candidates:
                return cart_items[0]
            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0], reverse=True)
            if len(candidates) == 1 or (candidates[0][0] >= candidates[1][0] + 3):
                return candidates[0][1]
            return None

        target = pick_target()
        if any(word in lowered for word in ["购物车里有什么", "看看购物车", "查看购物车", "我的购物车", "show my cart", "view my cart", "what is in my cart", "what's in my cart", "my cart"]):
            return {
                "should_act": True,
                "action": "list",
                "requires_confirmation": False,
                "product_title": "",
                "sku_id": None,
                "sku_requests": [],
                "item_id": None,
                "quantity": None,
                "user_message": self._lang_text(agent_lang, "我来为你查看当前会话用户的购物车。", "I will check the current user's cart for you."),
                "missing_fields": [],
            }

        if any(word in lowered for word in ["删除", "移除", "不要了", "去掉", "remove", "delete", "take out"]):
            if not target:
                candidate_items = [
                    {
                        "item_id": it.get("item_id"),
                        "sku_id": it.get("sku_id"),
                        "product_title": it.get("product_title"),
                        "option_summary": it.get("option_summary"),
                        "quantity": it.get("quantity"),
                    }
                    for it in cart_items
                ]
                return {
                    "should_act": False,
                    "action": "none",
                    "requires_confirmation": False,
                    "product_title": "",
                    "sku_id": None,
                    "sku_requests": [],
                    "item_id": None,
                    "quantity": None,
                    "user_message": self._lang_text(
                        agent_lang,
                        "我还不能确定你要删除购物车里的哪一项，请从下面候选中选择或告诉我书名/版本。",
                        "I still cannot determine which cart item to remove. Please choose from candidates below or tell me the title/edition.",
                    ),
                    "missing_fields": ["item_id"],
                    "candidate_items": candidate_items,
                }
            return {
                "should_act": True,
                "action": "remove",
                "requires_confirmation": True,
                "product_title": str(target.get("product_title") or ""),
                "sku_id": target.get("sku_id"),
                "sku_requests": [],
                "item_id": target.get("item_id"),
                "quantity": None,
                "user_message": self._lang_text(
                    agent_lang,
                    "我已经识别到你要删除购物车项，接下来会通过弹窗请你确认。",
                    "I detected you want to remove a cart item. I will ask for confirmation in a dialog.",
                ),
                "missing_fields": [],
            }

        if any(word in lowered for word in ["改成", "改为", "改到", "更新", "数量改", "增加", "减少", "加一", "减一", "两本", "2本", "一本", "1本", "update", "change", "quantity", "qty", "set to", "increase", "decrease", "add one", "minus one"]):
            if not target:
                candidate_items = [
                    {
                        "item_id": it.get("item_id"),
                        "sku_id": it.get("sku_id"),
                        "product_title": it.get("product_title"),
                        "option_summary": it.get("option_summary"),
                        "quantity": it.get("quantity"),
                    }
                    for it in cart_items
                ]
                return {
                    "should_act": False,
                    "action": "none",
                    "requires_confirmation": False,
                    "product_title": "",
                    "sku_id": None,
                    "sku_requests": [],
                    "item_id": None,
                    "quantity": None,
                    "user_message": self._lang_text(
                        agent_lang,
                        "我还不能确定你要修改购物车里的哪一项，请从下面候选中选择或告诉我书名/版本。",
                        "I still cannot determine which cart item to update. Please choose from candidates below or tell me the title/edition.",
                    ),
                    "missing_fields": ["item_id"],
                    "candidate_items": candidate_items,
                }

            quantity = None
            if any(word in lowered for word in ["减一", "少一", "decrease by one", "minus one", "less one"]) or ("减少" in lowered and "一本" in lowered):
                quantity = max(int(target.get("quantity") or 1) - 1, 0)
            elif any(word in lowered for word in ["加一", "多一", "increase by one", "plus one", "add one"]) or ("增加" in lowered and "一本" in lowered):
                quantity = int(target.get("quantity") or 0) + 1
            elif "两本" in lowered or "2本" in lowered:
                quantity = 2
            elif "一本" in lowered or "1本" in lowered:
                quantity = 1
            else:
                quantity = self._extract_numeric_quantity(lowered)

            if quantity is None:
                return suggestion

            return {
                "should_act": True,
                "action": "remove" if quantity == 0 else "update",
                "requires_confirmation": True,
                "product_title": str(target.get("product_title") or ""),
                "sku_id": target.get("sku_id"),
                "sku_requests": [],
                "item_id": target.get("item_id"),
                "quantity": quantity,
                "user_message": self._lang_text(
                    agent_lang,
                    "我已经识别到你要修改购物车数量，接下来会通过弹窗请你确认。" if quantity > 0 else "数量调整为 0 会删除该购物车项，接下来会通过弹窗请你确认。",
                    "I detected that you want to update cart quantity. I will ask for confirmation in a dialog." if quantity > 0 else "Quantity set to 0 will remove this cart item. I will ask for confirmation in a dialog.",
                ),
                "missing_fields": [],
            }

        return suggestion

    def _extract_sku_requests(self, message: str, reference: Dict[str, Any]) -> List[Dict[str, int]]:
        skus = reference.get("skus") or []
        if not skus:
            sku_ids = reference.get("sku_ids") or []
            quantity = self._extract_numeric_quantity((message or "").lower())
            safe_quantity = quantity if isinstance(quantity, int) and quantity > 0 else 1
            return [{"sku_id": int(sku_ids[0]), "quantity": safe_quantity}] if sku_ids else []

        lowered = (message or "").lower()
        requests: List[Dict[str, int]] = []
        matched_ids = set()

        def quantity_for(*keywords: str) -> int:
            if any(keyword and keyword in lowered for keyword in keywords):
                parsed = self._extract_numeric_quantity(lowered)
                return parsed if isinstance(parsed, int) and parsed > 0 else 1
            return 0

        for sku in skus:
            option_text = str(sku.get("option_values") or "")
            option_lower = option_text.lower()
            sku_id = sku.get("sku_id")
            if not sku_id or not sku.get("is_available", True):
                continue
            qty = 0
            if "精装" in option_text or "hardcover" in option_lower:
                qty = quantity_for("精装", "hardcover")
            elif "平装" in option_text or "paperback" in option_lower:
                qty = quantity_for("平装", "paperback")
            if qty > 0:
                matched_ids.add(int(sku_id))
                requests.append({"sku_id": int(sku_id), "quantity": qty})

        if requests:
            return requests

        parsed = self._extract_numeric_quantity(lowered)
        default_quantity = parsed if isinstance(parsed, int) and parsed > 0 else 1
        for sku in skus:
            sku_id = sku.get("sku_id")
            if sku_id and int(sku_id) not in matched_ids and sku.get("is_available", True):
                return [{"sku_id": int(sku_id), "quantity": default_quantity}]
        return []

    @staticmethod
    def _is_greeting(message: str) -> bool:
        value = (message or "").strip().lower()
        return value in {"你好", "hello", "hi", "嗨", "哈喽", "您好"}

    @staticmethod
    def _is_identity_question(message: str) -> bool:
        value = (message or "").strip().lower()
        return any(
            text in value
            for text in [
                "你是什么",
                "你是谁",
                "你是？",
                "你是啥",
                "自我介绍",
                "介绍一下你自己",
                "你能做什么",
                "你会什么",
                "what are you",
                "who are you",
            ]
        )

    @staticmethod
    def _is_general_chat(message: str) -> bool:
        return DeepSeekService._is_greeting(message) or DeepSeekService._is_identity_question(message)

    @staticmethod
    def _is_book_related(message: str) -> bool:
        value = (message or "").lower()
        keywords = [
            "书", "小说", "作者", "出版社", "推荐", "题材", "科幻", "反乌托邦", "推理", "爱情", "历史",
            "python", "编程", "计算机", "开发", "程序", "代码", "算法", "有没有", "找一本", "介绍这本",
            "book", "books", "novel", "author", "publisher", "recommend", "recommendation", "genre", "science fiction", "dystopian", "mystery", "romance", "history",
            "programming", "computer", "development", "code", "algorithm", "show me", "find a book",
        ]
        return any(keyword in value for keyword in keywords)

    @staticmethod
    def _wants_recommendation(message: str) -> bool:
        value = (message or "").lower()
        return any(keyword in value for keyword in [
            "推荐", "想要", "给我", "类似", "相关", "还有", "其他", "别的", "找一本", "有没有",
            "recommend", "suggest", "similar", "related", "another", "other", "find a book", "any books",
        ])

    @staticmethod
    def _is_follow_up(message: str) -> bool:
        value = (message or "").lower()
        return any(keyword in value for keyword in [
            "还有", "其他", "别的", "换一本", "类似", "除此之外", "除了",
            "another", "other", "else", "similar", "besides", "apart from", "anything else",
        ])

    @staticmethod
    def _short_desc(item: Dict[str, Any], size: int = 34, agent_lang: str = "zh") -> str:
        if DeepSeekService._is_en_lang(agent_lang):
            desc = (item.get("description_en") or item.get("description") or "No description").strip()
        else:
            desc = (item.get("description") or item.get("description_en") or "暂无简介").strip()
        return desc[:size].rstrip("，。；：,. ")

    @staticmethod
    def _title_key(item: Dict[str, Any]) -> str:
        return f"{item.get('title') or ''}|{item.get('title_en') or ''}"

    def _dedupe_books(self, books: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for item in books:
            key = self._title_key(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _infer_focus_from_history(self, message: str, history: List[Dict[str, str]]) -> str:
        current = (message or "").strip()
        if current and not self._is_follow_up(current):
            return current
        for item in reversed(history):
            if item.get("role") == "user":
                content = item.get("content", "").strip()
                if content and content != current and not self._is_greeting(content) and not self._is_identity_question(content):
                    return content
        return current

    def _theme_candidates(self, focus: str, catalog_snapshot: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        lowered_focus = focus.lower()
        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in catalog_snapshot:
            title = str(item.get("title") or "").lower()
            title_en = str(item.get("title_en") or "").lower()
            author = str(item.get("author") or "").lower()
            desc = str(item.get("description") or "").lower()
            desc_en = str(item.get("description_en") or "").lower()
            blob = " ".join(
                [
                    title,
                    title_en,
                    author,
                    str(item.get("author_en") or "").lower(),
                    str(item.get("publisher") or "").lower(),
                    str(item.get("publisher_en") or "").lower(),
                    desc,
                    desc_en,
                ]
            )
            score = 0
            if any(word in lowered_focus for word in ["编程", "计算机", "python", "开发", "程序", "代码", "算法", "软件", "programming", "computer", "software", "development", "code", "algorithm"]):
                if any(word in blob for word in ["python", "编程", "开发", "算法", "程序", "代码", "深度学习", "计算机", "机器学习", "keras"]):
                    score += 12
            if any(word in lowered_focus for word in ["科幻", "science fiction", "sci-fi"]):
                if any(word in title + " " + desc + " " + desc_en for word in ["科幻", "science fiction", "sci-fi", "宇宙", "文明", "外星", "未来"]):
                    score += 12
                if any(word in author for word in ["刘慈欣", "阿西莫夫", "verne", "asimov", "orwell", "玛丽", "雪莱"]):
                    score += 4
            if "反乌托邦" in lowered_focus or "dystopian" in lowered_focus:
                if any(word in desc + " " + desc_en + " " + title for word in ["极权", "监视", "控制", "社会", "反乌托邦", "dystopian", "surveillance", "totalitarian"]):
                    score += 10
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda item: item[0], reverse=True)
        result = []
        seen = set()
        for _, item in scored:
            key = self._title_key(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    async def extract_book_query(self, message: str, history: List[Dict[str, str]], agent_lang: str = "zh") -> str:
        if self._is_general_chat(message):
            return ""
        if not self.enabled:
            return message.strip()
        prompt = (
            "你是一个书店检索规划器。"
            "请从用户当前问题和上下文中提取最适合查询本地书库的关键词。"
            "仅返回 JSON：{\"query\":\"...\"}。"
            + self._lang_text(agent_lang, " query 可以是中文关键词。", " query should be in English keywords if possible.")
        )
        payload = await self._chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({"history": history, "message": message}, ensure_ascii=False)},
            ],
            json_mode=True,
        )
        try:
            data = json.loads(payload)
            return str(data.get("query") or message).strip()
        except json.JSONDecodeError:
            return message.strip()

    async def compose_book_answer(
        self,
        message: str,
        history: List[Dict[str, str]],
        plan: Dict[str, Any],
        books: List[Dict[str, Any]],
        catalog_snapshot: List[Dict[str, Any]],
        agent_lang: str = "zh",
    ) -> str:
        if not books and not self.enabled:
            return self._fallback_answer(message, history, plan, books, catalog_snapshot, agent_lang=agent_lang)
        if not self.enabled:
            return self._fallback_answer(message, history, plan, books, catalog_snapshot, agent_lang=agent_lang)
        prompt = (
            "你是在线书店智能助手。"
            "这是一个 chatbot + tools 模式。"
            "你负责自然对话、情绪理解、上下文承接和用户友好回复。"
            "数据库/API 负责事实查询与购物车操作。"
            "你必须参考 planner 给出的意图。"
            "当 intent 是 general_chat 时，正常聊天，不要生硬提数据库。"
            "当 intent 是 catalog_lookup 或 catalog_recommendation 时，优先依据提供的 books 和 catalog_snapshot 回答，不得编造数据库中不存在的具体书目详情。"
            "如果 planner 认为用户需要推荐，但数据库结果较少，可以结合 catalog_snapshot 做自然推荐。"
            "如果用户情绪低落并想找书，可以给出温和、体贴、自然的推荐理由。"
            "当 intent 是 cart_help 或 cart_action 时，不要在对话里做二次确认提问；只需要简洁说明已经识别到用户的购物车意图，并提示将通过弹窗确认。不要声称已经执行成功。"
            "只有在用户明确询问书籍但提供数据无法支持时，才回答：暂无相关信息。"
            "如果 planner 给出 follow_up_question，且当前信息不足，你可以用那句或更自然的方式追问。"
            "整体语气自然、像聊天机器人，不要机械。"
            + self._lang_text(agent_lang, " 请使用中文回复。", " Please reply in English.")
        )
        return await self._chat(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "history": history,
                            "question": message,
                            "plan": plan,
                            "books": books,
                            "catalog_snapshot": catalog_snapshot,
                            "capabilities": {
                                "general_chat": True,
                                "catalog_readonly_lookup": True,
                                "cart_mutation_via_api_only": True,
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )

    def _fallback_answer(
        self,
        message: str,
        history: List[Dict[str, str]],
        plan: Dict[str, Any],
        books: List[Dict[str, Any]],
        catalog_snapshot: List[Dict[str, Any]],
        agent_lang: str = "zh",
    ) -> str:
        en_mode = self._is_en_lang(agent_lang)
        intent = str(plan.get("intent") or "general_chat")
        if self._is_identity_question(message):
            return self._lang_text(
                agent_lang,
                "我是在线书店智能助手，可以陪你聊天，也可以查书、介绍书籍信息，并按作者、题材或关键词推荐。",
                "I am the online bookstore assistant. I can chat with you, look up books, introduce titles, and recommend books by author, genre, or keywords.",
            )
        if self._is_greeting(message):
            return self._lang_text(
                agent_lang,
                "你好，我是在线书店智能助手。你可以问我书籍信息、作者、题材，或者让我直接推荐。",
                "Hi, I am the online bookstore assistant. You can ask me about books, authors, genres, or ask for recommendations directly.",
            )
        if intent == "general_chat" and any(word in (message or "").lower() for word in ["不开心", "难过", "烦", "心情", "sad", "upset", "stressed", "depressed"]):
            theme_candidates = self._theme_candidates("healing warm relaxed" if en_mode else "治愈 温暖 轻松", catalog_snapshot)
            if theme_candidates:
                picks = []
                for item in theme_candidates[:3]:
                    title = item.get("title_en") or item.get("title") if en_mode else item.get("title") or item.get("title_en")
                    if en_mode:
                        picks.append(f"{title}: {self._short_desc(item, agent_lang=agent_lang)}")
                    else:
                        picks.append(f"《{title}》：{self._short_desc(item, agent_lang=agent_lang)}")
                if en_mode:
                    return "You seem a bit down. You can start with these easier reads: " + "; ".join(picks) + "."
                return f"听起来你现在有点低落，可以先看看这些相对容易读进去的书：{'；'.join(picks)}。"
            return self._lang_text(
                agent_lang,
                "听起来你现在有点不开心。如果你愿意，我可以按治愈、轻松、科幻逃离感或思考人生这几种方向帮你推荐书。",
                "You seem a little down. If you want, I can recommend books in healing, light, escapist sci-fi, or reflective categories.",
            )
        if intent in {"cart_help", "cart_action"}:
            return self._lang_text(
                agent_lang,
                "我已经识别到你的购物车操作意图。接下来会直接弹出确认框，只有你点击确认后，才会对当前会话用户的购物车执行变更。",
                "I detected your cart operation intent. A confirmation dialog will appear, and changes are applied only after you confirm.",
            )

        books = self._dedupe_books(books)
        focus = self._infer_focus_from_history(message, history)
        theme_candidates = self._theme_candidates(focus, catalog_snapshot)

        if self._wants_recommendation(focus) and theme_candidates:
            if self._is_follow_up(message) and books:
                excluded = {self._title_key(item) for item in books}
                theme_candidates = [item for item in theme_candidates if self._title_key(item) not in excluded]

        if books:
            if len(books) == 1 and not self._wants_recommendation(message):
                top = books[0]
                if en_mode:
                    title = top.get("title_en") or top.get("title") or ""
                    author = top.get("author_en") or top.get("author") or "N/A"
                    desc = (top.get("description_en") or top.get("description") or "No description").strip()
                    return f"{title}; Author: {author}; Description: {desc}"
                title = top.get("title") or top.get("title_en") or ""
                author = top.get("author") or top.get("author_en") or "暂无"
                desc = (top.get("description") or top.get("description_en") or "暂无").strip()
                return f"《{title}》；作者：{author}；简介：{desc}"

            recommendations = []
            for item in books[:3]:
                reason = self._short_desc(item, agent_lang=agent_lang)
                title = item.get("title_en") or item.get("title") if en_mode else item.get("title") or item.get("title_en")
                if en_mode:
                    recommendations.append(f"{title}: {reason}")
                else:
                    recommendations.append(f"《{title}》：{reason}")
            return ("You can check these: " if en_mode else "可以看看：") + ("; ".join(recommendations) if en_mode else "；".join(recommendations))

        if self._wants_recommendation(focus):
            picks = []
            seen = set()
            for item in theme_candidates:
                key = self._title_key(item)
                if key in seen:
                    continue
                seen.add(key)
                title = item.get("title_en") or item.get("title") if en_mode else item.get("title") or item.get("title_en")
                reason = self._short_desc(item, agent_lang=agent_lang)
                if en_mode:
                    picks.append(f"{title}: {reason}")
                else:
                    picks.append(f"《{title}》：{reason}")
                if len(picks) >= 3:
                    break
            if picks:
                return ("You can start with: " if en_mode else "可以先看看这些：") + ("; ".join(picks) if en_mode else "；".join(picks))

        if self._is_book_related(message) and history:
            for item in reversed(history):
                content = item.get("content", "")
                if "《" in content and "》" in content:
                    return self._lang_text(
                        agent_lang,
                        "如果你想基于上一条继续找同作者或同类型书，可以直接说作者名、题材或关键词。",
                        "If you want to continue from the previous result, tell me the author, genre, or keywords and I can find similar books.",
                    )
        if not self._is_book_related(message):
            return self._lang_text(
                agent_lang,
                "我可以陪你聊天，也可以帮你查书、推荐书，或者说明如何通过接口完成购物车操作。",
                "I can chat with you, help you find books, recommend books, or explain cart operations.",
            )
        return self._lang_text(agent_lang, "暂无相关信息", "No relevant information found.")

    async def compose_cart_confirmation(self, action: str, product_title: str, quantity: int | None, option_summary: str | None, agent_lang: str = "zh") -> str:
        if not self.enabled:
            if self._is_en_lang(agent_lang):
                if action == "add":
                    return f"Confirm adding '{product_title}' to cart?"
                if action == "update":
                    return f"Confirm updating the quantity of '{product_title}' to {quantity}?"
                return f"Confirm removing '{product_title}' from cart?"
            if action == "add":
                return f"确认将《{product_title}》加入购物车吗？"
            if action == "update":
                return f"确认将《{product_title}》的数量更新为 {quantity} 吗？"
            return f"确认将《{product_title}》从购物车移除吗？"
        prompt = self._lang_text(
            agent_lang,
            "你是购物车确认助手。请生成一句简洁、礼貌、明确的中文确认语句。不要输出解释，不要换行。",
            "You are a cart confirmation assistant. Generate one concise, polite, and explicit English confirmation sentence. Do not add explanation or line breaks.",
        )
        details = {"action": action, "product_title": product_title, "quantity": quantity, "option_summary": option_summary}
        return await self._chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(details, ensure_ascii=False)},
        ])

    async def _chat(self, messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        await self.qps_gate.wait_turn()
        if not self.enabled:
            raise RuntimeError("DeepSeek API key is not configured")
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {"model": self.settings.deepseek_model, "messages": messages, "temperature": 0.2}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.settings.deepseek_timeout_seconds) as client:
            try:
                response = await client.post(self.settings.deepseek_api_url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"]).strip()
            except httpx.TimeoutException as e:
                self.logger.exception("DeepSeek request timed out")
                raise RuntimeError(f"DeepSeek request timed out after {self.settings.deepseek_timeout_seconds}s") from e
            except httpx.RequestError as e:
                self.logger.exception("DeepSeek request error")
                raise RuntimeError("DeepSeek request failed") from e
            except Exception:
                self.logger.exception("DeepSeek unknown error")
                raise
