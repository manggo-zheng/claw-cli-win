# -*- coding: utf-8 -*-
"""配置和操作系统外观的共享助手"""
from __future__ import annotations

import os
import winreg

import yaml

from app.logger import CONFIG_DIR, log


def load_yaml(file_name: str) -> dict:
    file_path = os.path.join(CONFIG_DIR, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except FileNotFoundError:
        log.error("Cannot find config file '%s'", file_path)
    except yaml.YAMLError as exc:
        log.error("Invalid YAML format in '%s': %s", file_name, exc)
    return {}


def is_windows_dark_mode() -> bool:
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(registry, key_path)
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception as exc:
        log.warning("Failed to detect Windows theme, fallback dark: %s", exc)
        return True
