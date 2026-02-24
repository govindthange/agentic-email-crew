import xml.etree.ElementTree as ET
import os

class ConfigParser:
    def __init__(self, config_path):
        self.config_path = config_path
        self.tree = ET.parse(config_path)
        self.root = self.tree.getroot()

    def get_categories(self):
        categories = {}
        cat_root = self.root.find('categories')
        if cat_root is not None:
            for cat in cat_root:
                name = cat.get('name')
                values = [v.strip() for v in (cat.get('values') or "").split(',')]
                if name:
                    categories[name] = values
        return categories

    def get_settings(self):
        settings = {}
        set_root = self.root.find('settings')
        if set_root is not None:
            for setting in set_root:
                name = setting.get('name')
                value = setting.get('value')
                if name:
                    settings[name] = value
        return settings

    def get_profiles(self):
        profiles = {}
        prof_root = self.root.find('profiles')
        if prof_root is not None:
            for prof in prof_root:
                name = prof.get('name')
                if name:
                    profiles[name] = {
                        'heavy': prof.get('heavy'),
                        'light': prof.get('light')
                    }
        return profiles

    def get_setting(self, name, default=None):
        settings = self.get_settings()
        return settings.get(name, default)
