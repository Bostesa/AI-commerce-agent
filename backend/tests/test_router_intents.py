from agent.router import classify_intent, extract_filters_rules

# 1. Text-only query
def test_intent_text():
    assert classify_intent("recommend breathable t-shirt under $30", has_image=False) == "TEXT_RECOMMEND"

# Image-only query
def test_intent_image():
    assert classify_intent("", has_image=True) == "IMAGE_SEARCH"

# Combined image and text query
def test_intent_image_and_text():
    assert classify_intent("like this but cheaper", has_image=True) == "IMAGE_AND_TEXT"

# Test filter extraction
def test_filter_rules_brand_price_category():
    f = extract_filters_rules("nike breathable t-shirt under $25")
    assert f.brand == "Nike"
    assert f.category == "t-shirt"
    assert f.price_max == 25.0
