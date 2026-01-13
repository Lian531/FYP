'''
app.py - Main Flask application for the Lumière beauty recommendation system.
Run from the Backend folder: python app.py
'''

import os
import re
import uuid
import logging
from functools import wraps
from flask_sqlalchemy import SQLAlchemy

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from models import db, User, Product, SkinAnalysis, Recommendation, Order, OrderItem
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "Frontend", "Pages")
STATIC_DIR    = os.path.join(BASE_DIR, "..", "Frontend", "Static")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXT   = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
)
app.config["SQLALCHEMY_DATABASE_URI"]    = config.SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"]                 = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"]         = 10 * 1024 * 1024  # 10 MB

db.init_app(app)

# ---------------------------------------------------------------------------
# Helpers / decorators
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def valid_email(email: str) -> bool:
    return bool(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session or not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


def classify_skin_type(q1, q2, q3, q4):
    """
    Questionnaire logic:
      q1 = oily / shiny after a few hours
      q2 = tight / dry after washing
      q3 = frequent acne / breakouts
      q4 = redness / itching / irritation
    """
    if q4:
        return "sensitive"
    if q1 and q2:
        return "combination"
    if q1 or q3:
        return "oily"
    if q2:
        return "dry"
    return "normal"


# Adds the cart item count to every page so the navbar can show it
@app.context_processor
def inject_cart():
    cart = session.get("cart", {})
    return {"cart_count": sum(cart.values())}


# Handles common HTTP errors and shows a friendly message instead of a crash page
def _is_ajax():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json


@app.errorhandler(400)
def err_bad_request(e):
    if _is_ajax():
        return jsonify(success=False, error="Bad request."), 400
    flash("Bad request — please check your input.", "error")
    return redirect(request.referrer or url_for("home"))


@app.errorhandler(RequestEntityTooLarge)
@app.errorhandler(413)
def err_too_large(e):
    if _is_ajax():
        return jsonify(success=False, error="File too large. Maximum size is 10 MB."), 413
    flash("File too large. Maximum upload size is 10 MB.", "error")
    return redirect(request.referrer or url_for("upload"))


@app.errorhandler(404)
def err_not_found(e):
    if _is_ajax():
        return jsonify(success=False, error="Not found."), 404
    flash("Page not found.", "error")
    return redirect(url_for("home"))


@app.errorhandler(403)
def err_forbidden(e):
    if _is_ajax():
        return jsonify(success=False, error="Access denied."), 403
    flash("You do not have permission to access that page.", "error")
    return redirect(url_for("home"))


@app.errorhandler(500)
def err_server(e):
    db.session.rollback()
    logger.error("Internal server error: %s", e, exc_info=True)
    if _is_ajax():
        return jsonify(success=False, error="Something went wrong. Please try again."), 500
    flash("Something went wrong on our end. Please try again.", "error")
    return redirect(request.referrer or url_for("home"))


def _cart_items():
    '''Reads the cart from the session and returns each item with its product info and total price.'''
    cart  = session.get("cart", {})
    items = []
    for pid_str, qty in cart.items():
        product = db.session.get(Product, int(pid_str))
        if product:
            items.append({
                "product":    product,
                "quantity":   qty,
                "line_total": float(product.price or 0) * qty,
            })
    return items


# Public pages — no login required
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html")

        if not valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html")

        try:
            user = User.query.filter_by(email=email).first()
        except Exception:
            logger.exception("DB error during login")
            flash("A server error occurred. Please try again.", "error")
            return render_template("login.html")

        if user and check_password_hash(user.password, password):
            session["user_id"]   = user.id
            session["user_name"] = user.name
            session["is_admin"]  = user.is_admin
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for("admin") if user.is_admin else url_for("questionnaire"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        error = None
        if not name or not email or not password or not confirm:
            error = "All fields are required."
        elif len(name) < 2:
            error = "Name must be at least 2 characters."
        elif not valid_email(email):
            error = "Please enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."

        if not error:
            try:
                if User.query.filter_by(email=email).first():
                    error = "Email is already registered."
            except Exception:
                logger.exception("DB error checking email during registration")
                error = "A server error occurred. Please try again."

        if error:
            flash(error, "error")
        else:
            try:
                user = User(
                    name=name,
                    email=email,
                    password=generate_password_hash(password),
                )
                db.session.add(user)
                db.session.commit()
                session["user_id"]   = user.id
                session["user_name"] = user.name
                session["is_admin"]  = user.is_admin
                flash(f"Account created! Welcome, {user.name}!", "success")
                return redirect(url_for("questionnaire"))
            except Exception:
                db.session.rollback()
                logger.exception("DB error during registration")
                flash("Could not create account. Please try again.", "error")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# Pages that require the user to be logged in
@app.route("/questionnaire", methods=["GET", "POST"])
@login_required
def questionnaire():
    if request.method == "POST":
        try:
            q1 = int(request.form.get("q1", -1))
            q2 = int(request.form.get("q2", -1))
            q3 = int(request.form.get("q3", -1))
            q4 = int(request.form.get("q4", -1))
        except (ValueError, TypeError):
            flash("Invalid questionnaire response. Please answer all questions.", "error")
            return render_template("questionnaire.html")

        if any(q not in (0, 1) for q in (q1, q2, q3, q4)):
            flash("Please answer all four questions before continuing.", "error")
            return render_template("questionnaire.html")

        skin_type = classify_skin_type(q1, q2, q3, q4)
        session["skin_type"] = skin_type
        flash(f"Skin type detected: {skin_type.capitalize()}. Now upload your photo!", "success")
        return redirect(url_for("upload"))

    return render_template("questionnaire.html")


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    # Must complete questionnaire first
    if not session.get("skin_type"):
        flash("Please complete the skin questionnaire first.", "error")
        return redirect(url_for("questionnaire"))

    if request.method == "POST":
        if "photo" not in request.files:
            flash("No file selected. Please choose a photo.", "error")
            return redirect(request.url)

        file = request.files["photo"]
        if not file or file.filename == "":
            flash("No file selected. Please choose a photo.", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload a JPG, PNG, or WEBP image.", "error")
            return redirect(request.url)

        # Check the actual file type, not just the extension
        mime = file.content_type or ""
        if not mime.startswith("image/"):
            flash("Uploaded file does not appear to be a valid image.", "error")
            return redirect(request.url)

        # Give the file a unique name so uploads never overwrite each other
        ext      = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.save(filepath)
        except Exception:
            logger.exception("Failed to save uploaded file")
            flash("Could not save the uploaded file. Please try again.", "error")
            return redirect(request.url)

        # Make sure the photo actually has one face before doing anything else
        try:
            from services.image_service import validate_face, detect_skin_tone
            is_valid, face_error = validate_face(filepath)
        except Exception:
            logger.exception("Face validation crashed")
            if os.path.exists(filepath):
                os.remove(filepath)
            flash("Image processing failed. Please upload a clear face photo.", "error")
            return redirect(request.url)

        if not is_valid:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash(face_error, "error")
            return redirect(request.url)

        # Detect the skin tone from the uploaded photo
        try:
            skin_tone, _conf, tone_warning = detect_skin_tone(filepath)
            if tone_warning:
                flash(tone_warning, "warning")
        except Exception:
            logger.exception("Skin tone detection failed")
            skin_tone = "brown"   # safe fallback
        skin_type = session.get("skin_type", "normal")

        # Save the analysis result and product recommendations to the database
        try:
            analysis = SkinAnalysis(
                user_id        = session["user_id"],
                image_path     = filename,
                predicted_tone = skin_tone,
                skin_type      = skin_type,
            )
            db.session.add(analysis)

            from services.recommendation_service import get_recommendations
            products = get_recommendations(skin_type, skin_tone)
            for product in products:
                db.session.add(Recommendation(
                    user_id    = session["user_id"],
                    product_id = product.id,
                ))

            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("DB error saving skin analysis")
            flash("Analysis complete but results could not be saved. Please try again.", "error")
            return redirect(request.url)

        session["last_analysis_id"] = analysis.id
        session["skin_tone"]        = skin_tone

        return redirect(url_for("results"))

    return render_template("upload.html", skin_type=session.get("skin_type"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # Sends the user's uploaded photo to the browser
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/results")
@login_required
def results():
    analysis_id = session.get("last_analysis_id")
    if not analysis_id:
        flash("Please complete the skin analysis first.", "error")
        return redirect(url_for("questionnaire"))

    try:
        analysis = db.session.get(SkinAnalysis, analysis_id)
    except Exception:
        logger.exception("DB error fetching analysis")
        flash("Could not load your results. Please try again.", "error")
        return redirect(url_for("upload"))

    if not analysis or analysis.user_id != session["user_id"]:
        flash("Analysis not found. Please try again.", "error")
        return redirect(url_for("questionnaire"))

    try:
        from services.recommendation_service import get_recommendations
        products = get_recommendations(analysis.skin_type, analysis.predicted_tone)
    except Exception:
        logger.exception("Recommendation service failed")
        products = []

    by_category = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)

    _tone_norm = {
        "fair": "white", "light": "white",
        "medium": "brown", "tan": "brown",
        "deep": "black",
    }
    raw_tone  = analysis.predicted_tone or session.get("skin_tone") or ""
    skin_tone = _tone_norm.get(raw_tone, raw_tone) or ""

    return render_template(
        "results.html",
        analysis     = analysis,
        by_category  = by_category,
        skin_type    = analysis.skin_type,
        skin_tone    = skin_tone,
    )


# Shop, cart, and checkout pages — customer side only

@app.route("/shop")
@login_required
def shop():
        category  = request.args.get("category", "")
        search    = request.args.get("search",   "").strip()
        min_price = request.args.get("min_price", "")
        max_price = request.args.get("max_price", "")
        sort      = request.args.get("sort", "name")

        q = Product.query
        if category:
            q = q.filter(Product.category == category)
        if search:
            q = q.filter(
                Product.name.ilike(f"%{search}%") |
                Product.brand.ilike(f"%{search}%") |
                Product.description.ilike(f"%{search}%")
            )
        if min_price:
            try:
                q = q.filter(Product.price >= float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                q = q.filter(Product.price <= float(max_price))
            except ValueError:
                pass
        if sort == "price_asc":
            q = q.order_by(Product.price.asc())
        elif sort == "price_desc":
            q = q.order_by(Product.price.desc())
        elif sort == "name_desc":
            q = q.order_by(Product.name.desc())
        else:
            q = q.order_by(Product.name.asc())

        try:
            products   = q.all()
            categories = [r[0] for r in db.session.query(Product.category).distinct().all() if r[0]]
        except Exception:
            logger.exception("DB error in shop query")
            flash("Could not load products. Please try again.", "error")
            products, categories = [], []

        return render_template(
            "shop.html",
            products=products, categories=categories,
            current_category=category, current_search=search,
            current_sort=sort, min_price=min_price, max_price=max_price,
    )


@app.route("/product/<int:product_id>")
@login_required
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("shop"))
    return render_template("product_detail.html", product=product)


@app.route("/cart/add", methods=["POST"])
@login_required
def cart_add():
    product_id = request.form.get("product_id", type=int)
    quantity   = max(1, min(request.form.get("quantity", 1, type=int), 99))

    if not product_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": "Invalid product."}), 400
        flash("Invalid product.", "error")
        return redirect(url_for("shop"))

    product = db.session.get(Product, product_id)
    if not product:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": "Product not found."}), 404
        flash("Product not found.", "error")
        return redirect(url_for("shop"))

    cart          = session.get("cart", {})
    pid           = str(product_id)
    cart[pid]     = cart.get(pid, 0) + quantity
    session["cart"] = cart
    session.modified  = True

    count = sum(cart.values())
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "cart_count": count,
                        "message": f"{product.name} added to cart!"})

    flash(f"{product.name} added to cart!", "success")
    return redirect(request.referrer or url_for("shop"))


@app.route("/cart/update", methods=["POST"])
@login_required
def cart_update():
    product_id = str(request.form.get("product_id", ""))
    action     = request.form.get("action", "")
    quantity   = request.form.get("quantity", None, type=int)

    cart = session.get("cart", {})
    if product_id in cart:
        current = cart.get(product_id, 1)
        if action == "increase":
            cart[product_id] = min(current + 1, 99)
        elif action == "decrease":
            if current <= 1:
                cart.pop(product_id, None)
            else:
                cart[product_id] = current - 1
        elif quantity is not None:
            if quantity <= 0:
                cart.pop(product_id, None)
            else:
                cart[product_id] = min(quantity, 99)
    session["cart"]   = cart
    session.modified  = True
    return redirect(url_for("cart_view"))


@app.route("/cart/remove", methods=["POST"])
@login_required
def cart_remove():
    product_id = str(request.form.get("product_id", ""))
    cart       = session.get("cart", {})
    cart.pop(product_id, None)
    session["cart"]  = cart
    session.modified = True
    flash("Item removed from cart.", "success")
    return redirect(url_for("cart_view"))


@app.route("/cart")
@login_required
def cart_view():
    items    = _cart_items()
    subtotal = sum(i["line_total"] for i in items)
    return render_template("cart.html", items=items, subtotal=subtotal)


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if not session.get("cart"):
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart_view"))

    items = _cart_items()
    total = sum(i["line_total"] for i in items)

    if request.method == "POST":
        name    = request.form.get("name",    "").strip()
        email   = request.form.get("email",   "").strip()
        address = request.form.get("address", "").strip()
        phone   = request.form.get("phone",   "").strip()

        errors = []
        if not name:
            errors.append("Full name is required.")
        elif len(name) < 2:
            errors.append("Please enter your full name.")
        if not email:
            errors.append("Email address is required.")
        elif not valid_email(email):
            errors.append("Please enter a valid email address.")
        if not address:
            errors.append("Delivery address is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("checkout.html", items=items, total=total,
                                   prefill=request.form)

        try:
            order = Order(user_id=session["user_id"], name=name, email=email,
                          address=address, phone=phone, total=total, status="pending")
            db.session.add(order)
            db.session.flush()

            for item in items:
                db.session.add(OrderItem(
                    order_id=order.id, product_id=item["product"].id,
                    quantity=item["quantity"], unit_price=item["product"].price,
                ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("DB error placing order")
            flash("Could not place your order. Please try again.", "error")
            return render_template("checkout.html", items=items, total=total,
                                   prefill=request.form)

        session.pop("cart", None)
        session.modified = True

        return redirect(url_for("order_confirmation", order_id=order.id))

    u          = db.session.get(User, session["user_id"])
    user_email = u.email if u else ""
    return render_template("checkout.html", items=items, total=total,
                           prefill={"name": session.get("user_name", ""),
                                    "email": user_email})


@app.route("/order/<int:order_id>/confirmation")
@login_required
def order_confirmation(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.user_id != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("home"))
    return render_template("order_confirmation.html", order=order)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin():
    stats = {
        "total_users":    User.query.count(),
        "total_products": Product.query.count(),
        "total_analyses": SkinAnalysis.query.count(),
        "total_recs":     Recommendation.query.count(),
    }
    users    = User.query.order_by(User.created_at.desc()).all()
    products = Product.query.order_by(Product.category).all()
    analyses = (
        SkinAnalysis.query
        .order_by(SkinAnalysis.created_at.desc())
        .limit(15)
        .all()
    )
    return render_template(
        "admin.html",
        stats=stats, users=users, products=products, analyses=analyses,
    )


PRODUCT_IMG_FOLDER = os.path.join(STATIC_DIR, "images", "products")
os.makedirs(PRODUCT_IMG_FOLDER, exist_ok=True)


@app.route("/admin/products/add", methods=["POST"])
@admin_required
def admin_add_product():
    name     = request.form.get("name",     "").strip()
    category = request.form.get("category", "").strip()
    price_raw = request.form.get("price",   "").strip()

    if not name:
        flash("Product name is required.", "error")
        return redirect(url_for("admin"))
    if not category:
        flash("Product category is required.", "error")
        return redirect(url_for("admin"))

    price = None
    if price_raw:
        try:
            price = float(price_raw)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Price must be a valid positive number.", "error")
            return redirect(url_for("admin"))

    image_url  = None
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        if not allowed_file(image_file.filename):
            flash("Product image must be a JPG, PNG, or WEBP file.", "error")
            return redirect(url_for("admin"))
        try:
            ext      = image_file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            image_file.save(os.path.join(PRODUCT_IMG_FOLDER, filename))
            image_url = f"images/products/{filename}"
        except Exception:
            logger.exception("Failed to save product image")
            flash("Image upload failed. Product not saved.", "error")
            return redirect(url_for("admin"))

    try:
        product = Product(
            name             = name,
            brand            = request.form.get("brand", "").strip(),
            category         = category,
            skin_type        = request.form.get("skin_type", "all"),
            skin_tone_target = request.form.get("skin_tone", "all"),
            description      = request.form.get("description", "").strip(),
            image_url        = image_url,
            price            = price,
        )
        db.session.add(product)
        db.session.commit()
        flash("Product added successfully!", "success")
    except Exception:
        db.session.rollback()
        logger.exception("DB error adding product")
        flash("Could not add product. Please try again.", "error")

    return redirect(url_for("admin"))


@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin"))

    if request.method == "GET":
        return render_template("edit_product.html", product=product)

    # POST — update
    name      = request.form.get("name",     "").strip()
    category  = request.form.get("category", "").strip()
    tone_raw  = request.form.get("skin_tone_target", "").strip().lower()

    if not name:
        flash("Product name is required.", "error")
        return render_template("edit_product.html", product=product)
    if not category:
        flash("Product category is required.", "error")
        return render_template("edit_product.html", product=product)

    VALID_TONES = {"white", "brown", "black"}
    skin_tone = tone_raw if tone_raw in VALID_TONES else "brown"

    price_raw = request.form.get("price", "").strip()
    price = None
    if price_raw:
        try:
            price = float(price_raw)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Price must be a valid positive number.", "error")
            return render_template("edit_product.html", product=product)

    stock_raw = request.form.get("stock", "").strip()
    stock = None
    if stock_raw:
        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash("Stock must be a non-negative integer.", "error")
            return render_template("edit_product.html", product=product)

    try:
        product.name             = name
        product.brand            = request.form.get("brand", "").strip()
        product.category         = category
        product.skin_type        = request.form.get("skin_type", "all")
        product.skin_tone_target = skin_tone
        product.description      = request.form.get("description", "").strip()
        product.price            = price
        product.stock            = stock
        image_url_input = request.form.get("image_url", "").strip()
        if image_url_input:
            product.image_url = image_url_input
        db.session.commit()
        flash("Product updated successfully!", "success")
    except Exception:
        db.session.rollback()
        logger.exception("DB error updating product %s", product_id)
        flash("Could not update product. Please try again.", "error")
        return render_template("edit_product.html", product=product)

    return redirect(url_for("admin"))


@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@admin_required
def admin_delete_product(product_id):
    try:
        product = db.session.get(Product, product_id)
        if product:
            Recommendation.query.filter_by(product_id=product_id).delete()
            db.session.delete(product)
            db.session.commit()
            flash("Product deleted.", "success")
        else:
            flash("Product not found.", "error")
    except Exception:
        db.session.rollback()
        logger.exception("DB error deleting product %s", product_id)
        flash("Could not delete product. Please try again.", "error")
    return redirect(url_for("admin"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin"))
    try:
        user = db.session.get(User, user_id)
        if user:
            Recommendation.query.filter_by(user_id=user_id).delete()
            SkinAnalysis.query.filter_by(user_id=user_id).delete()
            db.session.delete(user)
            db.session.commit()
            flash("User deleted.", "success")
        else:
            flash("User not found.", "error")
    except Exception:
        db.session.rollback()
        logger.exception("DB error deleting user %s", user_id)
        flash("Could not delete user. Please try again.", "error")
    return redirect(url_for("admin"))


# Admin CLI command to set up the database tables
@app.cli.command("init-db")
def init_db_command():
    # Creates all database tables. Run with: flask --app app init-db
    db.create_all()
    print("Database tables created successfully.")


@app.route("/session-debug")
def session_debug():
    if not session:
        return """
        <html><body style="font-family:sans-serif;padding:2rem;background:#fff8f5;">
        <h2 style="color:#c0392b;">&#x26A0; No Active Session</h2>
        <p style="color:#555;">Please <a href="/login">login</a> to start a session.</p>
        </body></html>
        """
    rows = "".join(
        f"<tr><td style='padding:8px 16px;border:1px solid #ddd;font-weight:600;'>{k}</td>"
        f"<td style='padding:8px 16px;border:1px solid #ddd;'>{v}</td></tr>"
        for k, v in session.items()
    )
    return f"""
    <html><body style="font-family:sans-serif;padding:2rem;background:#fff8f5;">
    <h2 style="color:#2e7d32;">&#x2705; Active Session</h2>
    <table style="border-collapse:collapse;min-width:400px;">
      <tr style="background:#c8a882;color:#fff;">
        <th style="padding:8px 16px;border:1px solid #ddd;">Key</th>
        <th style="padding:8px 16px;border:1px solid #ddd;">Value</th>
      </tr>
      {rows}
    </table>
    <p style="margin-top:1rem;"><a href="/logout">Logout</a></p>
    </body></html>
    """


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)