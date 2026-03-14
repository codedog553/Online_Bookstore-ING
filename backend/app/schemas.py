from datetime import datetime
from typing import List, Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
    # 需求：至少 8 位，且必须同时包含字母与数字
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # 允许包含特殊字符，但必须同时包含：字母 + 数字
        if len(v) < 8:
            return v  # 交给 min_length 的默认错误信息
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("密码至少 8 位，且必须包含字母和数字")
        return v


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
    # 商品信息国际化：仅要求支持中文(默认)与英文
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None
    base_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    category_id: Optional[int] = None
    is_active: bool
    images: Optional[str] = None   # JSON 字符串列表
    options: Optional[str] = None  # JSON 字符串

    class Config:
        from_attributes = True


class ProductDetail(ProductOut):
    skus: List[SKUOut] = []


class PagedProductsOut(BaseModel):
    """商品分页返回结构：用于前端显示真实 total。"""

    items: List[ProductOut]
    total: int
    page: int
    size: int


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
    """创建订单。

    兼容两种前端实现：
    - 传 `address_id`：从地址簿中选择地址（原实现）。
    - 传 `address`：直接提交收货地址对象（可用于“上一次地址”预填/不维护地址簿的简化实现）。
    """

    class ShippingAddressIn(BaseModel):
        receiver_name: str
        phone: Optional[str] = None
        province: str
        city: str
        district: str
        detail_address: str

    address_id: Optional[int] = None
    address: Optional[ShippingAddressIn] = None

    @model_validator(mode="after")
    def _validate_address(self):
        if not self.address_id and not self.address:
            raise ValueError("address_id 或 address 至少提供一个")
        return self


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
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None
    base_price: float
    description: Optional[str] = None
    description_en: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = True
    images: Optional[str] = None
    options: Optional[str] = None


class AdminProductUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None
    base_price: Optional[float] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None
    images: Optional[str] = None
    options: Optional[str] = None


class SalesSeriesPoint(BaseModel):
    period: str  # 例如 2026-03-01 / 2026-W10 / 2026-03
    sales: float
    order_count: int


class BestSellerOut(BaseModel):
    product_id: int
    title: str
    title_en: Optional[str] = None
    sales: float


class SalesSummaryOut(BaseModel):
    total_sales: float
    order_count: int
    best_sellers: List[BestSellerOut] = []
    series: List[SalesSeriesPoint] = []


class AdminReviewOut(BaseModel):
    """管理端评论列表展示（用于内容治理）。"""

    id: int
    user_id: int
    user_email: EmailStr
    product_id: int
    product_title: str
    order_id: str
    rating: int
    comment: Optional[str] = None
    is_visible: bool
    created_at: datetime


class AdminReviewUpdate(BaseModel):
    is_visible: bool

# 管理端 - SKU
class AdminSKUCreate(BaseModel):
    option_values: str  # JSON 字符串，例如 {"color":"red","size":"M"}
    price_adjustment: float = 0.0
    stock_quantity: int = 0
    is_available: bool = True


class AdminSKUUpdate(BaseModel):
    option_values: Optional[str] = None
    price_adjustment: Optional[float] = None
    stock_quantity: Optional[int] = None
    is_available: Optional[bool] = None
