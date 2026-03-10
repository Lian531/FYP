'''
seed_products.py - Adds sample products to the database for testing.

Run from Backend/:
    python seed_products.py

Adds 20+ products across 7 categories. Safe to run more than once —
it will skip any product that already exists in the database.
'''

import sys
import os

# Make sure Python can find the app and models when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Product

PRODUCTS = [
    # ── Foundation ──────────────────────────────────────────────────────────
    dict(name="Flawless Cover Foundation",   brand="Lumiere Luxe",
         category="Foundation", skin_type="dry",         skin_tone_target="white",
         price=32.99, stock=50,
         description="Lightweight, buildable coverage with a dewy finish. Enriched with "
                     "hyaluronic acid to keep fair skin hydrated all day. SPF 20."),
    dict(name="Radiance Glow Foundation",    brand="Lumiere Pro",
         category="Foundation", skin_type="oily",        skin_tone_target="brown",
         price=29.99, stock=45,
         description="Oil-control formula with a semi-matte finish. Warm undertones suit "
                     "medium-to-tan skin beautifully. Lasts 16 hours."),
    dict(name="Deep Velvet Foundation",      brand="Lumiere Luxe",
         category="Foundation", skin_type="normal",      skin_tone_target="black",
         price=34.99, stock=30,
         description="Full-coverage, skin-nourishing formula developed for deep skin tones. "
                     "Rich pigments eliminate ashiness. Wear time 18 hours."),
    dict(name="Natural Matte Foundation",    brand="Lumiere Essentials",
         category="Foundation", skin_type="combination", skin_tone_target="all",
         price=27.99, stock=60,
         description="Shine-control foundation for combination skin. Available in 40 shades. "
                     "Buildable from light to full coverage."),

    # ── Face Wash ───────────────────────────────────────────────────────────
    dict(name="Gentle Foam Cleanser",        brand="Lumiere Naturals",
         category="Face Wash",  skin_type="oily",        skin_tone_target="all",
         price=18.99, stock=80,
         description="Sulfate-free foaming cleanser that removes excess oil without stripping "
                     "the skin's natural moisture barrier. Infused with green tea extract."),
    dict(name="Hydrating Cream Wash",        brand="Lumiere Naturals",
         category="Face Wash",  skin_type="dry",         skin_tone_target="all",
         price=21.99, stock=70,
         description="Creamy, non-foaming cleanser that melts away impurities while "
                     "leaving skin feeling soft and nourished. Suitable for sensitive dry skin."),
    dict(name="Calming Oat Cleanser",        brand="Lumiere Naturals",
         category="Face Wash",  skin_type="sensitive",   skin_tone_target="all",
         price=24.99, stock=65,
         description="Fragrance-free, hypoallergenic oat-milk cleanser that soothes redness "
                     "and calms reactive skin. Dermatologist tested."),

    # ── Moisturizer ─────────────────────────────────────────────────────────
    dict(name="Luminous Day Cream",          brand="Lumiere Luxe",
         category="Moisturizer",skin_type="normal",      skin_tone_target="white",
         price=39.99, stock=55,
         description="Lightweight day cream with vitamin C and niacinamide to brighten fair "
                     "skin and reduce the appearance of redness. SPF 15."),
    dict(name="Rich Hydra Complex",          brand="Lumiere Pro",
         category="Moisturizer",skin_type="dry",         skin_tone_target="all",
         price=44.99, stock=40,
         description="Intensely hydrating cream with ceramides and shea butter. Repairs the "
                     "skin barrier overnight and leaves all tones with a healthy glow."),
    dict(name="Oil-Control Fluid",           brand="Lumiere Pro",
         category="Moisturizer",skin_type="oily",        skin_tone_target="all",
         price=36.99, stock=50,
         description="Weightless gel-fluid moisturiser that controls shine for up to 12 hours. "
                     "Non-comedogenic formula safe for all skin tones."),
    dict(name="Barrier Repair Balm",         brand="Lumiere Naturals",
         category="Moisturizer",skin_type="sensitive",   skin_tone_target="all",
         price=41.99, stock=35,
         description="Ultra-gentle balm formulated with colloidal oatmeal and allantoin. "
                     "Rebuilds the skin barrier and reduces irritation on sensitive skin."),

    # ── Sunscreen ───────────────────────────────────────────────────────────
    dict(name="Invisible Shield SPF50",      brand="Lumiere Pro",
         category="Sunscreen",  skin_type="all",         skin_tone_target="white",
         price=25.99, stock=90,
         description="Ultra-sheer mineral SPF50 that leaves no white cast on fair skin. "
                     "Water-resistant for 80 minutes. PA++++ broad spectrum."),
    dict(name="Tinted Sun Guard SPF40",      brand="Lumiere Pro",
         category="Sunscreen",  skin_type="all",         skin_tone_target="brown",
         price=28.99, stock=75,
         description="Tinted mineral sunscreen with a warm bronze tint that enhances medium "
                     "and olive skin. Antioxidant-rich formula for daily protection."),
    dict(name="Deep Glow SPF50+",            brand="Lumiere Luxe",
         category="Sunscreen",  skin_type="all",         skin_tone_target="black",
         price=31.99, stock=60,
         description="High-protection SPF50+ with a luminous finish formulated specifically "
                     "to blend seamlessly on deep skin tones. Zero white cast."),

    # ── Concealer ───────────────────────────────────────────────────────────
    dict(name="Perfect Cover Stick",         brand="Lumiere Essentials",
         category="Concealer",  skin_type="all",         skin_tone_target="all",
         price=19.99, stock=85,
         description="Creamy concealer stick with full coverage and a natural finish. "
                     "Available in 30 shades from porcelain to ebony."),
    dict(name="Full Coverage Pot",           brand="Lumiere Pro",
         category="Concealer",  skin_type="all",         skin_tone_target="black",
         price=22.99, stock=60,
         description="High-pigment pot concealer developed for deep skin tones. "
                     "Covers hyperpigmentation, dark spots, and blemishes effortlessly."),

    # ── Lipstick ────────────────────────────────────────────────────────────
    dict(name="Nude Rose Lip",               brand="Lumiere Luxe",
         category="Lipstick",   skin_type="all",         skin_tone_target="white",
         price=16.99, stock=100,
         description="Soft rose-nude long-lasting lipstick that flatters fair skin. "
                     "Moisturising formula with vitamin E. Lasts 8 hours."),
    dict(name="Warm Terracotta Lip",         brand="Lumiere Luxe",
         category="Lipstick",   skin_type="all",         skin_tone_target="brown",
         price=16.99, stock=100,
         description="Earthy terracotta shade that pops beautifully on medium and olive skin. "
                     "Creamy finish with 8-hour wear."),
    dict(name="Berry Deep Lip",              brand="Lumiere Luxe",
         category="Lipstick",   skin_type="all",         skin_tone_target="black",
         price=16.99, stock=100,
         description="Rich berry-plum shade crafted for deep skin tones. Bold pigment "
                     "with a satin finish and conditioning vitamin E complex."),

    # ── Powder ──────────────────────────────────────────────────────────────
    dict(name="Translucent Setting Powder",  brand="Lumiere Pro",
         category="Powder",     skin_type="oily",        skin_tone_target="white",
         price=23.99, stock=70,
         description="Finely milled translucent powder that sets makeup and controls shine "
                     "on fair skin without adding visible colour. Silky, skin-soft finish."),
    dict(name="Bronzed Finish Powder",       brand="Lumiere Essentials",
         category="Powder",     skin_type="all",         skin_tone_target="brown",
         price=26.99, stock=65,
         description="Warm bronzing powder that adds sun-kissed definition to medium "
                     "and tan skin. Buildable shimmer for day-to-night looks."),
    dict(name="Deep Setting Powder",         brand="Lumiere Pro",
         category="Powder",     skin_type="all",         skin_tone_target="black",
         price=24.99, stock=55,
         description="Rich-toned loose setting powder that eliminates flashback and "
                     "keeps deep skin tones looking flawless under all lighting."),
]


def run_stock_migration():
    '''Adds the stock column to the products table if it is not there yet.'''
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE products ADD COLUMN stock INT NULL"
            ))
            conn.commit()
        print("  Migration: 'stock' column added to products.")
    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err or "already exists" in err or "1060" in err:
            pass  # column already exists -- fine
        else:
            print(f"  Migration note: {e}")


def seed():
    with app.app_context():
        db.create_all()
        run_stock_migration()

        added = 0
        for data in PRODUCTS:
            if not Product.query.filter_by(name=data["name"]).first():
                db.session.add(Product(**data))
                added += 1

        db.session.commit()
        total = Product.query.count()
        print(f"Done. Added {added} new products. Total in DB: {total}.")


if __name__ == "__main__":
    seed()
