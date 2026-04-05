from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    is_admin = Column(Boolean, default=False)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    title_en = Column(String(200))
    author = Column(String(100))
    author_en = Column(String(100))
    publisher = Column(String(200))
    publisher_en = Column(String(200))
    description = Column(Text)
    description_en = Column(Text)
    base_price = Column(Numeric(10, 2), nullable=False)
    options = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    skus = relationship("ProductSKU", back_populates="product")


class ProductSKU(Base):
    __tablename__ = "product_skus"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    option_values = Column(Text, nullable=False)
    price_adjustment = Column(Numeric(10, 2), default=0)
    stock_quantity = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    photos = Column(Text)

    product = relationship("Product", back_populates="skus")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("product_skus.id"), nullable=False)
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    sku = relationship("ProductSKU")
