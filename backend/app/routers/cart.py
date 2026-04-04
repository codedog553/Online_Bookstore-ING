from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/cart", tags=["cart"])

# =========================
# Requirements Traceability
# =========================
# A2: After login, customers can manage carts (server-side persisted across sessions).
# A7: Add product to cart (default quantity = 1).
# A8: List cart items with product name/price/quantity and show totals (total computed on frontend).
# A9: Update quantity.
# A10: Remove item.
# D2/D3: Cart is SKU-based to support configurable products and buying multiple configurations.
# D5: Out-of-stock / unavailable SKU cannot be added/updated/checked out (validated here + surfaced to frontend).
# W2: Product bilingual fields are returned (title/title_en) for frontend locale rules.


def _sku_unit_price(sku: models.ProductSKU) -> float:
    # A8/D3：购物车和订单展示的单价，统一来自“商品基础价 + SKU 配置加价”。
    base = float(sku.product.base_price)
    adj = float(sku.price_adjustment or 0)
    return base + adj


@router.get("", response_model=List[schemas.CartItemOut])
def get_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # A2/A8：购物车保存在服务端，用户重新登录后仍可读取。
    # 返回结果除了名称/数量/价格外，还带上 SKU 库存与可售状态，供前端做 D5 缺货提示。
    items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    result: List[schemas.CartItemOut] = []
    for it in items:
        unit_price = _sku_unit_price(it.sku)
        prod = it.sku.product
        result.append(
            schemas.CartItemOut(
                id=it.id,
                sku_id=it.sku_id,
                quantity=it.quantity,
                product_id=prod.id,
                product_title=prod.title,
                product_title_en=prod.title_en,
                option_values=it.sku.option_values,
                product_options=prod.options,
                unit_price=unit_price,
                subtotal=unit_price * it.quantity,
                stock_quantity=it.sku.stock_quantity,
                is_available=it.sku.is_available,
            )
        )
    return result


@router.post("/items", response_model=schemas.Msg)
def add_to_cart(payload: schemas.CartItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # A7：加入购物车默认 quantity=1（见 schemas.CartItemCreate 默认值）。
    # D2/D3：加入购物车的最小单位是 SKU，而不是抽象商品。
    # 这保证了：
    # - 配置商品必须先选定具体版本/配置；
    # - 同一本书的不同版本会形成不同购物车项；
    # - 缺货或不可售 SKU 不能加入购物车。
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
    # A9：购物车支持改数量。
    # A10：当数量 <= 0 时，直接退化为删除该项（等价于 remove）。
    # D5：更新时也会再次校验库存与可售状态，防止前端页面停留期间库存发生变化。
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
    if not item.sku.is_available:
        raise HTTPException(status_code=400, detail="SKU 不可售")
    if item.sku.stock_quantity is not None and payload.quantity > item.sku.stock_quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    item.quantity = payload.quantity
    db.add(item)
    db.commit()
    return schemas.Msg(message="数量已更新")


@router.delete("/items/{item_id}", response_model=schemas.Msg)
def remove_item(item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # A10：显式删除购物车项。
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
