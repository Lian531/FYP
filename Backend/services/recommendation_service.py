'''
recommendation_service.py - Finds products that match the user's skin type and skin tone.

Skin tone is always one of: white, brown, or black.
Older tone values like 'fair', 'light', 'medium', 'tan', 'deep' are automatically
converted to the nearest matching value so recommendations still work.
'''

from sqlalchemy import or_
from models import db, Product

# Converts old tone names to the 3 values we use now
_TONE_MAP = {
    "fair":   "white",
    "light":  "white",
    "medium": "brown",
    "tan":    "brown",
    "deep":   "black",
    "white":  "white",
    "brown":  "brown",
    "black":  "black",
}


def get_recommendations(skin_type: str, skin_tone: str) -> list:
    '''
    Looks up products that match the user's skin type and skin tone.
    Products tagged as 'all' are always included regardless of the user's values.
    Returns a list of matching products sorted by category and name.
    '''
    product_tone = _TONE_MAP.get(skin_tone, "brown")   # default to brown if unknown

    return (
        Product.query
        .filter(
            or_(Product.skin_type == skin_type, Product.skin_type == "all"),
            or_(
                Product.skin_tone_target == product_tone,
                Product.skin_tone_target == "all",
            ),
        )
        .order_by(Product.category, Product.name)
        .all()
    )
