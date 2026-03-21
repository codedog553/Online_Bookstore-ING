from __future__ import annotations

from datetime import date, datetime, timedelta
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, String

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_admin
from ..time_utils import now_cn_naive

router = APIRouter(prefix="/api/admin", tags=["admin"])

# =========================
# Requirements Traceability
# =========================
# A14: Vendor can browse/search products.
# A15: Vendor can search by product ID substring (system-generated unique product ID).
# A16: Vendor can add new products; photos uploaded locally (per SKU) and multiple allowed.
# A17: Vendor can edit product detail information.
# A18: Vendor can disable/enable products (is_active) to hide from customers.
# A19: Vendor can list purchase orders (newest first) incl. PO number/date/customer/amount/status.
# A20: Vendor can view purchase order detail and line items.
# B1: Multi-photos per SKU; admin portal can add/remove photos.
# B2/B4: Vendor triggers order status changes (ship/cancel) and timeline is recorded.
# D1/D4: Configurable products + SKU separation + inventory (stock_quantity/is_available).
# D5: Unavailable/out-of-stock SKUs should not be purchasable (enforced in cart/order routes; admin sets inventory here).
# W2: Vendor must input bilingual product information at creation/update.


def _uploads_dir() -> str:
    """后端 uploads 根目录（与 main.py 中保持一致）。"""

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")


def _ensure_sku_dir(sku_id: int) -> str:
    base = os.path.abspath(_uploads_dir())
    d = os.path.join(base, f"sku_{sku_id}")
    os.makedirs(d, exist_ok=True)
    return d


def _load_json_list(s: Optional[str]) -> List[str]:
    if not s:
        return []
    try:
        import json

        v = json.loads(s)
        return [str(x) for x in v] if isinstance(v, list) else []
    except Exception:
        return []


def _dump_json_list(v: List[str]) -> str:
    import json

    return json.dumps(v, ensure_ascii=False)


