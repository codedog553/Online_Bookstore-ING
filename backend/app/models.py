from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship
from .db import Base


# 需求标注总览（本文件主要负责数据结构层）
# - A1：用户注册时写入首个收货地址，并把它作为默认/上一次地址。
# - A13：订单需要保留下单时的收货地址快照，避免后续改地址影响历史订单。
# - B1：商品多图按 SKU 维度存储，支持一个版本对应多张图片。
# - B2/B4：订单既保存当前状态，也保存状态时间线事件。
# - D1/D4/D5：可配置商品通过 Product + ProductSKU + 库存字段实现。
# - W2：商品信息保存中英双语字段，供前端按语言规则展示。


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    # A1：系统在业务上只记忆“上一次填写的地址”，
    # 这里用 default_address_id 指向当前用户最近一次用于结算预填的地址记录。
    default_address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    language = Column(String(5), default="zh")
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan", foreign_keys="Address.user_id")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", foreign_keys="Order.user_id")
    reviews = relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    default_address = relationship("Address", foreign_keys=[default_address_id], uselist=False)


class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # A1/A11：虽然产品要求前端主流程“不维护地址列表”，
    # 但底层仍复用地址表做持久化，以降低实现复杂度并兼容旧逻辑。
    receiver_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    province = Column(String(50), nullable=False)
    city = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    detail_address = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="addresses", foreign_keys=[user_id])
    orders = relationship("Order", back_populates="address", foreign_keys="Order.address_id")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children = relationship("Category", remote_side=[id])
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    # W2：商品业务信息要求录入简体中文与英文两套文本。
    # 前端再根据当前语言决定显示中文还是英文。
    title_en = Column(String(200), nullable=True)
    author = Column(String(100), nullable=True)
    author_en = Column(String(100), nullable=True)
    # A6/W2：作者、出版方属于商品详情中的额外属性，也要求中英双语。
    publisher = Column(String(200), nullable=True)
    publisher_en = Column(String(200), nullable=True)
    base_price = Column(Numeric(10, 2), nullable=False)
    min_price = Column(Numeric(10, 2), nullable=True)
    max_price = Column(Numeric(10, 2), nullable=True)
    description = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    images = Column(Text, nullable=True)  # JSON string list
    # D1：商品级 options 保存“有哪些可选项、每个可选项有哪些值”。
    # 例如：{"版本": ["普通", "精装"]}
    options = Column(Text, nullable=True)  # JSON string dict
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    skus = relationship("ProductSKU", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product")


class ProductSKU(Base):
    __tablename__ = "product_skus"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    # D1/D4：每个 SKU 对应一种确定的配置组合；
    # 因此不同版本/配置会拥有独立库存、独立可售状态。
    option_values = Column(Text, nullable=False)  # JSON string dict
    price_adjustment = Column(Numeric(10, 2), default=0)
    # D4/D5：库存按 SKU 维度维护，而不是按商品维度统一维护。
    stock_quantity = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    # B1/A16/D2：图片也按 SKU 维度保存。
    # 这样前端在用户选择不同版本时，可以切换到该版本对应的图片组。
    photos = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="skus")
    cart_items = relationship("CartItem", back_populates="sku")
    order_items = relationship("OrderItem", back_populates="sku")


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("product_skus.id"), nullable=False)
    # A7/D3：购物车项绑定到 SKU，因此同一本书的不同版本会作为不同购物车项存在。
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="cart_items")
    sku = relationship("ProductSKU", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(20), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # address_id 仍然保留到地址表的关联，便于复用已有地址数据；
    # 但历史订单展示不能只依赖这条关联，因为地址可能被用户后续修改。
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    # A13：订单下单时的地址快照。
    # 这样即使用户之后修改了“上一次地址”，历史订单仍显示下单当时的真实地址信息。
    ship_receiver_name = Column(String(100), nullable=True)
    ship_phone = Column(String(20), nullable=True)
    ship_province = Column(String(50), nullable=True)
    ship_city = Column(String(50), nullable=True)
    ship_district = Column(String(50), nullable=True)
    ship_detail_address = Column(String(255), nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    # B2：订单当前状态，用于列表过滤与业务流转判断。
    status = Column(String(20), default="pending")  # pending, shipped, cancelled, completed
    # B4：常用状态时间点做冗余落库，便于详情页直接展示。
    shipped_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders", foreign_keys=[user_id])
    address = relationship("Address", back_populates="orders", foreign_keys=[address_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_events = relationship("OrderStatusEvent", back_populates="order", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="order", foreign_keys="Review.order_id")


class OrderStatusEvent(Base):
    """订单状态时间线事件（B4）。

    说明：每次状态变化都追加一条事件记录，用于前端展示 timeline。

    这里与 orders.status / shipped_at / completed_at / cancelled_at 并存：
    - orders.status：表示“当前状态”，便于筛选与快速判断；
    - order_status_events：表示“历史轨迹”，便于详情页展示完整时间线。
    """

    __tablename__ = "order_status_events"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="status_events", foreign_keys=[order_id])


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("product_skus.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    # A13/D3：订单项需要记录下单时对应 SKU 的配置快照，
    # 避免商品配置名称或结构变动后影响历史订单展示。
    option_values = Column(Text, nullable=False)  # JSON string dict snapshot

    order = relationship("Order", back_populates="items", foreign_keys=[order_id])
    sku = relationship("ProductSKU", back_populates="order_items", foreign_keys=[sku_id])


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reviews", foreign_keys=[user_id])
    product = relationship("Product", back_populates="reviews", foreign_keys=[product_id])
    order = relationship("Order", back_populates="reviews", foreign_keys=[order_id])
