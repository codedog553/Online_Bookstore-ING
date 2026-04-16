from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from .. import models


STOPWORDS = {
    "你好", "请", "想要", "我想要", "我想", "给我", "推荐", "介绍", "一下", "一本", "这本", "那本", "有没有",
    "的", "书", "小说", "作品", "帮我", "看看", "找", "查", "查找", "有关", "关于", "什么", "哪些",
    "相关", "方面", "类型", "题材", "一本书", "本书", "学习", "希望", "想学",
    "please", "recommend", "show", "find", "book", "books", "novel", "novels", "about", "related", "suggest", "want", "looking", "for", "me", "tell", "give", "any", "some",
}

THEME_ALIASES = {
    "反乌托邦": ["反乌托邦", "极权", "监视", "控制", "压迫", "预言", "社会", "真实", "思想"],
    "dystopian": ["反乌托邦", "dystopian", "totalitarian", "surveillance", "oppression", "control"],
    "科幻": ["科幻", "未来", "宇宙", "文明", "科技", "太空"],
    "science fiction": ["科幻", "science fiction", "sci-fi", "future", "space", "civilization", "technology"],
    "推理": ["推理", "侦探", "悬疑", "案件", "谜团"],
    "mystery": ["推理", "侦探", "悬疑", "案件", "谜团", "mystery", "detective", "suspense", "crime"],
    "爱情": ["爱情", "恋爱", "情感", "婚姻"],
    "romance": ["爱情", "恋爱", "情感", "婚姻", "romance", "love", "relationship"],
    "历史": ["历史", "帝国", "战争", "王朝", "年代"],
    "history": ["历史", "帝国", "战争", "王朝", "年代", "history", "empire", "war", "dynasty"],
    "计算机": ["计算机", "编程", "程序", "开发", "算法", "软件", "代码", "python", "java", "数据库", "网络"],
    "computer": ["计算机", "编程", "程序", "开发", "算法", "软件", "代码", "python", "java", "数据库", "网络", "computer", "programming", "development", "algorithm", "software", "code"],
    "python": ["python", "爬虫", "数据分析", "机器学习", "深度学习", "keras"],
    "编程": ["编程", "程序", "开发", "代码", "算法", "python", "java", "入门", "实践"],
    "programming": ["编程", "程序", "开发", "代码", "算法", "python", "java", "入门", "实践", "programming", "developer", "coding"],
}

FOLLOW_UP_OTHER = {"其他", "别的", "别本", "换一本", "还有吗", "除此之外", "除了", "不要这本"}
FOLLOW_UP_REFER = {"其他", "别的", "还有", "再来", "换一本", "类似", "同类", "这本", "那本", "除此之外", "除了"}

FOLLOW_UP_OTHER.update({"other", "another", "anything else", "different one", "not this one"})
FOLLOW_UP_REFER.update({"other", "another", "more", "similar", "like this", "besides", "apart from"})


