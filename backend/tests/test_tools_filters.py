from agent.tools import apply_filters
from agent.models import FilterSpec
import pandas as pd

# Helper to make a simple product catalog dataframe
def make_df():
    return pd.DataFrame([
        {"id": "a", "title": "Nike Tee", "description": "", "category": "t-shirt", "brand": "Nike", "price": 25.0, "currency": "USD", "image_url": "", "tags": "breathable,athletic"},
        {"id": "b", "title": "Adidas Tee", "description": "", "category": "t-shirt", "brand": "Adidas", "price": 30.0, "currency": "USD", "image_url": "", "tags": "athletic"},
        {"id": "c", "title": "Nike Hoodie", "description": "", "category": "hoodie", "brand": "Nike", "price": 45.0, "currency": "USD", "image_url": "", "tags": "warm"},
    ])

# Test various filtering scenarios
def test_filters_by_brand_and_category():
    df = make_df()
    f = FilterSpec(brand="Nike", category="t-shirt")
    out = apply_filters(df, f)
    assert list(out["id"]) == ["a"]

# Test price range filtering
def test_filters_by_price_range():
    df = make_df()
    f = FilterSpec(price_min=26, price_max=46)
    out = apply_filters(df, f)
    # items with price 30 and 45
    assert set(out["id"]) == {"b", "c"}

# Test filtering by tags
def test_filters_by_tags():
    df = make_df()
    f = FilterSpec(tags_contains="breathable")
    out = apply_filters(df, f)
    assert list(out["id"]) == ["a"]

