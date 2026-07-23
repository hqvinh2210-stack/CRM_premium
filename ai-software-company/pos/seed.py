from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pos.db import SessionLocal, init_db
from pos.models.auth import Role, Store, User, UserStoreRole
from pos.models.catalog import Category, Product, StockLevel
from pos.models.customers import Customer
from pos.models.loyalty import LoyaltyProgram, Reward
from pos.models.promo import PromoType, Promotion
from pos.security import hash_password


def seed(db: Session | None = None) -> dict:
    close = False
    if db is None:
        init_db()
        db = SessionLocal()
        close = True
    try:
        store = db.query(Store).filter(Store.code == "MAIN").first()
        if not store:
            store = Store(code="MAIN", name="Cua hang chinh", address="HCM")
            db.add(store)
            db.flush()

        admin = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin:
            admin = User(
                email="admin@example.com",
                phone="0900000001",
                full_name="Admin POS",
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            db.flush()

        cashier = db.query(User).filter(User.email == "cashier@example.com").first()
        if not cashier:
            cashier = User(
                email="cashier@example.com",
                phone="0900000002",
                full_name="Thu ngan",
                password_hash=hash_password("cashier123"),
            )
            db.add(cashier)
            db.flush()

        for user, role in ((admin, Role.admin), (cashier, Role.cashier)):
            link = (
                db.query(UserStoreRole)
                .filter(UserStoreRole.user_id == user.id, UserStoreRole.store_id == store.id)
                .first()
            )
            if not link:
                db.add(UserStoreRole(user_id=user.id, store_id=store.id, role=role))

        cat = db.query(Category).filter(Category.name == "Do uong").first()
        if not cat:
            cat = Category(name="Do uong")
            db.add(cat)
            db.flush()

        products_spec = [
            ("CF-DEN", "Ca phe den", "8901001", Decimal("25000"), 100),
            ("CF-SUA", "Ca phe sua", "8901002", Decimal("30000"), 100),
            ("TRA-DA", "Tra da", "8901003", Decimal("15000"), 50),
            ("BANH-MI", "Banh mi thit", "8902001", Decimal("20000"), 40),
        ]
        for sku, name, barcode, price, qty in products_spec:
            p = db.query(Product).filter(Product.sku == sku).first()
            if not p:
                p = Product(
                    sku=sku,
                    name=name,
                    barcode=barcode,
                    price=price,
                    cost=price * Decimal("0.5"),
                    category_id=cat.id,
                    track_inventory=True,
                )
                db.add(p)
                db.flush()
            stock = (
                db.query(StockLevel)
                .filter(StockLevel.store_id == store.id, StockLevel.product_id == p.id)
                .first()
            )
            if not stock:
                db.add(StockLevel(store_id=store.id, product_id=p.id, qty=qty))

        cust = db.query(Customer).filter(Customer.phone == "0912345678").first()
        if not cust:
            db.add(Customer(phone="0912345678", name="Khach VIP", notes="Demo customer"))

        if not db.query(LoyaltyProgram).filter(LoyaltyProgram.is_active.is_(True)).first():
            db.add(
                LoyaltyProgram(
                    name="CRM Premium Points",
                    earn_rate=Decimal("0.01"),
                    redeem_value=Decimal("100"),
                )
            )
        if not db.query(Reward).first():
            db.add(Reward(name="Giam 10k", points_cost=100, description="Redeem 100 diem"))
            db.add(Reward(name="Giam 50k", points_cost=500, description="Redeem 500 diem"))

        if not db.query(Promotion).filter(Promotion.code == "SALE10").first():
            db.add(
                Promotion(
                    name="Giam 10% toan don",
                    code="SALE10",
                    promo_type=PromoType.percent,
                    value=Decimal("10"),
                    min_subtotal=Decimal("0"),
                )
            )
        if not db.query(Promotion).filter(Promotion.code == "FIX15").first():
            db.add(
                Promotion(
                    name="Giam co dinh 15k",
                    code="FIX15",
                    promo_type=PromoType.fixed,
                    value=Decimal("15000"),
                    min_subtotal=Decimal("50000"),
                )
            )

        db.commit()
        return {
            "store_id": store.id,
            "admin_email": "admin@example.com",
            "admin_password": "admin123",
            "cashier_email": "cashier@example.com",
            "cashier_password": "cashier123",
        }
    finally:
        if close:
            db.close()


if __name__ == "__main__":
    print(seed())