def _append_status_event(db: Session, order_id: str, status: str, note: Optional[str] = None) -> None:
    """追加订单状态事件（B4）。"""

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

    说明：课程项目不引入后台 scheduler，这里采用“访问接口时触发扫描”。
    """

    # B2：自动取消以中国大陆时间（UTC+8）为基准判断。
    expired_before = now_cn_naive() - timedelta(days=3)
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
        od.cancelled_at = now_cn_naive()
        db.add(od)
        _append_status_event(db, od.order_id, "cancelled", note="auto-cancel: vendor not shipped within 3 days")

    db.commit()
    return len(expired_orders)


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


@router.get("/products/{product_id}/skus", response_model=List[schemas.SKUOut])
def list_product_skus(product_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    prod = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")
    return prod.skus


@router.post("/products/{product_id}/skus", response_model=schemas.SKUOut)
def create_product_sku(product_id: int, payload: schemas.AdminSKUCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    prod = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在")
    sku = models.ProductSKU(
        product_id=product_id,
        option_values=payload.option_values,
        price_adjustment=payload.price_adjustment,
        stock_quantity=payload.stock_quantity,
        is_available=payload.is_available,
    )
    db.add(sku)
    db.flush()
    # 刷新产品价格区间
    db.refresh(prod)
    _update_product_price_range(db, prod)
    db.commit()
    db.refresh(sku)
    return sku


@router.put("/skus/{sku_id}", response_model=schemas.SKUOut)
def update_sku(sku_id: int, payload: schemas.AdminSKUUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    sku = db.query(models.ProductSKU).filter(models.ProductSKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(sku, k, v)
    db.add(sku)
    # 刷新对应产品价格区间
    prod = db.query(models.Product).filter(models.Product.id == sku.product_id).first()
    if prod:
        _update_product_price_range(db, prod)
    db.commit()
    db.refresh(sku)
    return sku


@router.delete("/skus/{sku_id}", response_model=schemas.Msg)
def delete_sku(sku_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    sku = db.query(models.ProductSKU).filter(models.ProductSKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    product_id = sku.product_id
    db.delete(sku)
    # 刷新对应产品价格区间
    prod = db.query(models.Product).filter(models.Product.id == product_id).first()
    if prod:
        _update_product_price_range(db, prod)
    db.commit()
    return schemas.Msg(message="SKU 已删除")


@router.post("/skus/{sku_id}/photos", response_model=schemas.SKUOut)
def upload_sku_photos(
    sku_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """SKU 多图上传（B1/A16）。

    - 使用本地文件上传保存到 backend/app/uploads/sku_{id}/
    - sku.photos 存储 JSON string list，元素为可直接访问的静态路径（/uploads/...）
    """

    # B1/A16：这里实现“每个 SKU 可上传多张图片”的核心能力。
    #           图片保存在 backend/app/uploads/sku_{id}/ 下，并通过 FastAPI StaticFiles 暴露为 /uploads/...（见 main.py）。

    sku = db.query(models.ProductSKU).filter(models.ProductSKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")

    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")

    sku_dir = _ensure_sku_dir(sku_id)
    existing = _load_json_list(sku.photos)

    for f in files:
        # 尽量保留扩展名，避免浏览器无法识别
        ext = os.path.splitext(f.filename or "")[-1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型：{ext}")

        filename = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(sku_dir, filename)
        with open(path, "wb") as out:
            out.write(f.file.read())
        existing.append(f"/uploads/sku_{sku_id}/{filename}")

    sku.photos = _dump_json_list(existing)
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


@router.delete("/skus/{sku_id}/photos", response_model=schemas.SKUOut)
def delete_sku_photo(
    sku_id: int,
    path: str = Query(..., description="要删除的图片路径（/uploads/...）"),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """删除 SKU 图片：从 sku.photos JSON 中移除，并删除本地文件。"""

    sku = db.query(models.ProductSKU).filter(models.ProductSKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")

    photos = _load_json_list(sku.photos)
    if path not in photos:
        raise HTTPException(status_code=404, detail="图片不存在")

    photos = [p for p in photos if p != path]

    # 尝试删除本地文件：将 /uploads/... 映射到 uploads 目录
    try:
        rel = path.lstrip("/")
        if rel.startswith("uploads/"):
            rel = rel[len("uploads/") :]
        abs_path = os.path.abspath(os.path.join(_uploads_dir(), rel))
        base = os.path.abspath(_uploads_dir())
        if abs_path.startswith(base) and os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        # 文件删除失败不影响数据库更新（比如文件已不存在）
        pass

    sku.photos = _dump_json_list(photos)
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


@router.post("/products", response_model=schemas.ProductOut)
def create_product(payload: schemas.AdminProductCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # A16/W2：新建商品必须输入中英双语字段（schemas.AdminProductCreate 已强约束）。
    # D1：options 字段用于定义 configurable product 的可选项和值。
    prod = models.Product(
        title=payload.title,
        title_en=payload.title_en,
        author=payload.author,
        author_en=payload.author_en,
        publisher=payload.publisher,
        publisher_en=payload.publisher_en,
        base_price=payload.base_price,
        description=payload.description,
        description_en=payload.description_en,
        category_id=payload.category_id,
        is_active=payload.is_active if payload.is_active is not None else True,
        options=payload.options,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)

    # D1/D4: simple product 也必须有 1 个 SKU。
    # 当 options 为空/缺省时，自动创建一个默认 SKU（option_values = {}）。
    if not (prod.options and prod.options.strip()):
        default_sku = models.ProductSKU(
            product_id=prod.id,
            option_values="{}",
            price_adjustment=0,
            stock_quantity=0,
            is_available=True,
        )
        db.add(default_sku)
        db.commit()
        db.refresh(prod)

    _update_product_price_range(db, prod)
    db.commit()
    return prod


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(product_id: int, payload: schemas.AdminProductUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # A17/A18/W2：编辑商品信息/上架下架（is_active）。
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
    # A14：管理端商品目录列表 + 搜索。
    # A15：支持按商品 ID 子串搜索（cast(Product.id, String).like）。
    query = db.query(models.Product)
    if q:
        like = f"%{q}%"
        # A15: 支持按商品 ID 子串搜索
        query = query.filter(
            (models.Product.title.like(like))
            | (models.Product.title_en.like(like))
            | (cast(models.Product.id, String).like(like))
        )
    return query.order_by(models.Product.created_at.desc()).all()


@router.get("/orders", response_model=List[schemas.AdminOrderListOut])
def admin_list_orders(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # A19：管理端订单列表（含 customer_name），按 created_at 倒序。
    _auto_cancel_expired_orders(db)
    rows = (
        db.query(models.Order, models.User.full_name.label("customer_name"))
        .join(models.User, models.User.id == models.Order.user_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [
        schemas.AdminOrderListOut(
            order_id=od.order_id,
            created_at=od.created_at,
            total_amount=float(od.total_amount),
            status=od.status,
            shipped_at=od.shipped_at,
            customer_name=customer_name,
        )
        for (od, customer_name) in rows
    ]


@router.get("/orders/{order_id}", response_model=schemas.OrderOut)
def admin_get_order(order_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """管理端订单详情（A20）。

    A20：点击订单可查看订单详情与行项目；
    A13/B4：同样展示地址快照与状态时间线。
    """

    _auto_cancel_expired_orders(db)
    od = db.query(models.Order).filter(models.Order.order_id == order_id).first()
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
        shipping_address=schemas.ShippingAddressSnapshotOut(
            receiver_name=od.ship_receiver_name or (od.address.receiver_name if od.address else ""),
            phone=od.ship_phone or (od.address.phone if od.address else None),
            province=od.ship_province or (od.address.province if od.address else ""),
            city=od.ship_city or (od.address.city if od.address else ""),
            district=od.ship_district or (od.address.district if od.address else ""),
            detail_address=od.ship_detail_address or (od.address.detail_address if od.address else ""),
        ),
        status_timeline=[
            schemas.OrderStatusEventOut.model_validate(ev)
            for ev in sorted(od.status_events, key=lambda e: e.created_at)
        ],
        customer_name=od.user.full_name,
        customer_email=od.user.email,
    )


@router.post("/orders/{order_id}/ship", response_model=schemas.Msg)
def mark_shipped(order_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    # B2/B4：vendor ship 操作触发 pending -> shipped，并写入 shipped 时间线事件。
    _auto_cancel_expired_orders(db)
    od = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可发货")
    od.status = "shipped"
    od.shipped_at = now_cn_naive()
    db.add(od)
    _append_status_event(db, od.order_id, "shipped", note="shipped by vendor")
    db.commit()
    return schemas.Msg(message="已标记为已发货")


@router.post("/orders/{order_id}/cancel", response_model=schemas.Msg)
def admin_cancel_order(order_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """管理端取消订单（B2）：pending -> cancelled。"""

    _auto_cancel_expired_orders(db)
    od = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not od:
        raise HTTPException(status_code=404, detail="订单不存在")
    if od.status != "pending":
        raise HTTPException(status_code=400, detail="仅待处理订单可取消")

    _restore_inventory_for_order(db, od)
    od.status = "cancelled"
    od.cancelled_at = now_cn_naive()
    db.add(od)
    _append_status_event(db, od.order_id, "cancelled", note="cancelled by vendor")
    db.commit()
    return schemas.Msg(message="订单已取消")


@router.get("/reviews", response_model=List[schemas.AdminReviewOut])
def list_reviews(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
    q: Optional[str] = Query(None),
    visible: Optional[bool] = Query(None),
):
    """管理端评论列表（内容治理）。

    - q: 模糊搜索（用户邮箱 / 商品标题 / 评论内容 / 订单号）
    - visible: 仅返回 visible / hidden
    """

    query = (
        db.query(
            models.Review,
            models.User.email.label("user_email"),
            models.Product.title.label("product_title"),
        )
        .join(models.User, models.User.id == models.Review.user_id)
        .join(models.Product, models.Product.id == models.Review.product_id)
        .order_by(models.Review.created_at.desc())
    )

    if visible is not None:
        query = query.filter(models.Review.is_visible == visible)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.User.email.like(like))
            | (models.Product.title.like(like))
            | (models.Review.comment.like(like))
            | (models.Review.order_id.like(like))
        )

    rows = query.all()
    return [
        schemas.AdminReviewOut(
            id=rv.id,
            user_id=rv.user_id,
            user_email=user_email,
            product_id=rv.product_id,
            product_title=product_title,
            order_id=rv.order_id,
            rating=rv.rating,
            comment=rv.comment,
            is_visible=rv.is_visible,
            created_at=rv.created_at,
        )
        for (rv, user_email, product_title) in rows
    ]


@router.patch("/reviews/{review_id}", response_model=schemas.AdminReviewOut)
def update_review(
    review_id: int,
    payload: schemas.AdminReviewUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    rv = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not rv:
        raise HTTPException(status_code=404, detail="评论不存在")
    rv.is_visible = payload.is_visible
    db.add(rv)
    db.commit()
    db.refresh(rv)

    # 理论上 join 一定能查到；这里给出兜底，避免 EmailStr 校验失败
    user_email = db.query(models.User.email).filter(models.User.id == rv.user_id).scalar() or "unknown@example.com"
    product_title = db.query(models.Product.title).filter(models.Product.id == rv.product_id).scalar() or "未知商品"

    return schemas.AdminReviewOut(
        id=rv.id,
        user_id=rv.user_id,
        user_email=user_email,
        product_id=rv.product_id,
        product_title=product_title,
        order_id=rv.order_id,
        rating=rv.rating,
        comment=rv.comment,
        is_visible=rv.is_visible,
        created_at=rv.created_at,
    )


@router.delete("/reviews/{review_id}", response_model=schemas.Msg)
def delete_review(review_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    rv = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not rv:
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(rv)
    db.commit()
    return schemas.Msg(message="评论已删除")


@router.get("/reports/sales", response_model=schemas.SalesSummaryOut)
def sales_report(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
):
    """销售报表（V1）。

    - 支持时间范围：start/end（包含端点）。为空则默认最近 30 天。
    - 支持粒度：day/week/month。
    - 返回 series：用于前端图表展示（销售额 + 订单数）。

    说明：为降低复杂度，本实现使用 Python 聚合，不追求性能。
    """

    def _parse_ymd(s: str) -> date:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail=f"日期格式错误：{s}，应为 YYYY-MM-DD")

    if start:
        start_d = _parse_ymd(start)
    else:
        # 报表默认时间范围按中国大陆日期（UTC+8）。
        start_d = (now_cn_naive().date() - timedelta(days=29))

    if end:
        end_d = _parse_ymd(end)
    else:
        end_d = now_cn_naive().date()

    if end_d < start_d:
        raise HTTPException(status_code=400, detail="end 不能早于 start")

    start_dt = datetime.combine(start_d, datetime.min.time())
    # end 取当天 23:59:59.999999
    end_dt = datetime.combine(end_d, datetime.max.time())

    orders_q = (
        db.query(models.Order)
        .filter(models.Order.status != "cancelled")
        .filter(models.Order.created_at >= start_dt)
        .filter(models.Order.created_at <= end_dt)
    )

    orders = orders_q.order_by(models.Order.created_at.asc()).all()
    order_ids = [o.order_id for o in orders]

    # 总销售额与订单数
    total_sales = float(sum(float(o.total_amount or 0.0) for o in orders))
    order_count = len(orders)

    # series 聚合
    series_map: dict[str, dict[str, float | int]] = {}
    for o in orders:
        d = o.created_at.date()
        if granularity == "day":
            period = d.strftime("%Y-%m-%d")
        elif granularity == "month":
            period = d.strftime("%Y-%m")
        else:
            iso_year, iso_week, _ = d.isocalendar()
            period = f"{iso_year}-W{iso_week:02d}"

        bucket = series_map.setdefault(period, {"sales": 0.0, "order_count": 0})
        bucket["sales"] = float(bucket["sales"]) + float(o.total_amount or 0.0)
        bucket["order_count"] = int(bucket["order_count"]) + 1

    series = [
        schemas.SalesSeriesPoint(
            period=k,
            sales=float(v["sales"]),
            order_count=int(v["order_count"]),
        )
        for k, v in sorted(series_map.items(), key=lambda kv: kv[0])
    ]

    # 畅销书（范围内）
    best_sellers: List[schemas.BestSellerOut] = []
    if order_ids:
        rows = (
            db.query(
                models.Product.id.label("product_id"),
                models.Product.title.label("title"),
                models.Product.title_en.label("title_en"),
                func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("sales"),
            )
            .join(models.ProductSKU, models.ProductSKU.product_id == models.Product.id)
            .join(models.OrderItem, models.OrderItem.sku_id == models.ProductSKU.id)
            .join(models.Order, models.OrderItem.order_id == models.Order.order_id)
            .filter(models.Order.order_id.in_(order_ids))
            .group_by(models.Product.id, models.Product.title, models.Product.title_en)
            .order_by(func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).desc())
            .limit(10)
            .all()
        )
        best_sellers = [
            schemas.BestSellerOut(
                product_id=r.product_id,
                title=r.title,
                title_en=r.title_en,
                sales=float(r.sales or 0.0),
            )
            for r in rows
        ]

    return schemas.SalesSummaryOut(
        total_sales=total_sales,
        order_count=order_count,
        best_sellers=best_sellers,
        series=series,
    )
