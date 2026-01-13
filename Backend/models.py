from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    analyses        = db.relationship("SkinAnalysis",   backref="user", lazy=True)
    recommendations = db.relationship("Recommendation", backref="user", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(150), nullable=False)
    brand            = db.Column(db.String(100))
    category         = db.Column(db.String(50))   # Foundation | Face Wash | Moisturizer | Sunscreen | Concealer | Lipstick | Powder
    skin_type        = db.Column(db.String(50))   # oily | dry | normal | combination | sensitive | all
    skin_tone_target = db.Column(db.String(20))   # white | brown | black | all
    description      = db.Column(db.Text)
    image_url        = db.Column(db.String(255), nullable=True)
    price            = db.Column(db.Numeric(10, 2))
    stock            = db.Column(db.Integer, nullable=True)  # NULL treated as "in stock"
    created_at       = db.Column(db.DateTime(timezone=True), default=_now)

    recommendations = db.relationship("Recommendation", backref="product", lazy=True)


class SkinAnalysis(db.Model):
    __tablename__ = "skin_tone_results"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    image_path     = db.Column(db.String(255))
    predicted_tone = db.Column(db.String(20))
    confidence     = db.Column(db.Numeric(5, 2))
    skin_type      = db.Column(db.String(50))
    created_at     = db.Column(db.DateTime(timezone=True), default=_now)


class Recommendation(db.Model):
    __tablename__ = "recommendations"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)


class Order(db.Model):
    __tablename__ = "orders"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name       = db.Column(db.String(150), nullable=False)
    email      = db.Column(db.String(150), nullable=False)
    address    = db.Column(db.Text, nullable=False)
    phone      = db.Column(db.String(30))
    total      = db.Column(db.Numeric(10, 2))
    status     = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    items = db.relationship("OrderItem", backref="order", lazy=True,
                            cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey("orders.id"),   nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2))  # price captured at order time
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    product = db.relationship("Product")
