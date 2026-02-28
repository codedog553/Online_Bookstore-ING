from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# 通用
class Msg(BaseModel):
    message: str


# 用户相关
class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    language: Optional[str] = "zh"


class UserCreate(BaseModel):  
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    language: Optional[str] = None
    default_address_id: Optional[int] = None


class UserOut(UserBase):
    id: int
    is_admin: bool
    default_address_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# 地址
class AddressBase(BaseModel):
    receiver_name: str
    phone: Optional[str] = None
    province: str
    city: str
    district: str
    detail_address: str
    is_default: Optional[bool] = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    receiver_name: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    detail_address: Optional[str] = None
    is_default: Optional[bool] = None


class AddressOut(AddressBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 分类
class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# 商品与 SKU
class SKUOut(BaseModel):
    id: int
    product_id: int
    option_values: str  # JSON 字符串
    price_adjustment: float
    stock_quantity: int
    is_available: bool

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    base_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    is_active: bool
    images: Optional[str] = None   # JSON 字符串列表
    options: Optional[str] = None  # JSON 字符串

    class Config:
        from_attributes = True


class ProductDetail(ProductOut):
    skus: List[SKUOut] = []


# 购物车
class CartItemCreate(BaseModel):
    sku_id: int
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemOut(BaseModel):
    id: int
    sku_id: int
    quantity: int
    # 展示需要的冗余字段
    product_title: str
    option_values: str
    unit_price: float
    subtotal: float


# 订单
class OrderCreate(BaseModel):
    address_id: int


class OrderItemOut(BaseModel):
    sku_id: int
    quantity: int
    unit_price: float
    option_values: str


class OrderOut(BaseModel):
    order_id: str
    total_amount: float
    status: str
    shipped_at: Optional[datetime] = None
    created_at: datetime
    items: List[OrderItemOut] = []


# 评论
class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    order_id: str
    rating: int
    comment: Optional[str] = None
    is_visible: bool
    created_at: datetime

    class Config:
        from_attributes = True


# 管理端
class AdminProductCreate(BaseModel):
    title: str
    author: Optional[str] = None
    base_price: float
    description: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = True
    images: Optional[str] = None
    options: Optional[str] = None


class AdminProductUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    base_price: Optional[float] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None
    images: Optional[str] = None
    options: Optional[str] = None


class SalesSummaryOut(BaseModel):
    total_sales: float
    order_count: int
    best_sellers: List[dict] = []
