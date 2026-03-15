from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/products", tags=["products"])


def _first_image_from_json_list(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        import json

        arr = json.loads(s)
        if isinstance(arr, list) and arr:
            v = str(arr[0] or "").strip()
            return v or None
    except Exception:
        return None
    return None


def _compute_thumbnail_url(prod: models.Product) -> Optional[str]:
    """A3/A16: 为商品列表计算缩略图。

    统一走 SKU 本地上传（P0）：
    - 不再读取/依赖 Product.images
    - 缩略图取“任意 SKU 的第一张 photos”
    """

    # any sku photos
    for sku in getattr(prod, "skus", []) or []:
        v2 = _first_image_from_json_list(getattr(sku, "photos", None))
        if v2:
            return v2
    return None


@router.get("", response_model=schemas.PagedProductsOut)
def list_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: Optional[int] = None,
    keyword: Optional[str] = None,
):
    q = db.query(models.Product).filter(models.Product.is_active == True)  # noqa: E712
    if category:
        q = q.filter(models.Product.category_id == category)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(models.Product.title.like(like), models.Product.title_en.like(like)))

    total = q.with_entities(func.count(models.Product.id)).scalar() or 0
    items = q.order_by(models.Product.created_at.desc()).offset((page - 1) * size).limit(size).all()

    # A3/A16: 动态补齐 thumbnail_url（response_model 需要）
    for p in items:
        try:
            setattr(p, "thumbnail_url", _compute_thumbnail_url(p))
        except Exception:
            pass
    return schemas.PagedProductsOut(items=items, total=int(total), page=page, size=size)


@router.get("/{product_id}", response_model=schemas.ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()  # noqa: E712
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    try:
        setattr(product, "thumbnail_url", _compute_thumbnail_url(product))
    except Exception:
        pass
    # 关系字段 skus 将自动随模型返回（pydantic from_attributes）
    return product


@router.get("/{product_id}/photos")
def list_product_photos(product_id: int, db: Session = Depends(get_db)):
    """返回某商品下所有 SKU 的图片（B1/D2）。

    前端用于在商品详情页展示“选项值对应图片”。

    返回结构：
    {
      "product_id": 1,
      "by_sku": { "12": ["/uploads/..."], ... },
      "option_images": { "版本": { "精装": "/uploads/..." } }
    }

    其中 option_images：只做一个弱约定：对每个 SKU 的 option_values，取第一个 key/value，映射到该 SKU 的第一张图。
    """

    import json

    prod = db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()  # noqa: E712
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    by_sku: dict[str, list[str]] = {}
    option_images: dict[str, dict[str, str]] = {}
    for sku in prod.skus:
        photos: list[str] = []
        if sku.photos:
            try:
                v = json.loads(sku.photos)
                if isinstance(v, list):
                    photos = [str(x) for x in v]
            except Exception:
                photos = []
        by_sku[str(sku.id)] = photos

        if photos:
            try:
                ov = json.loads(sku.option_values or "{}")
                if isinstance(ov, dict) and ov:
                    k = next(iter(ov.keys()))
                    val = str(ov.get(k))
                    option_images.setdefault(k, {})[val] = photos[0]
            except Exception:
                pass

    return {"product_id": prod.id, "by_sku": by_sku, "option_images": option_images}


@router.get("/search", response_model=List[schemas.ProductOut])
def search_products(q: str, db: Session = Depends(get_db)):
    like = f"%{q}%"
    items = (
        db.query(models.Product)
        .filter(models.Product.is_active == True)  # noqa: E712
        .filter(or_(models.Product.title.like(like), models.Product.title_en.like(like)))
        .order_by(models.Product.created_at.desc())
        .all()
    )

    for p in items:
        try:
            setattr(p, "thumbnail_url", _compute_thumbnail_url(p))
        except Exception:
            pass
    return items
