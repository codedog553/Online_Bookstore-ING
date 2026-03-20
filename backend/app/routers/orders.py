from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])

# =========================
# Requirements Traceability
# =========================
# A2: After login, customers can manage orders; orders are persisted server-side.
# A11: Checkout creates a purchase order and clears the cart.
# A12: Customers can list their purchase orders (reverse chronological).
# A13: Order detail includes shipping address snapshot + line items (unit price/subtotal) + status.
# B2: Order workflow status (pending/shipped/cancelled/completed) + allowed transitions.
# B3: Filter order list by current (latest) status.
# B4: Status timeline (OrderStatusEvent) keeps timestamps for changes.
# D3: Different SKU configurations are separate line items.
# D5: Validate SKU availability/stock again at checkout.


def _sku_unit_price(sku: models.ProductSKU) -> float:
    # A11/A13：订单项单价在下单瞬间固定为“商品基础价 + SKU 加价”。
    base = float(sku.product.base_price)
    adj = float(sku.price_adjustment or 0)
    return base + adj


def _append_status_event(db: Session, order_id: str, status: str, note: Optional[str] = None) -> None:
    """追加订单状态事件（B4）。

    B4：系统以时间线形式记录状态名与开始时间点。
    """

    db.add(models.OrderStatusEvent(order_id=order_id, status=status, note=note))


def _restore_inventory_for_order(db: Session, od: models.Order) -> None:
    """取消订单时返还库存。"""

    for it in od.items:
        sku = it.sku
        if sku.stock_quantity is not None:
            sku.stock_quantity += it.quantity
            db.add(sku)


def _auto_cancel_expired_orders(db: Session) -> int:
    """将超过 3 天仍为 pending 的订单自动取消（B2）。

    设计说明：课程项目不引入后台 scheduler，这里采用“访问接口时触发扫描”。
    """

    expired_before = datetime.utcnow() - timedelta(days=3)
    expired_orders = (
        db.query(models.Order)
        .filter(models.Order.status == "pending")
        .filter(models.Order.created_at <= expired_before)
        .all()
    )
    if not expired_orders:
        return 0

    for od in expired_orders:
        _restore_inventory_for_order(db, od)
        od.status = "cancelled"
        od.cancelled_at = datetime.utcnow()
        db.add(od)
        _append_status_event(db, od.order_id, "cancelled", note="auto-cancel: vendor not shipped within 3 days")

    db.commit()
    return len(expired_orders)


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


