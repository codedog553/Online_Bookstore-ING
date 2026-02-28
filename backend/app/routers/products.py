from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=List[schemas.ProductOut])
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
        q = q.filter(models.Product.title.like(like))
    items = q.order_by(models.Product.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return items


@router.get("/{product_id}", response_model=schemas.ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()  # noqa: E712
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    # 关系字段 skus 将自动随模型返回（pydantic from_attributes）
    return product


@router.get("/search", response_model=List[schemas.ProductOut])
def search_products(q: str, db: Session = Depends(get_db)):
    like = f"%{q}%"
    items = (
        db.query(models.Product)
        .filter(models.Product.is_active == True)  # noqa: E712
        .filter(models.Product.title.like(like))
        .order_by(models.Product.created_at.desc())
        .all()
    )
    return items
