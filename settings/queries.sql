-- name: insert_harvested_item
INSERT OR IGNORE INTO harvested_market_items (
    item_id, model_name, category, raw_title, title, price, shipping_cost, total_cost,
    currency, condition_id, is_sold, source_platform, date_listed,
    epid, buying_options, bid_count, item_end_date, seller_username, feedback_score, image_url
) VALUES (
    :item_id, :model_name, :category, :raw_title, :title, :price, :shipping_cost, :total_cost,
    :currency, :condition_id, :is_sold, :source_platform, :date_listed,
    :epid, :buying_options, :bid_count, :item_end_date, :seller_username, :feedback_score, :image_url
);

-- name: get_harvested_items_by_category
SELECT * FROM harvested_market_items
WHERE category = :category;

-- name: insert_historical_metrics
INSERT OR REPLACE INTO historical_metrics (
    model_name, timeframe, condition_type, total_units, min_item_price,
    max_item_price, avg_item_price, med_item_price, avg_shipping_cost, avg_total_cost
) VALUES (
    :model_name, :timeframe, :condition_type, :total_units, :min_item_price,
    :max_item_price, :avg_item_price, :med_item_price, :avg_shipping_cost, :avg_total_cost
);
