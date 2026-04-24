# -*- coding: utf-8 -*-
"""应用包导出定义。"""

__all__ = ["AppController"]


def __getattr__(name: str):
    """延迟导入 UI 入口，避免普通模块导入被 Qt 依赖拖住。"""
    if name == "AppController":
        from .menu import AppController

        return AppController
    raise AttributeError(name)
