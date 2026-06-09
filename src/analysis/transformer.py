import logging
from src.core.models import MarketItem

logger = logging.getLogger("BazaarPipeline")

class MarketItemTransformer:
    @staticmethod
    def raw_ebay_json_to_market_item(item_json: dict, category: str, condition_id: int, is_sold: bool = False) -> MarketItem:
        raw_title = item_json.get("title", "")

        try:
            price = float(item_json.get("price", {}).get("value", 0.0))
        except (ValueError, TypeError):
            price = 0.0

        shipping_options = item_json.get("shippingOptions", [])
        shipping = 0.0
        if shipping_options and isinstance(shipping_options, list):
            try:
                shipping = float(shipping_options[0].get("shippingCost", {}).get("value", 0.0))
            except (ValueError, TypeError, IndexError):
                shipping = 0.0

        seller_info = item_json.get("seller", {})
        image_info = item_json.get("image", {})

        return MarketItem(
            item_id=item_json.get("itemId"),
            model_name="PENDING",
            category=category,
            raw_title=raw_title,
            title=raw_title.strip(),
            price=price,
            shipping_cost=shipping,
            total_cost=price + shipping,
            currency=item_json.get("price", {}).get("currency", "USD"),
            condition_id=condition_id,
            is_sold=is_sold, # 🌟 Track historical solds accurately
            source_platform="ebay",
            epid=item_json.get("epid"),
            buying_options=item_json.get("buyingOptions"),
            bid_count=item_json.get("bidCount"),
            item_end_date=item_json.get("itemEndDate"),
            seller_username=seller_info.get("username"),
            feedback_score=seller_info.get("feedbackScore"),
            image_url=image_info.get("imageUrl")
        )
