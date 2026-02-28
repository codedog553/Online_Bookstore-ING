from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_password_hash, verify_password, create_access_token
from ..db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.email == user_in.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    user = models.User(
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        language="zh",
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)


@router.post("/login", response_model=schemas.Token)
def login(cred: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == cred.email).first()
    if not user or not verify_password(cred.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)
