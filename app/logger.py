# -*- coding: utf-8 -*-
"""
全局日志管理与路径管理
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# 1. 动态获取项目根目录 (兼容 PyInstaller 打包后的运行环境)
if getattr(sys, 'frozen', False):
    # 如果被打包成了 exe，根目录就是 exe 所在目录
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    # 如果是 python 源码运行，根目录是 app/ 的上一级
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. 定义各模块标准路径
CONFIG_DIR = os.path.join(ROOT_DIR, 'configs')
SCRIPTS_DIR = os.path.join(ROOT_DIR, 'scripts')
ASSETS_DIR = os.path.join(ROOT_DIR, 'assets')
LOGS_DIR = os.path.join(ROOT_DIR, 'logs')

# 确保日志目录存在
os.makedirs(LOGS_DIR, exist_ok=True)


# 3. 初始化全局 Logger
def setup_logger():
    log_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 轮转文件处理器 (最大 1MB，保留 3 个备份)
    log_file = os.path.join(LOGS_DIR, 'app.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(log_formatter)

    # 控制台处理器 (在IDE调试时也能看到)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    logger = logging.getLogger("OpenClaw")
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


log = setup_logger()
