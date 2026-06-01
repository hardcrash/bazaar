import sqlite3
import logging

# Configure logging for tracking rejected data
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def standardize_timeframe(tf_string):
    """Maps varied timeframe formats to strict schema definitions."""
    if not tf_string:
        return "unknown"

    tf_clean = str(tf_string).strip().lower()

    mapping = {
        '1m': 'past_month',
        'month': 'past_month',
        'past_month': 'past_month',
        '1y': 'past_year',
        'year': 'past_year',
        'past_year': 'past_year'
    }

    return mapping.get(tf_clean, tf_clean)

# 🛠️ Fixed: Removed 'normalize_model_name' import from check_db.py entirely.
# Passed valid_categories down dynamically to isolate the boundary checks.
def validate_metrics_payload(payload, valid_categories=None):
    """
    Validates the data fields against dynamic runtime configuration constraints.
    Returns (True, cleaned_payload) if safe, or (False, reason) if corrupted.
    """
    try:
        # 1. Cast keys cleanly
        model_name = str(payload.get('model_name', '')).strip()
        timeframe = standardize_timeframe(payload.get('timeframe'))
        condition = str(payload.get('condition_type', '')).strip().lower()
        category = payload.get('category')  # Track incoming category cleanly

        # 2. Extract and cast numbers safely
        total_units = int(payload.get('total_units', 0))
        avg_price = float(payload.get('avg_item_price', 0.0))
        avg_shipping = float(payload.get('avg_shipping_cost', 0.0))
        avg_total = float(payload.get('avg_total_cost', 0.0))

        # --- MODULAR VALIDATION RULES ---
        if not model_name or model_name.lower() in ["unknown", ""]:
            return False, "Missing or unparseable model name"

        # 🌟 Dynamic Category Lookups (Slamming the door on hardcoded strings)
        if valid_categories and category not in valid_categories:
            return False, f"Category '{category}' is not approved in runtime market configuration"

        if timeframe not in ['past_month', 'past_year']:
            return False, f"Unsupported timeframe token: '{timeframe}'"

        if condition not in ['working', 'broken']:
            return False, f"Invalid condition classification: '{condition}'"

        if total_units <= 0:
            return False, f"Invalid transaction volume: {total_units} units"

        if avg_price < 0 or avg_shipping < 0 or avg_total <= 0:
            return False, "Negative prices or invalid total costs detected"

        # Return the sanitized, strictly typed package
        return True, {
            'model_name': model_name,
            'timeframe': timeframe,
            'condition_type': condition,
            'total_units': total_units,
            'avg_item_price': avg_price,
            'avg_shipping_cost': avg_shipping,
            'avg_total_cost': avg_total
        }

    except (ValueError, TypeError) as err:
        return False, f"Data type parsing mismatch: {str(err)}"

def ingest_historical_metrics(cursor, raw_payloads, allowed_categories=None):
    """
    Processes, sanitizes, and inserts batch records safely.
    Expects an active sqlite3 cursor, a list of dictionaries, and dynamic valid categories.
    """
    success_count = 0
    skipped_count = 0

    # Safely format categories to an immutable lookup set
    category_set = set(allowed_categories) if allowed_categories else None

    # Note: Updated upsert query matches your fresh DashboardAggregator logic
    insert_query = """
        INSERT INTO historical_metrics (
            model_name, timeframe, condition_type, total_units,
            avg_item_price, avg_shipping_cost, avg_total_cost
        ) VALUES (
            :model_name, :timeframe, :condition_type, :total_units,
            :avg_item_price, :avg_shipping_cost, :avg_total_cost
        )
        ON CONFLICT(model_name, timeframe, condition_type) DO UPDATE SET
            total_units = excluded.total_units,
            avg_item_price = excluded.avg_item_price,
            avg_shipping_cost = excluded.avg_shipping_cost,
            avg_total_cost = excluded.avg_total_cost;
    """

    for idx, raw_data in enumerate(raw_payloads):
        # Pass the dynamic categories config file list down to validation layer
        is_valid, clean_data = validate_metrics_payload(raw_data, valid_categories=category_set)

        if is_valid:
            cursor.execute(insert_query, clean_data)
            success_count += 1
        else:
            logging.warning(f"Row {idx} rejected from entry. Reason: {clean_data}")
            skipped_count += 1

    print(f"\n📥 INGESTION BATCH COMPLETE | Saved: {success_count} | Dropped: {skipped_count}")
    return success_count, skipped_count
