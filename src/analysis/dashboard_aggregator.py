import sqlite3
from datetime import datetime
# Inject Option B interceptor methods
from src.analysis.ingest_pipeline import validate_metrics_payload

class DashboardAggregator:
    def __init__(self, db_path="bazaar.db"):
        self.db_path = db_path

    def calculate_historical_metrics(self, model_name, timeframe='past_month'):
        """
        Computes true segmented time series windows over data snapshots
        and runs them through a pre-commit validation layer.
        """
        date_modifier = "-30 days" if timeframe == 'past_month' else "-395 days"
        conditions = {'working': 3000, 'broken': 7000}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Robust math-aware Upsert query to protect UNIQUE key constraints safely
                upsert_query = """
                    INSERT INTO historical_metrics (
                        model_name, timeframe, condition_type, total_units,
                        min_item_price, max_item_price, avg_item_price,
                        avg_shipping_cost, avg_total_cost, last_updated
                    ) VALUES (
                        :model_name, :timeframe, :condition_type, :total_units,
                        :min_item_price, :max_item_price, :avg_item_price,
                        :avg_shipping_cost, :avg_total_cost, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(model_name, timeframe, condition_type) DO UPDATE SET
                        total_units = total_units + excluded.total_units,
                        min_item_price = MIN(min_item_price, excluded.min_item_price),
                        max_item_price = MAX(max_item_price, excluded.max_item_price),
                        avg_item_price = round(((avg_item_price * total_units) + (excluded.avg_item_price * excluded.total_units)) / (total_units + excluded.total_units), 2),
                        avg_shipping_cost = round(((avg_shipping_cost * total_units) + (excluded.avg_shipping_cost * excluded.total_units)) / (total_units + excluded.total_units), 2),
                        avg_total_cost = round(((avg_total_cost * total_units) + (excluded.avg_total_cost * excluded.total_units)) / (total_units + excluded.total_units), 2),
                        last_updated = CURRENT_TIMESTAMP;
                """

                for cond_label, cond_id in conditions.items():
                    cursor.execute('''
                        SELECT
                            COUNT(item_id) as total_units,
                            COALESCE(MIN(price), 0.0) as min_p,
                            COALESCE(MAX(price), 0.0) as max_p,
                            COALESCE(AVG(price), 0.0) as avg_p,
                            COALESCE(AVG(shipping_cost), 0.0) as avg_s,
                            COALESCE(AVG(price + shipping_cost), 0.0) as avg_t
                        FROM market_snapshots
                        WHERE model_name = ?
                          AND condition_id = ?
                          AND date_fetched >= datetime('now', ?)
                    ''', (model_name, cond_id, date_modifier))

                    stats = cursor.fetchone()
                    total_units, min_p, max_p, avg_p, avg_s, avg_total = stats

                    if total_units == 0:
                        continue

                    # 1. Structure the raw data into a raw payload package
                    raw_payload = {
                        'model_name': model_name,
                        'timeframe': timeframe,
                        'condition_type': cond_label,
                        'total_units': total_units,
                        'avg_item_price': avg_p,
                        'avg_shipping_cost': avg_s,
                        'avg_total_cost': avg_total
                    }

                    # 2. Direct execution through our Option B validation interceptor
                    is_valid, clean_payload = validate_metrics_payload(raw_payload)

                    if is_valid:
                        # Append the min/max fields missing from the payload checker back into dictionary context
                        clean_payload['min_item_price'] = min_p
                        clean_payload['max_item_price'] = max_p

                        # Save safely
                        cursor.execute(upsert_query, clean_payload)
                    else:
                        print(f"[-] Aggregation rejected for model '{model_name}'. Error: {clean_payload}")

                conn.commit()

        except Exception as e:
            print(f"[-] Database Exception inside Aggregator for '{model_name}': {e}")

    def get_dashboard_view(self, model_name):
        """Fetches the aggregated comparison view for the UI dashboard."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM historical_metrics
                    WHERE model_name = ?
                    ORDER BY timeframe DESC, condition_type DESC
                ''', (model_name,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[-] Failed to extract dashboard view data rows: {e}")
            return []
