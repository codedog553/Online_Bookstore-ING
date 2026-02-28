from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _sku_unit_price(sku: models.ProductSKU) -> float:
    base = float(sku.product.base_price)
    adj = float(sku.price_adjustment or 0)
    return base + adj


@router.get("", response_model=List[schemas.CartItemOut])
def get_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    result: List[schemas.CartItemOut] = []
    for it in items:
        unit_price = _sku_unit_price(it.sku)
        result.append(
            schemas.CartItemOut(
                id=it.id,
                sku_id=it.sku_id,
                quantity=it.quantity,
                product_title=it.sku.product.title,
                option_values=it.sku.option_values,
                unit_price=unit_price,
                subtotal=unit_price * it.quantity,
            )
        )
    return result


@router.post("/items", response_model=schemas.Msg)
def add_to_cart(payload: schemas.CartItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    sku = db.query(models.ProductSKU).filter(models.ProductSKU.id == payload.sku_id).first()
    if not sku or not sku.is_available:
        raise HTTPException(status_code=400, detail="SKU 不可用或不存在")
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于 0")
    if sku.stock_quantity is not None and payload.quantity > sku.stock_quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    existing = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.id, models.CartItem.sku_id == payload.sku_id)
        .first()
    )
    if existing:
        new_qty = existing.quantity + payload.quantity
        if sku.stock_quantity is not None and new_qty > sku.stock_quantity:
            raise HTTPException(status_code=400, detail="库存不足")
        existing.quantity = new_qty
        db.add(existing)
    else:
        item = models.CartItem(user_id=current_user.id, sku_id=payload.sku_id, quantity=payload.quantity)
        db.add(item)
    db.commit()
    return schemas.Msg(message="已加入购物车")


@router.put("/items/{item_id}", response_model=schemas.Msg)
def update_item(item_id: int, payload: schemas.CartItemUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = (
        db.query(models.CartItem)
        .filter(models.CartItem.id == item_id, models.CartItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="购物车项不存在")
    if payload.quantity <= 0:
        db.delete(item)
        db.commit()
        return schemas.Msg(message="已从购物车移除")
    if item.sku.stock_quantity is not None and payload.quantity > item.sku.stock_quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    item.quantity = payload.quantity
    db.add(item)
    db.commit()
    return schemas.Msg(message="数量已更新")


@router.delete("/items/{item_id}", response_model=schemas.Msg)
def remove_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = (
        db.query(models.CartItem)
        .filter(models.CartItem.id == item_id, models.CartItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="购物车项不存在")
    db.delete(item)
    db.commit()
    return schemas.Msg(message="已删除")
