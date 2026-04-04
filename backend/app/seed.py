"""
简单的示例数据初始化脚本：
- 创建管理员与普通用户
- 创建分类、商品及 SKU（平装/精装）
- 创建示例地址、订单与评论

注意：本脚本用于“开发/演示”场景的清库重建。
- 会清空数据库中的所有业务表数据；
- 会清空本地上传目录 backend/app/uploads（包括你手动上传的图片）。
  如果你希望保留手动上传图片，请自行修改 reset_uploads 的行为。

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
from typing import Optional

import os
import uuid
from datetime import datetime, timedelta

from .time_utils import now_cn_naive


def reset_all(db: Session):
    # =========================
    # 数据库清理（清库重建）
    # =========================
    # 说明：SQLite/SQLAlchemy 的 delete() 不会自动处理“非 ORM 级别 cascade 的历史数据”。
    # 因此我们在此显式逐表清理，确保多次运行 seed 不会出现“重复时间线/重复演示数据”。
    #
    # B4：订单状态时间线表（OrderStatusEvent）必须清理；
    #     否则每次 seed 会对同一个演示订单重复插入 timeline event（看起来像“重复创建映射”）。
    db.query(models.OrderStatusEvent).delete()

    # 其余表：为简单起见逐表清理
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


def reset_uploads():
    """清空本地上传目录（uploads）。

    目的：
    - 避免多次运行 seed 后，占位文件/图片在文件系统中不断累积；
    - 避免 sku_id 被复用时，旧目录残留导致你误以为“图片映射被重复创建”。

    风险：
    - 该操作会删除你手动在管理端上传的图片。
      你已确认可以接受“彻底清空 uploads，再手动重新上传”。
    """

    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    if not os.path.exists(uploads_dir):
        return

    # 递归删除 uploads_dir 下所有内容，但保留 uploads_dir 目录本身。
    # 仅用于演示/开发环境。
    for name in os.listdir(uploads_dir):
        p = os.path.join(uploads_dir, name)
        try:
            if os.path.isdir(p):
                # Python 3.8+ 可用 shutil.rmtree
                import shutil

                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
        except Exception:
            # 清理失败不应阻止 seed（例如文件占用）
            pass


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


def create_product_with_skus(
    db: Session,
    title: str,
    author: str,
    base_price: float,
    category_id: int,
    # 注意：新实现的图片只走 SKU 本地上传（sku.photos），此处保留参数仅用于 seed 生成文件。
    images: list[str],
    *,
    title_en: Optional[str] = None,
    author_en: Optional[str] = None,
    description_en: Optional[str] = None,
):
    prod = models.Product(
        title=title,
        title_en=title_en or title,
        author=author,
        author_en=author_en or author,
        base_price=base_price,
        description=f"《{title}》简介……",
        description_en=description_en or f"Introduction of {title}...",
        category_id=category_id,
        is_active=True,
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

    # 生成“本地上传”图片文件，并写入 sku.photos
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    def _write_dummy_image(sku_id: int, idx: int) -> str:
        """写入一个占位文件（不是真图片），用于演示 /uploads 静态路径与多图机制。

        注意：如果你希望在浏览器真实显示图片，请在管理端用“上传图片”功能上传 jpg/png。
        """

        sku_dir = os.path.join(uploads_dir, f"sku_{sku_id}")
        os.makedirs(sku_dir, exist_ok=True)
        filename = f"seed_{idx}_{uuid.uuid4().hex}.txt"
        abs_path = os.path.join(sku_dir, filename)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(f"seed placeholder for {title} sku {sku_id} image {idx}\n")
        return f"/uploads/sku_{sku_id}/{filename}"

    # 为每个 SKU 写入 2 个占位文件路径
    sku1.photos = json.dumps([_write_dummy_image(sku1.id, 1), _write_dummy_image(sku1.id, 2)], ensure_ascii=False)
    sku2.photos = json.dumps([_write_dummy_image(sku2.id, 1), _write_dummy_image(sku2.id, 2)], ensure_ascii=False)
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

    # 订单 + 时间线（B4）：演示 pending -> shipped -> completed
    # 注意：所有时间使用中国大陆时间（UTC+8）。
    created_at = now_cn_naive() - timedelta(days=1)
    shipped_at = created_at + timedelta(hours=4)
    completed_at = shipped_at + timedelta(hours=6)

    od = models.Order(
        order_id="ORDER99991231-001",
        user_id=user.id,
        address_id=addr.id,
        # 地址快照（A13）
        ship_receiver_name=addr.receiver_name,
        ship_phone=addr.phone,
        ship_province=addr.province,
        ship_city=addr.city,
        ship_district=addr.district,
        ship_detail_address=addr.detail_address,
        total_amount=unit_price,
        status="completed",
        created_at=created_at,
        shipped_at=shipped_at,
        completed_at=completed_at,
    )
    db.add(od)
    db.commit()
    db.refresh(od)

    # 时间线事件
    db.add_all(
        [
            models.OrderStatusEvent(order_id=od.order_id, status="pending", created_at=created_at),
            models.OrderStatusEvent(order_id=od.order_id, status="shipped", note="seed shipped", created_at=shipped_at),
            models.OrderStatusEvent(order_id=od.order_id, status="completed", note="seed completed", created_at=completed_at),
        ]
    )
    db.commit()

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
        # 清 uploads（文件系统层面），再清 DB（数据层面）
        # 顺序说明：先删文件再删 DB，避免极端情况下 DB 删除失败但文件已清空导致“不一致”。
        reset_uploads()
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
        # =========================
        # 扩充种子商品数量（A5：便于分页展示）
        # =========================
        # 前端当前分页 size=20，因此默认生成 >= 60 个商品，可展示至少 3 页。
        # 你可以通过环境变量 SEED_PRODUCT_COUNT 调整：
        # - Windows: set SEED_PRODUCT_COUNT=120
        # - macOS/Linux: export SEED_PRODUCT_COUNT=120
        try:
            product_count = int(os.environ.get("SEED_PRODUCT_COUNT", "60"))
        except Exception:
            product_count = 60
        product_count = max(1, product_count)

        # 保留 2 个“代表性商品”：用于演示双语字段、SKU（平装/精装）与多图机制
        featured_products: list[models.Product] = []
        featured_products.append(
            create_product_with_skus(
                db,
                "哈利波特与魔法石",
                "J.K.罗琳",
                49.0,
                cat1.id,
                imgs1,
                title_en="Harry Potter and the Philosopher's Stone",
                author_en="J.K. Rowling",
                description_en="The first book in the Harry Potter series.",
            )
        )
        featured_products.append(
            create_product_with_skus(
                db,
                "深入浅出计算机",
                "张三",
                59.0,
                cat2.id,
                imgs2,
                title_en="Computer Science Made Easy",
                author_en="Zhang San",
                description_en="An easy-to-understand introduction to computer science.",
            )
        )

        # 批量生成其余商品：使用简单模板生成，避免 seed 过长。
        # 说明：仍然创建平装/精装两个 SKU，并写入 2 个占位文件到 sku.photos。
        remaining = max(0, product_count - len(featured_products))
        for i in range(remaining):
            # 让 created_at 产生自然分布：越新的排在越前（配合 /api/products created_at desc）
            # 注意：我们不强行改 created_at 字段，交由 DB 默认即可；这里只用“名字/价格”区分。
            idx = i + 1
            title = f"演示图书 {idx:03d}"
            title_en = f"Demo Book {idx:03d}"
            author = "演示作者"
            author_en = "Demo Author"
            base_price = 20.0 + (idx % 30)
            cat_id = cat1.id if (idx % 2 == 0) else cat2.id
            create_product_with_skus(
                db,
                title,
                author,
                base_price,
                cat_id,
                imgs1 if (idx % 2 == 0) else imgs2,
                title_en=title_en,
                author_en=author_en,
                description_en=f"Introduction of {title_en}...",
            )

        # 用 featured_products[0] 生成一个演示订单与评论
        create_demo_order_and_review(db, user, featured_products[0])

        print("Seed completed. Admin: admin@demo.com / Admin1234, User: user@demo.com / User1234")
    finally:
        db.close()


if __name__ == "__main__":
    main()
