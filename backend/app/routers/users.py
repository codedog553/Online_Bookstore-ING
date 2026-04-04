from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=schemas.UserOut)
def update_me(payload: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.language is not None:
        current_user.language = payload.language
    if payload.default_address_id is not None:
        # 简单校验：该地址属于当前用户
        addr = db.query(models.Address).filter(models.Address.id == payload.default_address_id, models.Address.user_id == current_user.id).first()
        if not addr:
            raise HTTPException(status_code=400, detail="默认地址无效")
        current_user.default_address_id = payload.default_address_id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
