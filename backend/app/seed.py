"""
简单的示例数据初始化脚本：
- 创建管理员与普通用户
- 创建分类、商品及 SKU（平装/精装）
- 创建示例地址、订单与评论

使用方法：
  conda activate Qchat
  pip install -r backend/requirements.txt
  python -m app.seed
"""
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db
from . import models
from .auth import get_password_hash
import json


def reset_all(db: Session):
    # 简单清库（SQLite，无外键顺序要求时可直接删除；为简单起见逐表清理）
    db.query(models.Review).delete()
    db.query(models.OrderItem).delete()
    db.query(models.Order).delete()
    db.query(models.CartItem).delete()
    db.query(models.ProductSKU).delete()
    db.query(models.Product).delete()
    db.query(models.Category).delete()
    db.query(models.Address).delete()
    db.query(models.User).delete()
    db.commit()


def create_users(db: Session):
    admin = models.User(
        full_name="Admin",
        email="admin@demo.com",
        password_hash=get_password_hash("Admin1234"),
        is_admin=True,
        language="zh",
    )
    user = models.User(
        full_name="Demo User",
        email="user@demo.com",
        password_hash=get_password_hash("User1234"),
        is_admin=False,
        language="zh",
    )
    db.add_all([admin, user])
    db.commit()
    db.refresh(admin)
    db.refresh(user)
    return admin, user


def create_categories(db: Session):
    cat1 = models.Category(name="文学", sort_order=1)
    cat2 = models.Category(name="科技", sort_order=2)
    db.add_all([cat1, cat2])
    db.commit()
    db.refresh(cat1)
    db.refresh(cat2)
    return cat1, cat2


def create_product_with_skus(db: Session, title: str, author: str, base_price: float, category_id: int, images: list[str]):
    prod = models.Product(
        title=title,
        author=author,
        base_price=base_price,
        description=f"《{title}》简介……",
        category_id=category_id,
        is_active=True,
        images=json.dumps(images, ensure_ascii=False),
        options=json.dumps({"version": ["平装", "精装"]}, ensure_ascii=False),
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)

    # 平装/精装 两个 SKU
    sku1 = models.ProductSKU(
        product_id=prod.id,
        option_values=json.dumps({"version": "平装"}, ensure_ascii=False),
        price_adjustment=0,
        stock_quantity=50,
        is_available=True,
    )
    sku2 = models.ProductSKU(
        product_id=prod.id,
        option_values=json.dumps({"version": "精装"}, ensure_ascii=False),
        price_adjustment=10.0,
        stock_quantity=20,
        is_available=True,
    )
    db.add_all([sku1, sku2])
    db.commit()

    # 更新价格范围
    prices = [float(prod.base_price) + float(sku1.price_adjustment or 0), float(prod.base_price) + float(sku2.price_adjustment or 0)]
    prod.min_price = min(prices)
    prod.max_price = max(prices)
    db.add(prod)
    db.commit()
    return prod


def create_demo_order_and_review(db: Session, user: models.User, product: models.Product):
    # 地址
    addr = models.Address(
        user_id=user.id,
        receiver_name=user.full_name,
        phone="13800000000",
        province="上海",
        city="上海",
        district="浦东新区",
        detail_address="世纪大道 1 号",
        is_default=True,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    user.default_address_id = addr.id
    db.add(user)
    db.commit()

    # 选择精装 SKU
    sku = db.query(models.ProductSKU).filter(models.ProductSKU.product_id == product.id, models.ProductSKU.option_values.like('%精装%')).first()
    unit_price = float(product.base_price) + float(sku.price_adjustment or 0)

    od = models.Order(
        order_id="ORDER99991231-001",
        user_id=user.id,
        address_id=addr.id,
        total_amount=unit_price,
        status="completed",
    )
    db.add(od)
    db.commit()
    db.refresh(od)

    oi = models.OrderItem(
        order_id=od.order_id,
        sku_id=sku.id,
        quantity=1,
        unit_price=unit_price,
        option_values=sku.option_values,
    )
    db.add(oi)
    db.commit()

    rv = models.Review(
        user_id=user.id,
        product_id=product.id,
        order_id=od.order_id,
        rating=5,
        comment="非常好看！",
        is_visible=True,
    )
    db.add(rv)
    db.commit()


def main():
    init_db()
    db = SessionLocal()
    try:
        reset_all(db)
        admin, user = create_users(db)
        cat1, cat2 = create_categories(db)
        # 示例图
        imgs1 = [
            "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=800",
            "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800",
        ]
        imgs2 = [
            "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=800",
            "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=800",
        ]
        p1 = create_product_with_skus(db, "哈利波特与魔法石", "J.K.罗琳", 49.0, cat1.id, imgs1)
        p2 = create_product_with_skus(db, "深入浅出计算机", "张三", 59.0, cat2.id, imgs2)
        create_demo_order_and_review(db, user, p1)
        print("Seed completed. Admin: admin@demo.com / Admin1234, User: user@demo.com / User1234")
    finally:
        db.close()


if __name__ == "__main__":
    main()
