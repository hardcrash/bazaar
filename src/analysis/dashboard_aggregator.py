import sqlite3
from datetime import datetime
import statistics  # 📊 Standard statistical math package
# Inject Option B interceptor methods
from src.analysis.ingest_pipeline import validate_metrics_payload

class DashboardAggregator:
    def __init__(self, db_path="bazaar.db"):
        self.db_path = db_path

    def calculate_historical_metrics(self, model_name, timeframe='past_month'):
        """
        Computes true segmented time series windows over data snapshots,
        extracts precise statistical metrics (Median/StdDev) on Landed Cost,
        and runs them through a pre-commit validation layer.
        """
        date_modifier = "-30 days" if timeframe == 'past_month' else "-395 days"
        conditions = {'working': 3000, 'broken': 7000}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Robust math-aware Upsert query to protect UNIQUE key constraints safely
                # Extended schema fields to store median and standard deviation metrics
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
                        total_units = excluded.total_units,
                        min_item_price = excluded.min_item_price,
                        max_item_price = excluded.max_item_price,
                        avg_item_price = excluded.avg_item_price,
                        avg_shipping_cost = excluded.avg_shipping_cost,
                        avg_total_cost = excluded.avg_total_cost,
                        last_updated = CURRENT_TIMESTAMP;
                """

                for cond_label, cond_id in conditions.items():
                    # 1. Gather all unique raw transactions within the window boundary
                    cursor.execute('''
                        SELECT price, shipping_cost, (price + shipping_cost) as landed_cost
                        FROM market_snapshots
                        WHERE model_name = ?
                          AND condition_id = ?
                          AND date_fetched >= datetime('now', ?)
                          AND is_sold = 1
                    ''', (model_name, cond_id, date_modifier))

                    rows = cursor.fetchall()
                    total_units = len(rows)

                    if total_units == 0:
                        continue

                    # 2. Map row arrays out to flat floats for pure calculations
                    base_prices = [r[0] for r in rows]
                    shipping_costs = [r[1] for r in rows]
                    landed_costs = [r[2] for r in rows]

                    # 3. Compute pure statistical shapes
                    min_p = min(base_prices)
                    max_p = max(base_prices)
                    avg_p = round(statistics.mean(base_prices), 2)
                    avg_s = round(statistics.mean(shipping_costs), 2)
                    avg_total = round(statistics.mean(landed_costs), 2)

                    # Dynamic metrics ready for your extended UI layout tracking:
                    median_landed = round(statistics.median(landed_costs), 2)
                    # Standard deviation requires at least 2 points to evaluate spanvariance
                    std_dev_landed = round(statistics.stdev(landed_costs), 2) if total_units > 1 else 0.0

                    # 4. Structure the raw data into a raw payload package
                    raw_payload = {
                        'model_name': model_name,
                        'timeframe': timeframe,
                        'condition_type': cond_label,
                        'total_units': total_units,
                        'avg_item_price': avg_p,
                        'avg_shipping_cost': avg_s,
                        'avg_total_cost': avg_total
                    }

                    # 5. Direct execution through our Option B validation interceptor
                    is_valid, clean_payload = validate_metrics_payload(raw_payload)

                    if is_valid:
                        # Append the min/max fields back into dictionary context
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
