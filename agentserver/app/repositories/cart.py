from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models


def add_item(db: Session, user_id: int, sku_id: int, quantity: int) -> str:
    with db.begin():
        sku = (
            db.query(models.ProductSKU)
            .options(joinedload(models.ProductSKU.product))
            .filter(models.ProductSKU.id == sku_id)
            .first()
        )
        if not sku or not sku.is_available:
            raise HTTPException(status_code=400, detail="SKU 不可用或不存在")
        if sku.stock_quantity is not None and quantity > sku.stock_quantity:
            raise HTTPException(status_code=400, detail="库存不足")

        item = db.query(models.CartItem).filter(models.CartItem.user_id == user_id, models.CartItem.sku_id == sku_id).first()
        if item:
            next_quantity = item.quantity + quantity
            if sku.stock_quantity is not None and next_quantity > sku.stock_quantity:
                raise HTTPException(status_code=400, detail="库存不足")
            item.quantity = next_quantity
            item.updated_at = datetime.utcnow()
        else:
            db.add(models.CartItem(user_id=user_id, sku_id=sku_id, quantity=quantity))
    return "已加入购物车"


def get_item(db: Session, user_id: int, item_id: int) -> Optional[models.CartItem]:
    return (
        db.query(models.CartItem)
        .options(joinedload(models.CartItem.sku).joinedload(models.ProductSKU.product))
        .filter(models.CartItem.id == item_id, models.CartItem.user_id == user_id)
        .first()
    )


def update_item(db: Session, user_id: int, item_id: int, quantity: int) -> str:
    with db.begin():
        item = get_item(db, user_id, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="购物车项不存在")
        if not item.sku.is_available:
            raise HTTPException(status_code=400, detail="SKU 不可售")
        if item.sku.stock_quantity is not None and quantity > item.sku.stock_quantity:
            raise HTTPException(status_code=400, detail="库存不足")
        item.quantity = quantity
        item.updated_at = datetime.utcnow()
    return "数量已更新"


def remove_item(db: Session, user_id: int, item_id: int) -> str:
    with db.begin():
        item = get_item(db, user_id, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="购物车项不存在")
        db.delete(item)
    return "已从购物车移除"


def list_items(db: Session, user_id: int):
    return (
        db.query(models.CartItem)
        .options(joinedload(models.CartItem.sku).joinedload(models.ProductSKU.product))
        .filter(models.CartItem.user_id == user_id)
        .order_by(models.CartItem.updated_at.desc(), models.CartItem.id.desc())
        .all()
    )


def find_items_by_title(db: Session, user_id: int, title_keyword: str):
    keyword = (title_keyword or "").strip()
    if not keyword:
        return []
    return (
        db.query(models.CartItem)
        .options(joinedload(models.CartItem.sku).joinedload(models.ProductSKU.product))
        .filter(models.CartItem.user_id == user_id)
        .all()
    )
