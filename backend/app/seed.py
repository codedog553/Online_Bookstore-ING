"""
示例数据初始化脚本。

- `python -m app.seed`：完全重置数据，并重建/下载商品图片
- `python -m app.seed_no_images`：仅重置数据库业务数据，保留 uploads，不下载图片
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from . import models
from .auth import get_password_hash
from .db import SessionLocal, init_db
from .time_utils import now_cn_naive


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(ROOT_DIR, "uploads")
SEED_IMAGE_CACHE_DIR = os.path.join(ROOT_DIR, "seed_image_cache")
SEED_DATA_DIR = os.path.join(ROOT_DIR, "seed_data")
BOOKS_DATA_PATH = os.path.join(SEED_DATA_DIR, "books.json")

LOCAL_FALLBACK_COVERS = [
    os.path.normpath(os.path.join(ROOT_DIR, "..", "..", "frontend", "src", "img", "1984normal.jpg")),
    os.path.normpath(os.path.join(ROOT_DIR, "..", "..", "frontend", "src", "img", "1984good.jpg")),
]

CATEGORY_MAP = {
    "literature": "文学",
    "scifi": "科幻",
    "technology": "科技",
    "business": "商业",
    "history": "历史",
    "children": "少儿",
    "science": "科学",
}

OPTION_IMAGES_I18N = {
    "版本": {
        "平装": "Paperback",
        "精装": "Hardcover",
    }
}


@dataclass
class SeedBook:
    slug: str
    title: str
    title_en: str
    author: str
    author_en: str
    publisher: str
    publisher_en: str
    description: str
    description_en: str
    category: str
    base_price: float
    isbn: Optional[str] = None
    cover_urls: Optional[list[str]] = None


def reset_all(db: Session):
    db.query(models.ProductCommentLike).delete()
    db.query(models.ProductComment).delete()
    db.query(models.ProductRating).delete()
    db.query(models.OrderStatusEvent).delete()
    db.query(models.Review).delete()
    db.query(models.OrderItem).delete()
    db.query(models.Order).delete()
    db.query(models.CartItem).delete()
    db.query(models.ProductSKU).delete()
    db.query(models.Product).delete()
    db.query(models.Category).delete()
    db.query(models.Address).delete()
    db.query(models.User).delete()
    db.commit()


def reset_uploads():
    if not os.path.exists(UPLOADS_DIR):
        return

    for name in os.listdir(UPLOADS_DIR):
        path = os.path.join(UPLOADS_DIR, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
        except Exception:
            pass


def _load_books() -> list[SeedBook]:
    with open(BOOKS_DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    books: list[SeedBook] = []
    for item in raw:
        books.append(
            SeedBook(
                slug=str(item["slug"]),
                title=str(item["title"]),
                title_en=str(item["title_en"]),
                author=str(item["author"]),
                author_en=str(item["author_en"]),
                publisher=str(item["publisher"]),
                publisher_en=str(item["publisher_en"]),
                description=str(item["description"]),
                description_en=str(item["description_en"]),
                category=str(item["category"]),
                base_price=float(item["base_price"]),
                isbn=str(item["isbn"]).strip() if item.get("isbn") else None,
                cover_urls=[str(x) for x in item.get("cover_urls") or []],
            )
        )
    if not books:
        raise RuntimeError("seed_data/books.json 为空，无法生成真实书籍数据")
    return books


def _cover_candidates(book: SeedBook) -> list[str]:
    urls = list(book.cover_urls or [])
    if book.isbn:
        isbn = book.isbn.replace("-", "").strip()
        urls.extend(
            [
                f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false",
                f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false",
            ]
        )
    return urls


def _cache_path(book: SeedBook, index: int) -> str:
    return os.path.join(SEED_IMAGE_CACHE_DIR, f"{book.slug}_{index}.jpg")


def _download_to_cache(url: str, cache_path: str) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 Kilo Seed"})
        with urlopen(req, timeout=20) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read()
        if not data:
            return False
        if content_type and not content_type.startswith("image/"):
            return False
        with open(cache_path, "wb") as f:
            f.write(data)
        return True
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False


def _existing_fallback_covers() -> list[str]:
    paths = []
    for path in LOCAL_FALLBACK_COVERS:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            paths.append(path)
    return paths


def _ensure_book_cover_cache(book: SeedBook) -> list[str]:
    os.makedirs(SEED_IMAGE_CACHE_DIR, exist_ok=True)
    cached_paths: list[str] = []
    for idx, url in enumerate(_cover_candidates(book), start=1):
        cache_path = _cache_path(book, idx)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            cached_paths.append(cache_path)
            continue
        if _download_to_cache(url, cache_path):
            cached_paths.append(cache_path)

    if cached_paths:
        return cached_paths

    fallbacks = _existing_fallback_covers()
    if fallbacks:
        return fallbacks
    raise RuntimeError(f"未能为书籍 {book.slug} 准备真实封面")


def _get_local_book_cover_sources(book: SeedBook) -> list[str]:
    cached_paths: list[str] = []
    for idx, _url in enumerate(_cover_candidates(book), start=1):
        cache_path = _cache_path(book, idx)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            cached_paths.append(cache_path)
    if cached_paths:
        return cached_paths

    fallbacks = _existing_fallback_covers()
    if fallbacks:
        return fallbacks

    raise RuntimeError(f"本地缓存中没有书籍 {book.slug} 的可用封面，且缺少 fallback 图片")


def _copy_cover_to_sku(sku_id: int, image_path: str, idx: int) -> str:
    sku_dir = os.path.join(UPLOADS_DIR, f"sku_{sku_id}")
    os.makedirs(sku_dir, exist_ok=True)
    ext = os.path.splitext(image_path)[1].lower() or ".jpg"
    target = os.path.join(sku_dir, f"seed_{idx}{ext}")
    shutil.copyfile(image_path, target)
    return f"/uploads/sku_{sku_id}/seed_{idx}{ext}"


def _ensure_multi_images(paths: list[str], desired_count: int = 2) -> list[str]:
    if not paths:
        raise ValueError("paths cannot be empty")
    if len(paths) >= desired_count:
        return paths[:desired_count]
    result = list(paths)
    while len(result) < desired_count:
        result.append(paths[len(result) % len(paths)])
    return result


def create_users(db: Session):
    admin = models.User(
        full_name="Admin",
        email="admin@demo.com",
        password_hash=get_password_hash("Admin1234"),
        is_admin=True,
        language="zh",
    )
    user = models.User(
        full_name="Demo User",
        email="user@demo.com",
        password_hash=get_password_hash("User1234"),
        is_admin=False,
        language="zh",
    )
    db.add_all([admin, user])
    db.commit()
    db.refresh(admin)
    db.refresh(user)
    return admin, user


def create_categories(db: Session) -> dict[str, models.Category]:
    created: dict[str, models.Category] = {}
    for idx, (slug, name) in enumerate(CATEGORY_MAP.items(), start=1):
        cat = models.Category(name=name, sort_order=idx)
        db.add(cat)
        db.flush()
        created[slug] = cat
    db.commit()
    for cat in created.values():
        db.refresh(cat)
    return created


def create_product_with_skus(db: Session, book: SeedBook, category_id: int, include_images: bool = True):
    options = {
        "版本": ["平装", "精装"],
        "optionValueI18n": OPTION_IMAGES_I18N,
    }
    prod = models.Product(
        title=book.title,
        title_en=book.title_en,
        author=book.author,
        author_en=book.author_en,
        publisher=book.publisher,
        publisher_en=book.publisher_en,
        base_price=book.base_price,
        description=book.description,
        description_en=book.description_en,
        category_id=category_id,
        is_active=True,
        options=json.dumps(options, ensure_ascii=False),
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)

    sku1 = models.ProductSKU(
        product_id=prod.id,
        option_values=json.dumps({"版本": "平装"}, ensure_ascii=False),
        price_adjustment=0,
        stock_quantity=40,
        is_available=True,
    )
    sku2 = models.ProductSKU(
        product_id=prod.id,
        option_values=json.dumps({"版本": "精装"}, ensure_ascii=False),
        price_adjustment=12.0,
        stock_quantity=18,
        is_available=True,
    )
    db.add_all([sku1, sku2])
    db.commit()
    db.refresh(sku1)
    db.refresh(sku2)

    if include_images:
        cached_paths = _ensure_book_cover_cache(book)
        paperback_images = _ensure_multi_images(cached_paths, 2)
        hardcover_images = _ensure_multi_images(list(reversed(cached_paths)), 2)

        sku1.photos = json.dumps(
            [_copy_cover_to_sku(sku1.id, path, idx + 1) for idx, path in enumerate(paperback_images)],
            ensure_ascii=False,
        )
        sku2.photos = json.dumps(
            [_copy_cover_to_sku(sku2.id, path, idx + 1) for idx, path in enumerate(hardcover_images)],
            ensure_ascii=False,
        )
        db.add_all([sku1, sku2])
        db.commit()

    prices = [float(prod.base_price) + float(sku1.price_adjustment or 0), float(prod.base_price) + float(sku2.price_adjustment or 0)]
    prod.min_price = min(prices)
    prod.max_price = max(prices)
    db.add(prod)
    db.commit()
    return prod


def bind_local_images_for_product(db: Session, book: SeedBook, product: models.Product):
    sku_list = (
        db.query(models.ProductSKU)
        .filter(models.ProductSKU.product_id == product.id)
        .order_by(models.ProductSKU.id.asc())
        .all()
    )
    if len(sku_list) < 2:
        return

    cached_paths = _get_local_book_cover_sources(book)
    paperback_images = _ensure_multi_images(cached_paths, 2)
    hardcover_images = _ensure_multi_images(list(reversed(cached_paths)), 2)

    sku_list[0].photos = json.dumps(
        [_copy_cover_to_sku(sku_list[0].id, path, idx + 1) for idx, path in enumerate(paperback_images)],
        ensure_ascii=False,
    )
    sku_list[1].photos = json.dumps(
        [_copy_cover_to_sku(sku_list[1].id, path, idx + 1) for idx, path in enumerate(hardcover_images)],
        ensure_ascii=False,
    )
    db.add_all(sku_list[:2])
    db.commit()


def create_demo_order_and_review(db: Session, user: models.User, product: models.Product):
    addr = models.Address(
        user_id=user.id,
        receiver_name=user.full_name,
        phone="13800000000",
        province="上海",
        city="上海",
        district="浦东新区",
        detail_address="世纪大道 1 号",
        is_default=True,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    user.default_address_id = addr.id
    db.add(user)
    db.commit()

    sku = (
        db.query(models.ProductSKU)
        .filter(models.ProductSKU.product_id == product.id, models.ProductSKU.option_values.like("%精装%"))
        .first()
    )
    unit_price = float(product.base_price) + float(sku.price_adjustment or 0)

    created_at = now_cn_naive() - timedelta(days=1)
    shipped_at = created_at + timedelta(hours=4)
    completed_at = shipped_at + timedelta(hours=6)

    order = models.Order(
        order_id="ORDER99991231-001",
        user_id=user.id,
        address_id=addr.id,
        ship_receiver_name=addr.receiver_name,
        ship_phone=addr.phone,
        ship_province=addr.province,
        ship_city=addr.city,
        ship_district=addr.district,
        ship_detail_address=addr.detail_address,
        total_amount=unit_price,
        status="completed",
        created_at=created_at,
        shipped_at=shipped_at,
        completed_at=completed_at,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    db.add_all(
        [
            models.OrderStatusEvent(order_id=order.order_id, status="pending", created_at=created_at),
            models.OrderStatusEvent(order_id=order.order_id, status="shipped", note="seed shipped", created_at=shipped_at),
            models.OrderStatusEvent(order_id=order.order_id, status="completed", note="seed completed", created_at=completed_at),
        ]
    )
    db.commit()

    db.add(
        models.OrderItem(
            order_id=order.order_id,
            sku_id=sku.id,
            quantity=1,
            unit_price=unit_price,
            option_values=sku.option_values,
        )
    )
    db.commit()

    db.add(models.ProductRating(user_id=user.id, product_id=product.id, order_id=order.order_id, rating=5, created_at=completed_at))
    db.add(
        models.ProductComment(
            user_id=user.id,
            product_id=product.id,
            content="装帧很好，内容也很值得收藏。",
            created_at=completed_at,
            updated_at=completed_at,
        )
    )
    db.commit()


def run_seed(include_images: bool, reset_images: bool):
    init_db()
    db = SessionLocal()
    try:
        if reset_images:
            reset_uploads()
        reset_all(db)
        books = _load_books()
        _admin, user = create_users(db)
        categories = create_categories(db)

        try:
            product_count = int(os.environ.get("SEED_PRODUCT_COUNT", "24"))
        except Exception:
            product_count = 24
        product_count = max(1, product_count)

        selected_books = books[: min(product_count, len(books))]
        created_products: list[models.Product] = []
        for book in selected_books:
            category = categories.get(book.category) or categories["literature"]
            product = create_product_with_skus(db, book, category.id, include_images=include_images)
            if not include_images:
                bind_local_images_for_product(db, book, product)
            created_products.append(product)

        if created_products:
            create_demo_order_and_review(db, user, created_products[0])

        mode = "with real books and refreshed images" if include_images else "without image refresh"
        print(f"Seed completed {mode}. Admin: admin@demo.com / Admin1234, User: user@demo.com / User1234")
    finally:
        db.close()


def main():
    run_seed(include_images=True, reset_images=True)


if __name__ == "__main__":
    main()
