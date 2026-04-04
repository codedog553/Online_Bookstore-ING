from datetime import datetime
from typing import List, Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# 需求标注说明：
# - A*：顾客侧账号 / 商品浏览 / 购物车 / 订单
# - B*：商品多图 / 订单状态流转 / 状态时间线
# - D*：可配置商品 / SKU / 库存
# - W*：国际化与商品双语字段


# 通用
class Msg(BaseModel):
    message: str


# 用户相关
class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    language: Optional[str] = "zh"


class UserCreate(BaseModel):
    """注册用户。

    按需求 A1：注册时必须提供收货地址。
    该地址会作为用户第一次下单时的默认/上一次地址（last address）。
    """

    class ShippingAddressIn(BaseModel):
        receiver_name: str
        phone: Optional[str] = None
        province: str
        city: str
        district: str
        detail_address: str

    full_name: str
    email: EmailStr
    # 需求：至少 8 位，且必须同时包含字母与数字
    password: str = Field(min_length=8)
    shipping_address: ShippingAddressIn

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
    # D1/D4/D5：SKU 响应承担“具体配置 + 库存 + 可售状态 + 多图”的输出责任。
    id: int
    product_id: int
    option_values: str  # JSON 字符串
    price_adjustment: float
    stock_quantity: int
    is_available: bool
    photos: Optional[str] = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    # A3/A6/W2：商品列表与详情共用的核心展示结构。
    # - A3：用于商品列表基础信息展示
    # - A6：详情页额外属性（作者、出版方等）
    # - W2：商品字段采用中英双语存储
    id: int
    title: str
    # 商品信息国际化：仅要求支持中文(默认)与英文
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None
    # 出版方（A6/W2）：中英双语
    publisher: Optional[str] = None
    publisher_en: Optional[str] = None
    base_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    category_id: Optional[int] = None
    is_active: bool
    # 注意：P0 统一图片只走 SKU 本地上传（sku.photos）。
    # 保留该字段仅为兼容旧数据/不做 DB 迁移；前端/后端新逻辑不再使用它。
    images: Optional[str] = None   # DEPRECATED
    options: Optional[str] = None  # JSON 字符串

    # A3/A16/P0: 商品缩略图（用于列表展示）。
    # - 由后端动态计算（从任意 SKU photos 取第一张）。
    thumbnail_url: Optional[str] = None

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
    # A7/D2：加入购物车时必须指定具体 SKU；可配置商品不能只传 product_id。
    sku_id: int
    quantity: int = 1


class CartItemUpdate(BaseModel):
    # A9：购物车数量修改入口。
    quantity: int


class CartItemOut(BaseModel):
    # A8/A9/A10/D3/D5：购物车列表项的完整展示/校验信息。
    # - A8：展示商品名、价格、数量、小计
    # - D3：区分同一本书的不同配置
    # - D5：携带库存与可售状态，供前端拦截缺货下单
    id: int
    sku_id: int
    quantity: int
    # 展示需要的冗余字段
    product_id: int
    product_title: str
    product_title_en: Optional[str] = None
    option_values: str
    # 用于 W2：选项值的双语映射（从商品 options 下发）
    product_options: Optional[str] = None
    unit_price: float
    subtotal: float

    # D5: 前端需要知道是否缺货/不可售，以在购物车/结算页做提示与禁止下单。
    stock_quantity: Optional[int] = None
    is_available: Optional[bool] = None


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
    # A13/D3：订单项输出的是“下单瞬间的商品/SKU 快照视角”。
    sku_id: int
    quantity: int
    unit_price: float
    option_values: str

    # 展示需要的冗余字段（A13/W2）
    product_id: int
    product_title: str
    product_title_en: Optional[str] = None
    # 用于 W2：选项值的双语映射（从商品 options 下发）
    product_options: Optional[str] = None
    subtotal: float


class ShippingAddressSnapshotOut(BaseModel):
    """订单内的收货地址快照（A13）。"""

    receiver_name: str
    phone: Optional[str] = None
    province: str
    city: str
    district: str
    detail_address: str


class OrderStatusEventOut(BaseModel):
    """订单状态时间线事件（B4）。"""

    id: int
    order_id: str
    status: str
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    # A12/A13/B3/B4：订单列表与详情的统一返回结构。
    # - A12：订单列表基础字段
    # - A13：订单详情中的地址快照、行项目
    # - B3：前端可依据当前 status 做过滤
    # - B4：状态时间线在详情中展示
    order_id: str
    total_amount: float
    status: str
    shipped_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    items: List[OrderItemOut] = []

    # 订单详情展示字段（A13/B4）
    shipping_address: Optional[ShippingAddressSnapshotOut] = None
    status_timeline: List[OrderStatusEventOut] = []

    # 管理端可选展示字段（A19/A20）
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None


class AdminOrderListOut(BaseModel):
    """管理端订单列表（A19）。"""

    order_id: str
    created_at: datetime
    total_amount: float
    status: str
    shipped_at: Optional[datetime] = None
    customer_name: str



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
    # A16/A17/D1/W2：管理端创建商品时的输入结构。
    # - A16：商品基本信息新增
    # - D1：允许定义 configurable product 的 options
    # - W2：强制录入中英双语商品文案
    # W2: 商品信息必须中英双语输入（后端强约束，避免绕过前端）
    title: str
    title_en: str
    author: str
    author_en: str
    publisher: str
    publisher_en: str
    base_price: float
    description: str
    description_en: str
    category_id: Optional[int] = None
    is_active: Optional[bool] = True
    options: Optional[str] = None


class AdminProductUpdate(BaseModel):
    # A17/A18/D1/W2：管理端编辑商品与启停商品时使用。
    title: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None
    publisher: Optional[str] = None
    publisher_en: Optional[str] = None
    base_price: Optional[float] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None
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
    # D1/D4/D5/B1：新增 SKU 时定义配置、加价、库存、可售状态。
    # 图片单独通过上传接口维护，因此这里不直接放 photos 字段。
    option_values: str  # JSON 字符串，例如 {"color":"red","size":"M"}
    price_adjustment: float = 0.0
    stock_quantity: int = 0
    is_available: bool = True


class AdminSKUUpdate(BaseModel):
    # D4/D5：SKU 编辑主要覆盖配置、库存与是否可售。
    option_values: Optional[str] = None
    price_adjustment: Optional[float] = None
    stock_quantity: Optional[int] = None
    is_available: Optional[bool] = None