def _safe_json_dict(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _normalize_text(text: Optional[str]) -> str:
    value = (text or "").lower()
    value = re.sub(r"[\s\W_]+", " ", value, flags=re.UNICODE)
    return value.strip()


def _extract_query_terms(query: str) -> List[str]:
    raw = (query or "").replace("*", " ").replace("`", " ").strip()
    if not raw:
        return []
    candidates = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{1,12}", raw)
    terms: List[str] = []
    for token in candidates:
        token = token.strip().lower()
        if not token or token in STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        terms.append(token)
    for alias, expansions in THEME_ALIASES.items():
        if alias in raw:
            terms.extend(expansions)
    return list(dict.fromkeys(terms))


def _flatten_history_terms(history: Optional[List[Dict[str, str]]]) -> List[str]:
    if not history:
        return []
    text_parts: List[str] = []
    for item in history[-6:]:
        role = item.get("role")
        if role == "user":
            text_parts.append(item.get("content", ""))
    merged = " ".join(text_parts)
    return _extract_query_terms(merged)


def _is_follow_up_query(query: str) -> bool:
    lowered = (query or "").lower()
    return any(word in lowered for word in FOLLOW_UP_REFER)


def _has_explicit_topic(query: str) -> bool:
    terms = _extract_query_terms(query)
    if not terms:
        return False
    return len(terms) >= 1


def _extract_titles(text: str) -> List[str]:
    return re.findall(r"《([^》]+)》", text or "")


def _history_excluded_titles(query: str, history: Optional[List[Dict[str, str]]]) -> List[str]:
    if not history:
        return []
    lowered = (query or "").lower()
    if not any(word in lowered for word in FOLLOW_UP_OTHER):
        return []
    excluded: List[str] = []
    for item in reversed(history[-4:]):
        if item.get("role") == "assistant":
            excluded.extend(_extract_titles(item.get("content", "")))
            if excluded:
                break
    return excluded


def _score_product(product: models.Product, terms: List[str]) -> int:
    haystack = " | ".join(
        [
            _normalize_text(product.title),
            _normalize_text(product.title_en),
            _normalize_text(product.author),
            _normalize_text(product.author_en),
            _normalize_text(product.publisher),
            _normalize_text(product.publisher_en),
            _normalize_text(product.description),
            _normalize_text(product.description_en),
        ]
    )
    score = 0
    for term in terms:
        normalized = _normalize_text(term)
        if not normalized:
            continue
        if normalized in _normalize_text(product.title) or normalized in _normalize_text(product.title_en):
            score += 12
        if normalized in _normalize_text(product.author) or normalized in _normalize_text(product.author_en):
            score += 10
        if normalized in _normalize_text(product.publisher) or normalized in _normalize_text(product.publisher_en):
            score += 6
        if normalized in haystack:
            score += 4
    if terms and any(term.isdigit() for term in terms):
        title_blob = f"{product.title or ''} {product.title_en or ''}"
        if any(term in title_blob for term in terms if term.isdigit()):
            score += 10
    return score


def search_books(db: Session, query: str, history: Optional[List[Dict[str, str]]] = None, limit: int = 5) -> List[Dict[str, Any]]:
    query_terms = _extract_query_terms(query)
    history_terms = _flatten_history_terms(history) if (_is_follow_up_query(query) or not _has_explicit_topic(query)) else []
    terms = list(dict.fromkeys(query_terms + history_terms[:4]))
    excluded_titles = set(_history_excluded_titles(query, history))
    if not terms:
        return []

    rows = (
        db.query(models.Product)
        .options(joinedload(models.Product.skus))
        .filter(models.Product.is_active == True)  # noqa: E712
        .all()
    )

    ranked = sorted(
        rows,
        key=lambda row: (_score_product(row, terms), row.created_at or 0),
        reverse=True,
    )
    ranked = [
        row
        for row in ranked
        if _score_product(row, terms) > 0 and row.title not in excluded_titles and (row.title_en or "") not in excluded_titles
    ][:limit]

    result: List[Dict[str, Any]] = []
    for row in ranked:
        result.append(
            {
                "product_id": row.id,
                "title": row.title,
                "title_en": row.title_en,
                "author": row.author,
                "author_en": row.author_en,
                "publisher": row.publisher,
                "publisher_en": row.publisher_en,
                "description": row.description,
                "description_en": row.description_en,
                "sku_ids": [sku.id for sku in row.skus],
                "skus": [
                    {
                        "sku_id": sku.id,
                        "option_values": sku.option_values,
                        "stock_quantity": sku.stock_quantity,
                        "is_available": sku.is_available,
                    }
                    for sku in row.skus
                ],
                "options": _safe_json_dict(row.options),
                "match_terms": terms,
            }
        )
    return result


def resolve_books_from_message(db: Session, message: str, limit: int = 5) -> List[Dict[str, Any]]:
    raw = (message or "").strip().lower()
    if not raw:
        return []

    rows = (
        db.query(models.Product)
        .options(joinedload(models.Product.skus))
        .filter(models.Product.is_active == True)  # noqa: E712
        .all()
    )

    matched: List[models.Product] = []
    for row in rows:
        title = (row.title or "").lower()
        title_en = (row.title_en or "").lower()
        author = (row.author or "").lower()
        author_en = (row.author_en or "").lower()
        if (title and title in raw) or (title_en and title_en in raw) or (author and author in raw) or (author_en and author_en in raw):
            matched.append(row)

    result: List[Dict[str, Any]] = []
    for row in matched[:limit]:
        result.append(
            {
                "product_id": row.id,
                "title": row.title,
                "title_en": row.title_en,
                "author": row.author,
                "author_en": row.author_en,
                "publisher": row.publisher,
                "publisher_en": row.publisher_en,
                "description": row.description,
                "description_en": row.description_en,
                "sku_ids": [sku.id for sku in row.skus],
                "skus": [
                    {
                        "sku_id": sku.id,
                        "option_values": sku.option_values,
                        "stock_quantity": sku.stock_quantity,
                        "is_available": sku.is_available,
                    }
                    for sku in row.skus
                ],
                "options": _safe_json_dict(row.options),
                "match_terms": [row.title],
            }
        )
    return result


def list_catalog(db: Session, limit: int = 12) -> List[Dict[str, Any]]:
    rows = (
        db.query(models.Product)
        .options(joinedload(models.Product.skus))
        .filter(models.Product.is_active == True)  # noqa: E712
        .order_by(models.Product.created_at.desc())
        .limit(limit)
        .all()
    )
    result: List[Dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "product_id": row.id,
                "title": row.title,
                "title_en": row.title_en,
                "author": row.author,
                "author_en": row.author_en,
                "publisher": row.publisher,
                "publisher_en": row.publisher_en,
                "description": row.description,
                "description_en": row.description_en,
                "sku_ids": [sku.id for sku in row.skus],
                "options": _safe_json_dict(row.options),
            }
        )
    return result


def get_sku_preview(db: Session, sku_id: int) -> Optional[Dict[str, Any]]:
    sku = (
        db.query(models.ProductSKU)
        .options(joinedload(models.ProductSKU.product))
        .filter(models.ProductSKU.id == sku_id)
        .first()
    )
    if not sku:
        return None
    return {
        "sku_id": sku.id,
        "product_title": sku.product.title,
        "option_summary": sku.option_values,
        "is_available": sku.is_available,
        "stock_quantity": sku.stock_quantity,
    }
