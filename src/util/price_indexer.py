# src/util/price_indexer.py

# src/utils/price_indexer.py

from typing import List, Tuple

class PriceBracketGenerator:
    @staticmethod
    def generate_brackets(min_price: float, max_price: float, step: float = 10.0) -> List[Tuple[float, float]]:
        """
        Slices a broad price range into smaller brackets to avoid hitting
        the eBay Browse API 1,000-item pagination ceiling.
        """
        brackets = []
        current_low = min_price

        while current_low < max_price:
            current_high = current_low + step
            if current_high > max_price:
                current_high = max_price

            brackets.append((current_low, current_high))
            current_low = current_high + 0.01  # Avoid overlapping cents

        return brackets
