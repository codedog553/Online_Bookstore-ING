from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
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
    # 商品信息国际化：仅要求支持中文(默认)与英文
    title_en = Column(String(200), nullable=True)
    author = Column(String(100), nullable=True)
    author_en = Column(String(100), nullable=True)
    base_price = Column(Numeric(10, 2), nullable=False)
    min_price = Column(Numeric(10, 2), nullable=True)
    max_price = Column(Numeric(10, 2), nullable=True)
    description = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    images = Column(Text, nullable=True)  # JSON string list
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
    option_values = Column(Text, nullable=False)  # JSON string dict
    price_adjustment = Column(Numeric(10, 2), default=0)
    stock_quantity = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
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
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="cart_items")
    sku = relationship("ProductSKU", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(20), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="pending")  # pending, shipped, cancelled, completed
    shipped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders", foreign_keys=[user_id])
    address = relationship("Address", back_populates="orders", foreign_keys=[address_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="order", foreign_keys="Review.order_id")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("product_skus.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
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
