# -*- coding: utf-8 -*-
"""
底层核心逻辑
"""
import os
import subprocess
import winreg

import psutil
import yaml

from app.logger import log, CONFIG_DIR, SCRIPTS_DIR

# Windows 隐藏窗口常量
if os.name == 'nt':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


def load_yaml(file_name):
    """从 configs 文件夹加载 yaml"""
    file_path = os.path.join(CONFIG_DIR, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        log.error(f"Cannot find config file '{file_path}'")
        return {}
    except yaml.YAMLError as exc:
        log.error(f"Invalid YAML format in '{file_name}': {exc}")
        return {}


def is_windows_dark_mode():
    """检测 Windows 是否开启了深色模式"""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(registry, key_path)
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception as e:
        log.warning(f"获取系统主题失败, 默认返回深色模式。原因: {e}")
        return True


class ServiceManager:
    """专门用于管理底层进程的启动、关闭与监控"""

    def __init__(self):
        self.process = None

    def start_process(self, cmd_name):
        if self.is_running():
            return False

        # 从 scripts 文件夹中寻找脚本
        full_path = os.path.join(SCRIPTS_DIR, cmd_name)

        if not os.path.exists(full_path):
            log.error(f"找不到脚本: {full_path}")
            return False

        try:
            self.process = subprocess.Popen(
                full_path,
                shell=False,  # 设为 False，不要额外包一层 cmd.exe
                cwd=SCRIPTS_DIR,
                creationflags=CREATE_NO_WINDOW  # 隐藏黑窗口
            )
            log.info(f"已启动进程 [{cmd_name}], PID: {self.process.pid}")
            return True
        except Exception as e:
            log.error(f"启动进程失败: {e}")
            return False

    def stop_process(self):
        if not self.is_running():
            return

        pid = self.process.pid
        log.info(f"准备结束进程树, PID: {pid}")
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()
            psutil.wait_procs(children + [parent], timeout=3)
            log.info("进程树清理完毕。")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            log.error(f"结束进程时发生异常: {e}")
        finally:
            self.process = None

    def is_running(self):
        if self.process is None:
            return False
        return self.process.poll() is None
