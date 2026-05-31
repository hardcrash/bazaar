import sqlite3
import logging
from check_db import normalize_model_name  # Reusing our core normalization utility

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

def validate_metrics_payload(payload):
    """
    Validates the data fields.
    Returns (True, cleaned_payload) if safe, or (False, reason) if corrupted.
    """
    try:
        # 1. Normalize name and timeframe
        model_name = normalize_model_name(payload.get('model_name'))
        timeframe = standardize_timeframe(payload.get('timeframe'))
        condition = str(payload.get('condition_type', '')).strip().lower()

        # 2. Extract and cast numbers safely
        total_units = int(payload.get('total_units', 0))
        avg_price = float(payload.get('avg_item_price', 0.0))
        avg_shipping = float(payload.get('avg_shipping_cost', 0.0))
        avg_total = float(payload.get('avg_total_cost', 0.0))

        # --- VALIDATION RULES ---
        if model_name == "Unknown":
            return False, "Missing or unparseable model name"

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

def ingest_historical_metrics(cursor, raw_payloads):
    """
    Processes, sanitizes, and inserts batch records safely.
    Expects an active sqlite3 cursor and a list of dictionaries.
    """
    success_count = 0
    skipped_count = 0

    insert_query = """
        INSERT INTO historical_metrics (
            model_name, timeframe, condition_type, total_units,
            avg_item_price, avg_shipping_cost, avg_total_cost
        ) VALUES (
            :model_name, :timeframe, :condition_type, :total_units,
            :avg_item_price, :avg_shipping_cost, :avg_total_cost
        )
        ON CONFLICT(model_name, timeframe, condition_type) DO UPDATE SET
            total_units = total_units + excluded.total_units,
            avg_item_price = round(((avg_item_price * total_units) + (excluded.avg_item_price * excluded.total_units)) / (total_units + excluded.total_units), 2),
            avg_shipping_cost = round(((avg_shipping_cost * total_units) + (excluded.avg_shipping_cost * excluded.total_units)) / (total_units + excluded.total_units), 2),
            avg_total_cost = round(((avg_total_cost * total_units) + (excluded.avg_total_cost * excluded.total_units)) / (total_units + excluded.total_units), 2);
    """

    for idx, raw_data in enumerate(raw_payloads):
        is_valid, clean_data = validate_metrics_payload(raw_data)

        if is_valid:
            cursor.execute(insert_query, clean_data)
            success_count += 1
        else:
            logging.warning(f"Row {idx} rejected from entry. Reason: {clean_data}")
            skipped_count += 1

    print(f"\n📥 INGESTION BATCH COMPLETE | Saved: {success_count} | Dropped: {skipped_count}")
    return success_count, skipped_count
