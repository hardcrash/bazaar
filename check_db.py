import sqlite3
from collections import defaultdict

def normalize_model_name(name):
    """
    Standardizes casing, trims duplicate spaces, and groups nearly-identical
    strings together while preserving a clean display format.
    """
    if not name:
        return "Unknown"

    # 1. Standardize casing and spaces
    clean = " ".join(name.strip().split())

    # 2. Fix specific known brand variations safely
    clean_lower = clean.lower()

    for brand in ["rog strix", "prime", "proart"]:
        if brand in clean_lower:
            parts = clean_lower.split(brand, 1)
            # Ensure there is actually a string fragment after the split keyword
            chipset = parts[1].strip().upper() if len(parts) > 1 and parts[1].strip() else ""

            # Map clean branding prefixes
            brand_display = "ROG Strix" if brand == "rog strix" else brand.title()
            return f"ASUS {brand_display} {chipset}".strip()

    # Default fallback: Title Case
    return clean.title()

def check_database(db_path="bazaar.db"):
    print("\n" + "="*80)
    print(f" BAZAAR BACKEND ENGINE: SYSTEM HEALTH & CONSOLIDATED METRICS")
    print("="*80)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Volume Tracking
        print("\n[📊] DATABASE STORAGE VOLUMES")
        print("-" * 40)
        for table in ['target_models', 'market_snapshots', 'historical_metrics']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"  ▪ {table.ljust(20)} : {cursor.fetchone()[0]} rows")
            except sqlite3.OperationalError:
                print(f"  ❌ {table.ljust(20)} : Missing or Unreadable Table")

        # 2. Consolidated Dashboard Calculation
        print("\n[🎯] PRESENTATION VIEW: COLLAPSED DASHBOARD METRICS")
        print("-" * 95)

        try:
            cursor.execute("""
                SELECT model_name, timeframe, condition_type, total_units, avg_item_price, avg_shipping_cost, avg_total_cost
                FROM historical_metrics
            """)
            raw_metrics = cursor.fetchall()
        except sqlite3.OperationalError:
            print("  ❌ Could not read from historical_metrics table.")
            return

        if not raw_metrics:
            print("  ℹ No compiled metrics found.")
            return

        # Nested dict structure: [Timeframe][Condition][Normalized Name] -> Consolidated Data Bucket
        consolidated = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
            'total_units': 0, 'weighted_p_sum': 0.0, 'weighted_s_sum': 0.0, 'weighted_t_sum': 0.0
        })))

        # Run the collapsing algorithm
        for row in raw_metrics:
            t_frame = row['timeframe']
            cond = row['condition_type']
            norm_name = normalize_model_name(row['model_name'])
            units = row['total_units']

            bucket = consolidated[t_frame][cond][norm_name]
            bucket['total_units'] += units
            bucket['weighted_p_sum'] += row['avg_item_price'] * units
            bucket['weighted_s_sum'] += row['avg_shipping_cost'] * units
            bucket['weighted_t_sum'] += row['avg_total_cost'] * units

        # Print Table Headers
        print(f"{'Model Name'.ljust(32)} | {'Time'.ljust(4)} | {'Cond.'.ljust(7)} | {'Units'.ljust(5)} | {'Base Avg'.ljust(8)} | {'Ship Avg'.ljust(8)} | {'Total Avg'}")
        print("-" * 95)

        # Timeframe label mapping dictionary
        timeframe_map = {
            'past_month': '1M',
            'past_year': '1Y'
        }

        # Sort and Display the collapsed metrics
        for t_frame in sorted(consolidated.keys()):
            # Fallback gracefully to the raw key if it doesn't match the standard schema
            time_display = timeframe_map.get(t_frame, t_frame[:4].upper())

            for cond in sorted(consolidated[t_frame].keys(), reverse=True):
                cond_display = "🔧 BRKN" if cond == 'broken' else "✅ WRKG"

                for name, data in sorted(consolidated[t_frame][cond].items()):
                    total_u = data['total_units']
                    if total_u == 0:
                        continue

                    # Compute true aggregate averages
                    final_p = round(data['weighted_p_sum'] / total_u, 2)
                    final_s = round(data['weighted_s_sum'] / total_u, 2)
                    final_t = round(data['weighted_t_sum'] / total_u, 2)

                    print(f"{name.ljust(32)} | {time_display.ljust(4)} | {cond_display.ljust(7)} | {str(total_u).ljust(5)} | ${str(final_p).ljust(7)} | ${str(final_s).ljust(7)} | ${final_t}")

if __name__ == "__main__":
    check_database()
