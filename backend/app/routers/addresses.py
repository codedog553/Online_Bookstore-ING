from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/addresses", tags=["addresses"])


@router.get("", response_model=List[schemas.AddressOut])
def list_addresses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
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
