from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/products", tags=["reviews"])


@router.get("/{product_id}/reviews", response_model=List[schemas.ReviewOut])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    items = (
        db.query(models.Review)
        .filter(models.Review.product_id == product_id, models.Review.is_visible == True)  # noqa: E712
        .order_by(models.Review.created_at.desc())
        .all()
    )
    return items


@router.post("/{product_id}/reviews", response_model=schemas.ReviewOut)
def create_review(product_id: int, payload: schemas.ReviewCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 验证评分范围
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="评分需在 1-5 之间")

    # 检查是否购买过该商品（任意订单包含该商品 SKU 即可，且订单未取消）
    # 通过订单项 -> SKU -> Product 关联判断
    order_item = (
        db.query(models.OrderItem)
        .join(models.Order, models.OrderItem.order_id == models.Order.order_id)
        .join(models.ProductSKU, models.OrderItem.sku_id == models.ProductSKU.id)
        .filter(
            models.Order.user_id == current_user.id,
            models.Order.status != "cancelled",
            models.ProductSKU.product_id == product_id,
        )
        .order_by(models.Order.created_at.desc())
        .first()
    )
    if not order_item:
        raise HTTPException(status_code=400, detail="仅限已购买用户评论")

    # 简单规则：同一用户对同一订单+商品仅限一条评论
    existed = (
        db.query(models.Review)
        .filter(
            models.Review.user_id == current_user.id,
            models.Review.product_id == product_id,
            models.Review.order_id == order_item.order_id,
        )
        .first()
    )
    if existed:
        raise HTTPException(status_code=400, detail="该订单下已评论过该商品")

    rv = models.Review(
        user_id=current_user.id,
        product_id=product_id,
        order_id=order_item.order_id,
        rating=payload.rating,
        comment=payload.comment,
        is_visible=True,
    )
    db.add(rv)
    db.commit()
    db.refresh(rv)
    return rv
