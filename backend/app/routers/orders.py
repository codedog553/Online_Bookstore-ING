from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _sku_unit_price(sku: models.ProductSKU) -> float:
    base = float(sku.product.base_price)
    adj = float(sku.price_adjustment or 0)
    return base + adj


def _generate_order_id(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ORDER{today}-"
    # 统计当日已有订单数量
    count = db.query(models.Order).filter(models.Order.order_id.like(prefix + "%")).count()
    seq = f"{count + 1:03d}"
    return prefix + seq


@router.get("", response_model=List[schemas.OrderOut])
def list_my_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
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


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    od = (
        db.query(models.Order)
        .filter(models.Order.order_id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    items = [
        schemas.OrderItemOut(
            sku_id=it.sku_id,
            quantity=it.quantity,
            unit_price=float(it.unit_price),
            option_values=it.option_values,
        )
        for it in od.items
    ]
    return schemas.OrderOut(
        order_id=od.order_id,
        total_amount=float(od.total_amount),
        status=od.status,
        shipped_at=od.shipped_at,
        created_at=od.created_at,
        items=items,
    )


@router.post("", response_model=schemas.OrderOut)
def create_order(payload: schemas.OrderCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 检查地址归属
    addr = (
        db.query(models.Address)
        .filter(models.Address.id == payload.address_id, models.Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(status_code=400, detail="收货地址无效")

    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="购物车为空")

    # 校验库存、计算金额
    total = 0.0
    for it in cart_items:
        if not it.sku.is_available:
            raise HTTPException(status_code=400, detail=f"SKU {it.sku_id} 不可售")
        if it.sku.stock_quantity is not None and it.quantity > it.sku.stock_quantity:
            raise HTTPException(status_code=400, detail=f"SKU {it.sku_id} 库存不足")
        total += _sku_unit_price(it.sku) * it.quantity

    order_id = _generate_order_id(db)
    order = models.Order(
        order_id=order_id,
        user_id=current_user.id,
        address_id=payload.address_id,
        total_amount=total,
        status="pending",
    )
    db.add(order)
    db.flush()  # 使 order 可引用

    for it in cart_items:
        unit_price = _sku_unit_price(it.sku)
        db.add(
            models.OrderItem(
                order_id=order.order_id,
                sku_id=it.sku_id,
                quantity=it.quantity,
                unit_price=unit_price,
                option_values=it.sku.option_values,
            )
        )
        # 扣减库存
        if it.sku.stock_quantity is not None:
            it.sku.stock_quantity = max(0, it.sku.stock_quantity - it.quantity)
            db.add(it.sku)
        db.delete(it)  # 清空购物车

    db.commit()
    db.refresh(order)

    # 返回订单详情
    items = [
        schemas.OrderItemOut(
            sku_id=it.sku_id,
            quantity=it.quantity,
            unit_price=float(it.unit_price),
            option_values=it.option_values,
        )
        for it in order.items
    ]
    return schemas.OrderOut(
        order_id=order.order_id,
        total_amount=float(order.total_amount),
        status=order.status,
        shipped_at=order.shipped_at,
        created_at=order.created_at,
        items=items,
    )


@router.post("/{order_id}/cancel", response_model=schemas.Msg)
def cancel_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    od = (
        db.query(models.Order)
        .filter(models.Order.order_id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可取消")

    # 返还库存
    for it in od.items:
        sku = it.sku
        if sku.stock_quantity is not None:
            sku.stock_quantity += it.quantity
            db.add(sku)
    od.status = "cancelled"
    db.add(od)
    db.commit()
    return schemas.Msg(message="订单已取消")
