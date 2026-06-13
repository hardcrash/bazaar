# src/analysis/transformer.py

import logging
from src.core.models import MarketItem
from src.core.sanitation_schemas import EbayAPIItemSchema

logger = logging.getLogger("BazaarPipeline")

class MarketItemTransformer:
    @staticmethod
    def raw_ebay_json_to_market_item(item_json: dict, category: str, condition_id: int, is_sold: bool = False) -> MarketItem:
        """Transforms a volatile, raw eBay API JSON payload into a verified
        and sanitized MarketItem data contract model using Pydantic tracking.
        """
        # 1. Flatten the incoming API payload structure to meet our schema requirements
        price_obj = item_json.get("price", {})
        shipping_options = item_json.get("shippingOptions", [])
        seller_info = item_json.get("seller", {})
        image_info = item_json.get("image", {})

        shipping_val = "0.0"
        if shipping_options and isinstance(shipping_options, list):
            shipping_val = shipping_options[0].get("shippingCost", {}).get("value", "0.0")

        flattened_data = {
            "itemId": item_json.get("itemId"),
            "title": item_json.get("title", ""),
            "price": str(price_obj.get("value", "0.0")),
            "shippingCost": str(shipping_val),
            "conditionId": int(item_json.get("conditionId", condition_id)),
            "sellerUser": seller_info.get("username", "UNKNOWN_SELLER"),
            "feedbackScore": int(seller_info.get("feedbackScore", 0) or 0),
            "positiveFeedbackPercent": float(seller_info.get("positiveFeedbackPercent", 0.0) or 0.0)
        }

        # 2. Channel data through the Pydantic Sanitation Layer Gatekeeper
        try:
            sanitized_payload = EbayAPIItemSchema(**flattened_data)
        except Exception as validation_err:
            logger.error(f"❌ Structural Ingestion Drop: Payload failed sanitation parameters: {validation_err}")
            raise validation_err

        # 3. Safely map pristine data directly to our standardized tracking model
        # Explicit numeric typing casts here are bulletproof because Pydantic pre-verified them.
        price_num = float(sanitized_payload.price_string)
        shipping_num = float(sanitized_payload.shipping_string)

        return MarketItem(
            item_id=sanitized_payload.item_id,
            model_name="PENDING",
            category=category,
            raw_title=item_json.get("title", ""),
            title=sanitized_payload.title,
            price=price_num,
            shipping_cost=shipping_num,
            total_cost=price_num + shipping_num,
            currency=price_obj.get("currency", "USD"),
            condition_id=sanitized_payload.condition_id,
            is_sold=is_sold,
            source_platform="ebay",
            epid=item_json.get("epid"),
            buying_options=item_json.get("buyingOptions"),
            bid_count=item_json.get("bidCount"),
            item_end_date=item_json.get("itemEndDate"),
            seller_username=sanitized_payload.seller_username,
            feedback_score=sanitized_payload.feedback_score,
            image_url=image_info.get("imageUrl")
        )
