from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/addresses", tags=["addresses"])

# =========================
# Requirements Traceability
# =========================
# A1: Registration collects an initial shipping address.
# A11: Checkout uses shipping address and updates the "last address" for next checkout autofill.
# NOTE (产品约束): 不维护用户 address list（地址簿），只记忆“上一次填写的地址”。
# This router exposes /last as the canonical endpoint for that rule.


@router.get("/last", response_model=schemas.AddressOut)
def get_last_address(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """获取用户“上一次地址”(last address)。

    说明：产品约束为“不维护地址列表”，但为兼容旧数据与减少改动成本，
    我们复用 addresses 表，仅返回 1 条记录供结算页预填。
    """
    # A11: 结算页会先调用该接口预填地址；若不存在则允许用户首次手填。
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
    if not addr:
        raise HTTPException(status_code=404, detail="暂无地址记录")
    return addr


@router.put("/last", response_model=schemas.AddressOut)
def upsert_last_address(payload: schemas.AddressCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """保存/更新 last address。

    前端可在“结算页”先保存地址，再下单；也可直接下单时保存（由 orders.create_order 内部完成）。
    """
    # A1/A11：这里实现“只记忆上一次地址”的产品规则。
    # 即使底层仍沿用 addresses 表，店面主流程也只会覆盖当前 last address，
    # 用于下一次结算页自动预填，而不是维护一个可选地址簿。
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
        for k, v in payload.dict().items():
            setattr(addr, k, v)
        addr.is_default = True
        db.add(addr)
        db.flush()
    else:
        addr = models.Address(user_id=current_user.id, **payload.dict())
        addr.is_default = True
        db.add(addr)
        db.flush()

    # 取消其他 default（避免旧数据导致多个默认）
    db.query(models.Address).filter(
        models.Address.user_id == current_user.id,
        models.Address.id != addr.id,
    ).update({models.Address.is_default: False})

    current_user.default_address_id = addr.id
    db.add(current_user)
    db.commit()
    db.refresh(addr)
    return addr


@router.get("", response_model=List[schemas.AddressOut])
def list_addresses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 说明：该接口主要用于兼容旧结构/调试。
    # 面向课程需求的前台流程，优先使用 /api/addresses/last，而非地址列表管理。
    items = (
        db.query(models.Address)
        .filter(models.Address.user_id == current_user.id)
        .order_by(models.Address.created_at.desc())
        .all()
    )
    return items


@router.post("", response_model=schemas.AddressOut)
def create_address(payload: schemas.AddressCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    addr = models.Address(user_id=current_user.id, **payload.dict())
    if payload.is_default:
        # 取消其他默认
        db.query(models.Address).filter(models.Address.user_id == current_user.id).update({models.Address.is_default: False})
    db.add(addr)
    db.commit()
    db.refresh(addr)
    if addr.is_default:
        current_user.default_address_id = addr.id
        db.add(current_user)
        db.commit()
    return addr


@router.put("/{address_id}", response_model=schemas.AddressOut)
def update_address(address_id: int, payload: schemas.AddressUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    addr = (
        db.query(models.Address)
        .filter(models.Address.id == address_id, models.Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(addr, k, v)
    if payload.is_default is True:
        db.query(models.Address).filter(models.Address.user_id == current_user.id, models.Address.id != addr.id).update({models.Address.is_default: False})
        current_user.default_address_id = addr.id
        db.add(current_user)
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/{address_id}", response_model=schemas.Msg)
def delete_address(address_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    addr = (
        db.query(models.Address)
        .filter(models.Address.id == address_id, models.Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(status_code=404, detail="地址不存在")
    db.delete(addr)
    db.commit()
    # 如删除的是默认地址，清空用户默认地址
    if current_user.default_address_id == address_id:
        current_user.default_address_id = None
        db.add(current_user)
        db.commit()
    return schemas.Msg(message="已删除")
