import yaml
import os

class AppConfig:
    def __init__(self, settings_dir="settings"):
        self.settings_dir = settings_dir
        # 1. Load Root Program Parameters
        self.params = self._load_yaml("config.yaml")
        # 2. Load Categories and Policies
        self.categories = self._load_yaml(os.path.join(settings_dir, "categories.yaml"))
        self.policies = self._load_yaml(os.path.join(settings_dir, "policies.yaml"))
        # 3. Load SQL Queries
        self.queries = self._load_sql(os.path.join(settings_dir, "queries.sql"))

    def _load_yaml(self, path):
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _load_sql(self, path):
        """Parses a SQL file into a dictionary of named queries."""
        queries = {}
        with open(path, 'r') as f:
            # Simple split by custom separator or tag
            content = f.read()
            # Logic: Split by lines starting with -- name: query_name
            for block in content.split('-- name:'):
                if block.strip():
                    parts = block.split('\n', 1)
                    queries[parts[0].strip()] = parts[1].strip()
        return queries

    def get_category_config(self, category_name):
        return {**self.categories.get(category_name, {}), **self.policies.get(category_name, {})}
