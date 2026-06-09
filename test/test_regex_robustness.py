import pytest
from src.analysis.strategy.cpu_strategy import ActiveCPUStrategy

@pytest.fixture
def strategy(tmp_path):
    # Uses the same YAML logic we verified
    mock_yaml = {
        "CPU": {
            "valid_models": ["5800X"],
            "blacklist_words": ["BUNDLE"],
            "noise_words": ["DDR4", "CPU"],
            "patterns": [r"RYZEN(?:\\s+[579])?\\s+(5\\d{3}(?:X3D|X|G|GE|XT)?)\\b"]
        }
    }
    return ActiveCPUStrategy(category_name="CPU", yaml_data=mock_yaml)

@pytest.mark.parametrize("title,expected_model,target_model", [
    ("AMD Ryzen 7 5800X3D - BOXED", "5800X3D", "5800X3D"),
    ("Ryzen 5800X CPU Unit", "5800X", "5800X"),
    ("AMD Ryzen 5600X (NOT 5800X)", "5600X", "5600X"), # When target is 5600X, it finds 5600X
])

def test_regex_extraction_accuracy(strategy, title, expected_model, target_model):
    assert strategy.extract_model(title.upper(), target_model.upper()) == expected_model
