# src/util/config_loader.py

import os
import yaml
from loguru import logger

class AppConfig:
    def __init__(self, settings_dir="settings"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # Define explicit absolute directory paths
        self.project_root = project_root
        self.settings_path = os.path.join(project_root, settings_dir)

        logger.debug(f"Resolving root path to: {self.project_root}")
        logger.debug(f"Resolving settings path to: {self.settings_path}")

        # 1. Load the core configuration file right from the PROJECT ROOT
        config_data = self._load_yaml(os.path.join(self.project_root, "config.yaml"))

        # Hydrate configuration values directly into AppConfig instance fields
        for key, value in config_data.items():
            setattr(self, key, value)
        logger.info("Successfully loaded and hydrated root core configuration parameters.")

        # 2. Load the data category matrix from the SETTINGS SUBDIRECTORY
        self.categories = self._load_yaml(os.path.join(self.settings_path, "categories.yaml"))
        logger.info("Successfully loaded unified categories configuration matrix.")

    def _load_yaml(self, path):
        """Safely opens and loads a target configuration file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
                logger.debug(f"Loaded YAML file successfully: {path}")
                return data
        except FileNotFoundError:
            logger.critical(f"Config Loader Malfunction: Missing critical file at '{path}'")
            raise FileNotFoundError(f"[-] Configuration Error: Missing file at '{path}'")

    def get_category_config(self, category_name):
        """Returns the unified config details for a given category."""
        config = self.categories.get(category_name, {})
        if not config:
            logger.warning(f"Requested configuration for unknown category target: '{category_name}'")
        return config