def _generate_order_id(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ORDER{today}-"
    # 统计当日已有订单数量
    count = db.query(models.Order).filter(models.Order.order_id.like(prefix + "%")).count()
    seq = f"{count + 1:03d}"
    return prefix + seq


@router.get("", response_model=List[schemas.OrderOut])
def list_my_orders(
    status: Optional[str] = Query(
        None,
        description="可选：按状态过滤（pending/shipped/cancelled/completed）",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # A12：订单列表按购买时间倒序展示（created_at desc）。
    # B3：订单列表可按 status 过滤；过滤依据为 orders.status（即订单“当前/最后状态”）。
    _auto_cancel_expired_orders(db)
    q = db.query(models.Order).filter(models.Order.user_id == current_user.id)
    if status:
        q = q.filter(models.Order.status == status)
    orders = q.order_by(models.Order.created_at.desc()).all()
    result: List[schemas.OrderOut] = []
    for od in orders:
        items = [
            schemas.OrderItemOut(
                sku_id=it.sku_id,
                quantity=it.quantity,
                unit_price=float(it.unit_price),
                option_values=it.option_values,
                product_id=it.sku.product_id,
                product_title=it.sku.product.title,
                product_options=it.sku.product.options,
                product_title_en=it.sku.product.title_en,
                subtotal=float(it.unit_price) * it.quantity,
            )
            for it in od.items
        ]
        result.append(
            schemas.OrderOut(
                order_id=od.order_id,
                total_amount=float(od.total_amount),
                status=od.status,
                shipped_at=od.shipped_at,
                completed_at=od.completed_at,
                cancelled_at=od.cancelled_at,
                created_at=od.created_at,
                items=items,
            )
        )
    return result


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # A13：订单详情返回地址快照（ship_* 字段）、行项目快照（unit_price/option_values），
    #      以保证历史订单展示不受后续地址或商品配置变更影响。
    # B4：同时返回状态时间线（OrderStatusEvent），用于前端 timeline 展示。
    _auto_cancel_expired_orders(db)
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
            product_id=it.sku.product_id,
            product_title=it.sku.product.title,
            product_title_en=it.sku.product.title_en,
            product_options=it.sku.product.options,
            subtotal=float(it.unit_price) * it.quantity,
        )
        for it in od.items
    ]
    return schemas.OrderOut(
        order_id=od.order_id,
        total_amount=float(od.total_amount),
        status=od.status,
        shipped_at=od.shipped_at,
        completed_at=od.completed_at,
        cancelled_at=od.cancelled_at,
        created_at=od.created_at,
        items=items,
        shipping_address=(
            schemas.ShippingAddressSnapshotOut(
                receiver_name=od.ship_receiver_name or od.address.receiver_name,
                phone=od.ship_phone or od.address.phone,
                province=od.ship_province or od.address.province,
                city=od.ship_city or od.address.city,
                district=od.ship_district or od.address.district,
                detail_address=od.ship_detail_address or od.address.detail_address,
            )
            if od.address
            else None
        ),
        status_timeline=[
            schemas.OrderStatusEventOut.model_validate(ev)
            for ev in sorted(od.status_events, key=lambda e: e.created_at)
        ],
    )


@router.post("", response_model=schemas.OrderOut)
def create_order(payload: schemas.OrderCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # A11：结算会创建订单，并在成功后清空购物车。
    # A1：若本次提交了新地址，则把它覆盖保存为用户的 last address（default_address_id），用于下次自动预填。
    # D5：下单前再次校验 SKU 是否可售、库存是否充足。
    _auto_cancel_expired_orders(db)
    # 兼容两种下单方式：
    # 1) 旧版：前端提交 address_id（从地址簿选择）
    # 2) 新版：前端提交 address（下单时填写/预填的地址对象，仅保存“上一次地址”）
    if payload.address_id:
        # A1：兼容旧版“地址簿选择”，仍把选中地址当作 last address。
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
        # A1：新版“结算页填写地址”——只记忆上一次地址，不维护可选地址列表。
        # 下单时填写地址，并保存为“上一次地址”供下次预填。
        # payload.address 在 schemas 中已通过 model_validator 做了非空校验
        addr = _upsert_last_address(db, current_user, payload.address)  # type: ignore[arg-type]

    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="购物车为空")

    # A8/A11/D5：校验库存并计算订单总金额。
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
        # A13：地址快照（ship_*）：下单瞬间复制，用于历史订单展示。
        ship_receiver_name=addr.receiver_name,
        ship_phone=addr.phone,
        ship_province=addr.province,
        ship_city=addr.city,
        ship_district=addr.district,
        ship_detail_address=addr.detail_address,
        total_amount=total,
        status="pending",
    )
    db.add(order)
    db.flush()  # 使 order 可引用

    # B2：订单创建时的初始状态为 pending。
    # B4：并同步记录时间线起点（pending event）。
    _append_status_event(db, order.order_id, "pending")

    for it in cart_items:
        unit_price = _sku_unit_price(it.sku)
        db.add(
            models.OrderItem(
                order_id=order.order_id,
                sku_id=it.sku_id,
                quantity=it.quantity,
                unit_price=unit_price,
                # D3/A13：订单项保留配置快照，支持同一本书多个版本同时购买，
                # 且历史订单不受后续 SKU 文案或配置结构调整影响。
                option_values=it.sku.option_values,
            )
        )
        # D5：扣减库存（SKU 维度）。
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
            product_id=it.sku.product_id,
            product_title=it.sku.product.title,
            product_title_en=it.sku.product.title_en,
            product_options=it.sku.product.options,
            subtotal=float(it.unit_price) * it.quantity,
        )
        for it in order.items
    ]
    return schemas.OrderOut(
        order_id=order.order_id,
        total_amount=float(order.total_amount),
        status=order.status,
        shipped_at=order.shipped_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at,
        items=items,
        shipping_address=schemas.ShippingAddressSnapshotOut(
            receiver_name=order.ship_receiver_name or addr.receiver_name,
            phone=order.ship_phone or addr.phone,
            province=order.ship_province or addr.province,
            city=order.ship_city or addr.city,
            district=order.ship_district or addr.district,
            detail_address=order.ship_detail_address or addr.detail_address,
        ),
        status_timeline=[
            schemas.OrderStatusEventOut.model_validate(ev)
            for ev in sorted(order.status_events, key=lambda e: e.created_at)
        ],
    )


@router.post("/{order_id}/cancel", response_model=schemas.Msg)
def cancel_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # B2：客户仅可取消 pending 订单；取消后返还库存，并写入 cancelled 时间线事件。
    _auto_cancel_expired_orders(db)
    od = (
        db.query(models.Order)
        .filter(models.Order.order_id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可取消")

    _restore_inventory_for_order(db, od)
    od.status = "cancelled"
    od.cancelled_at = datetime.utcnow()
    db.add(od)
    _append_status_event(db, od.order_id, "cancelled", note="cancelled by customer")
    db.commit()
    return schemas.Msg(message="订单已取消")


@router.post("/{order_id}/complete", response_model=schemas.Msg)
def complete_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """用户确认收货（B2）：shipped -> completed。"""

    _auto_cancel_expired_orders(db)
    od = (
        db.query(models.Order)
        .filter(models.Order.order_id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "shipped":
        raise HTTPException(status_code=400, detail="仅已发货订单可确认收货")

    od.status = "completed"
    od.completed_at = datetime.utcnow()
    db.add(od)
    _append_status_event(db, od.order_id, "completed", note="confirmed by customer")
    db.commit()
    return schemas.Msg(message="已确认收货")
