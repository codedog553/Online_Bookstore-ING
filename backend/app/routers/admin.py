from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, String

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


@router.post("/products", response_model=schemas.ProductOut)
def create_product(payload: schemas.AdminProductCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    prod = models.Product(
        title=payload.title,
        title_en=payload.title_en,
        author=payload.author,
        author_en=payload.author_en,
        base_price=payload.base_price,
        description=payload.description,
        description_en=payload.description_en,
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
        # A15: 支持按商品 ID 子串搜索
        query = query.filter(
            (models.Product.title.like(like))
            | (models.Product.title_en.like(like))
            | (cast(models.Product.id, String).like(like))
        )
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
        start_d = (datetime.utcnow().date() - timedelta(days=29))

    if end:
        end_d = _parse_ymd(end)
    else:
        end_d = datetime.utcnow().date()

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
