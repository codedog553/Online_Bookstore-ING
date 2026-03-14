from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _upsert_last_address(
    db: Session,
    current_user: models.User,
    address_in: schemas.OrderCreate.ShippingAddressIn,
) -> models.Address:
    """将下单填写的地址保存为“上一次地址”(last address)。

    设计说明（按产品要求）：
    - 用户在结算/下单时填写地址，不维护可选地址列表。
    - 系统仅保存用户上一次输入的地址，用于下次结算预填。

    实现策略：
    - 优先使用 users.default_address_id 指向的地址作为 last address。
    - 若不存在，则取该用户最新的一条地址。
    - 若仍不存在，则创建新地址。
    - 最终将该地址设置为用户的 default_address_id（用于预填）。
    """

    addr: Optional[models.Address] = None
    if current_user.default_address_id:
        addr = (
            db.query(models.Address)
            .filter(
                models.Address.id == current_user.default_address_id,
                models.Address.user_id == current_user.id,
            )
            .first()
        )

    if not addr:
        addr = (
            db.query(models.Address)
            .filter(models.Address.user_id == current_user.id)
            .order_by(models.Address.created_at.desc())
            .first()
        )

    if addr:
        addr.receiver_name = address_in.receiver_name
        addr.phone = address_in.phone
        addr.province = address_in.province
        addr.city = address_in.city
        addr.district = address_in.district
        addr.detail_address = address_in.detail_address
        addr.is_default = True
        db.add(addr)
        db.flush()
    else:
        addr = models.Address(
            user_id=current_user.id,
            receiver_name=address_in.receiver_name,
            phone=address_in.phone,
            province=address_in.province,
            city=address_in.city,
            district=address_in.district,
            detail_address=address_in.detail_address,
            is_default=True,
        )
        db.add(addr)
        db.flush()  # 获取 addr.id

    # 取消其他默认（虽然我们不维护地址列表，但保留旧数据时避免出现多个 default）
    db.query(models.Address).filter(
        models.Address.user_id == current_user.id,
        models.Address.id != addr.id,
    ).update({models.Address.is_default: False})

    current_user.default_address_id = addr.id
    db.add(current_user)
    db.flush()
    return addr


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
    # 兼容两种下单方式：
    # 1) 旧版：前端提交 address_id（从地址簿选择）
    # 2) 新版：前端提交 address（下单时填写/预填的地址对象，仅保存“上一次地址”）
    if payload.address_id:
        addr = (
            db.query(models.Address)
            .filter(
                models.Address.id == payload.address_id,
                models.Address.user_id == current_user.id,
            )
            .first()
        )
        if not addr:
            raise HTTPException(status_code=400, detail="地址无效")
        # 选中的地址视为“上一次地址”（便于下次预填）
        current_user.default_address_id = addr.id
        db.add(current_user)
        db.flush()
    else:
        # 下单时填写地址，并保存为“上一次地址”供下次预填。
        # payload.address 在 schemas 中已通过 model_validator 做了非空校验
        addr = _upsert_last_address(db, current_user, payload.address)  # type: ignore[arg-type]

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
        address_id=addr.id,
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
