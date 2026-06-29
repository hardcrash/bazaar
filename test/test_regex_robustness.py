# test/test_regex_robustness.py

import pytest
from src.analysis.strategy.cpu_strategy import CPUStrategy

@pytest.fixture
def strategy():
    mock_yaml = {
        "valid_models": ["5800X", "5600X", "5900X"],
        "blacklist_words": ["BUNDLE"],
        "title_noise_words": ["DDR4", "CPU"],
        "patterns": [r"RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b"]
    }
    return CPUStrategy(category_name="CPU", yaml_config=mock_yaml)


@pytest.mark.parametrize("title,expected_model", [
    ("AMD Ryzen 7 5800X3D - BOXED", "5800X3D"),
    ("Ryzen 5800X CPU Unit", "5800X"),
    ("AMD Ryzen 5600X (NOT 5800X)", "5600X"),

    # --- Structural Edge Cases ---
    ("AMD RYZEN 7 5800X UPGRADED TO 5900X", "5800X"),
    ("RYZEN   7    5800X??? NEW", "5800X"),
    ("INTEL CORE I7 12700K CPU", "UNKNOWN"),
])
def test_regex_extraction_accuracy(strategy, title, expected_model):
    extracted = strategy.extract_model(title)
    assert extracted == expected_model