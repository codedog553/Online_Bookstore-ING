from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_password_hash, verify_password, create_access_token
from ..db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# =========================
# Requirements Traceability
# =========================
# A1: Customers register with full name/email/password/shipping address; the address becomes the first "last address".
# A2: Login gates server-side persisted capabilities (cart/orders/addresses) via JWT.


def _create_initial_address(db: Session, user: models.User, addr_in: schemas.UserCreate.ShippingAddressIn) -> models.Address:
    """注册时创建用户的首个地址，并写入 default_address_id。

    产品约束：不维护 address list，只记忆上一次填写的地址。
    为兼容现有结构，我们仍落库到 addresses 表，但前端只使用 /api/addresses/last.
    """

    addr = models.Address(
        user_id=user.id,
        receiver_name=addr_in.receiver_name,
        phone=addr_in.phone,
        province=addr_in.province,
        city=addr_in.city,
        district=addr_in.district,
        detail_address=addr_in.detail_address,
        is_default=True,
    )
    db.add(addr)
    db.flush()  # 获取 addr.id
    user.default_address_id = addr.id
    db.add(user)
    return addr


@router.post("/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # A1：注册时要求提交 full name / email / password / shipping address。
    # A1：这里先创建用户，再立刻创建首个地址记录，并把它标记为 default/last address。
    #      该 default_address_id 会被结算页当作“上一次地址”预填来源。
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
    db.flush()  # 获取 user.id

    # A1: 注册时写入首个 shipping address，作为首次下单的默认/上一次地址
    _create_initial_address(db, user, user_in.shipping_address)

    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)


@router.post("/login", response_model=schemas.Token)
def login(cred: schemas.UserLogin, db: Session = Depends(get_db)):
    # A2：登录是购物车、订单、地址等“登录后能力”的入口。
    # A2：产品浏览/搜索/详情无需登录（见 products.py 中无 Depends(get_current_user)）；
    #     需要服务器侧持久化的用户能力（cart/orders/addresses）则依赖该认证结果。
    user = db.query(models.User).filter(models.User.email == cred.email).first()
    if not user or not verify_password(cred.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)
