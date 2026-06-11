import os
import yaml

class AppConfig:
    def __init__(self, settings_dir="settings"):
        # 1. Dynamically locate the project root directory
        current_dir = os.path.dirname(os.path.abspath(__file__)) # src/util/
        project_root = os.path.dirname(os.path.dirname(current_dir)) # bazaar-data/

        # 2. Build the absolute path to your root settings directory
        self.settings_path = os.path.join(project_root, settings_dir)

        # 3. Load the unified categories matrix
        self.categories = self._load_yaml(os.path.join(self.settings_path, "categories.yaml"))

    def _load_yaml(self, path):
        """Safely opens and loads a target configuration file."""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise FileNotFoundError(f"[-] Configuration Error: Missing file at '{path}'")

    def get_category_config(self, category_name):
        """Returns the unified config details for a given category."""
        return self.categories.get(category_name, {})
