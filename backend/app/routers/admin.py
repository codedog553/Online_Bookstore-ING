from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _update_product_price_range(db: Session, product: models.Product):
    # 根据现有 SKU 更新产品 min/max 价格
    prices = []
    for sku in product.skus:
        base = float(product.base_price)
        adj = float(sku.price_adjustment or 0)
        prices.append(base + adj)
    if prices:
        product.min_price = min(prices)
        product.max_price = max(prices)
        db.add(product)


@router.post("/products", response_model=schemas.ProductOut)
def create_product(payload: schemas.AdminProductCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    prod = models.Product(
        title=payload.title,
        author=payload.author,
        base_price=payload.base_price,
        description=payload.description,
        category_id=payload.category_id,
        is_active=payload.is_active if payload.is_active is not None else True,
        images=payload.images,
        options=payload.options,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    _update_product_price_range(db, prod)
    db.commit()
    return prod


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(product_id: int, payload: schemas.AdminProductUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    prod = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(prod, k, v)
    db.add(prod)
    _update_product_price_range(db, prod)
    db.commit()
    db.refresh(prod)
    return prod


@router.get("/products", response_model=List[schemas.ProductOut])
def list_all_products(db: Session = Depends(get_db), admin=Depends(get_current_admin), q: Optional[str] = Query(None)):
    query = db.query(models.Product)
    if q:
        like = f"%{q}%"
        query = query.filter(models.Product.title.like(like))
    return query.order_by(models.Product.created_at.desc()).all()


@router.get("/orders", response_model=List[schemas.OrderOut])
def admin_list_orders(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    orders = db.query(models.Order).order_by(models.Order.created_at.desc()).all()
    result: List[schemas.OrderOut] = []
    for od in orders:
        items = [
            schemas.OrderItemOut(
                sku_id=it.sku_id,
                quantity=it.quantity,
                unit_price=float(it.unit_price),
                option_values=it.option_values,
            )
            for it in od.items
        ]
        result.append(
            schemas.OrderOut(
                order_id=od.order_id,
                total_amount=float(od.total_amount),
                status=od.status,
                shipped_at=od.shipped_at,
                created_at=od.created_at,
                items=items,
            )
        )
    return result


@router.post("/orders/{order_id}/ship", response_model=schemas.Msg)
def mark_shipped(order_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    od = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可发货")
    od.status = "shipped"
    od.shipped_at = datetime.utcnow()
    db.add(od)
    db.commit()
    return schemas.Msg(message="已标记为已发货")


@router.delete("/reviews/{review_id}", response_model=schemas.Msg)
def delete_review(review_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    rv = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not rv:
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(rv)
    db.commit()
    return schemas.Msg(message="评论已删除")


@router.get("/reports/sales", response_model=schemas.SalesSummaryOut)
def sales_report(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # 总销售额与订单数（排除已取消）
    total_sales = (
        db.query(func.coalesce(func.sum(models.Order.total_amount), 0.0))
        .filter(models.Order.status != "cancelled")
        .scalar()
    )
    order_count = db.query(models.Order).filter(models.Order.status != "cancelled").count()

    # 畅销书：按 product 汇总销量（数量与销售额），取前 10
    rows = (
        db.query(
            models.Product.id.label("product_id"),
            models.Product.title.label("title"),
            func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("sales"),
        )
        .join(models.ProductSKU, models.ProductSKU.product_id == models.Product.id)
        .join(models.OrderItem, models.OrderItem.sku_id == models.ProductSKU.id)
        .join(models.Order, models.OrderItem.order_id == models.Order.order_id)
        .filter(models.Order.status != "cancelled")
        .group_by(models.Product.id, models.Product.title)
        .order_by(func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).desc())
        .limit(10)
        .all()
    )

    best_sellers = [
        {"product_id": r.product_id, "title": r.title, "sales": float(r.sales or 0.0)} for r in rows
    ]

    return schemas.SalesSummaryOut(
        total_sales=float(total_sales or 0.0),
        order_count=order_count,
        best_sellers=best_sellers,
    )
