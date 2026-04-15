import sys
import os
import yaml
import subprocess
import psutil  # 必须安装: pip install psutil
import winreg

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSystemTrayIcon, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QByteArray, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QColor
from PyQt6.QtSvg import QSvgRenderer


# ==========================================
# 1. 读取配置文件 (同上保持不变)
# ==========================================
def load_yaml(file_name):
    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Cannot find config file '{file_name}'")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error: Invalid YAML format in '{file_name}': {exc}")
        sys.exit(1)


APP_CONFIG = load_yaml('config.yaml')
MENU_CONFIG = load_yaml('menu.yaml')

# ==========================================
# 1.5 操作系统状态检测
# ==========================================
def is_windows_dark_mode():
    """检测 Windows 是否开启了深色模式"""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(registry, key_path)
        # AppsUseLightTheme: 0 = Dark, 1 = Light
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        # 如果获取失败（比如在旧版 Win7），默认返回暗色或亮色
        return True


# ==========================================
# 2. 进程管理核心 (注入灵魂)
# ==========================================
class ServiceManager:
    """专门用于管理底层进程的启动、关闭与监控"""

    def __init__(self):
        self.process = None

    def start_process(self, cmd_path):
        """非阻塞启动子进程"""
        if self.is_running():
            return False

        base_path = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_path, cmd_path)

        if not os.path.exists(full_path):
            print(f"Error: 找不到脚本 {full_path}")
            return False

        try:
            # 使用 Popen 非阻塞启动进程。shell=True 适合执行 .bat/.cmd
            self.process = subprocess.Popen(full_path, shell=True, cwd=base_path)
            print(f"已启动进程, PID: {self.process.pid}")
            return True
        except Exception as e:
            print(f"启动进程失败: {e}")
            return False

    def stop_process(self):
        """精准的进程树击杀，防止孤儿进程遗留"""
        if not self.is_running():
            return

        pid = self.process.pid
        print(f"准备结束进程树, PID: {pid}")
        try:
            parent = psutil.Process(pid)
            # 1. 找到该进程衍生的所有子孙进程
            children = parent.children(recursive=True)
            # 2. 击杀所有子孙进程 (例如 node.exe, java.exe)
            for child in children:
                child.terminate()
            # 3. 击杀父进程 (cmd.exe)
            parent.terminate()

            # 等待它们彻底死亡
            psutil.wait_procs(children + [parent], timeout=3)
            print("进程树清理完毕。")
        except psutil.NoSuchProcess:
            pass  # 进程已经死了
        except Exception as e:
            print(f"结束进程时发生异常: {e}")
        finally:
            self.process = None

    def is_running(self):
        """检查进程是否存活"""
        if self.process is None:
            return False
        # poll() 返回 None 说明进程还在跑，返回数字说明退出了
        return self.process.poll() is None


# ==========================================
# 3. 基础工具与组件 (同上保持不变)
# ==========================================
def render_svg_to_pixmap(svg_string, color, size=16):
    # ...(保持之前的代码)...
    colored_svg = svg_string.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(colored_svg.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PyQt6.QtGui import QPainter
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


class MenuItem(QWidget):
    # ...(保持之前的代码)...
    clicked = pyqtSignal()

    def __init__(self, item_config, parent=None):
        super().__init__(parent)
        self.config = item_config
        self.is_exit = item_config.get("is_exit", False)
        self.is_enabled = True
        self.current_theme = APP_CONFIG["themes"]["dark"]
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        self.icon_label = QLabel()
        self.text_label = QLabel(item_config["text"])
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        font = self.text_label.font()
        font.setPixelSize(13)
        self.text_label.setFont(font)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()

    def update_theme(self, theme):
        self.current_theme = theme
        self.update_ui()

    def update_ui(self):
        if not self.is_enabled:
            color = self.current_theme["text_muted"]
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self.is_exit:
            color = self.current_theme["exit_text"]
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            color = self.current_theme["text_main"]
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_label.setStyleSheet(f"color: {color};")
        svg_icon = APP_CONFIG["svg_icons"].get(self.config["icon"], "")
        self.icon_label.setPixmap(render_svg_to_pixmap(svg_icon, color))
        self.setStyleSheet("background-color: transparent; border-radius: 6px;")

    def set_item_enabled(self, enabled):
        self.is_enabled = enabled
        self.update_ui()

    def enterEvent(self, event):
        if self.is_enabled:
            self.setStyleSheet(f"background-color: {self.current_theme['hover_bg']}; border-radius: 6px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("background-color: transparent; border-radius: 6px;")
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ==========================================
# 4. 动态构建的菜单主窗口
# ==========================================
class CustomTrayMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(240)

        # 引入服务管理器
        self.service_mgr = ServiceManager()
        self.current_state = APP_CONFIG["header"]["initial_state"]

        self.theme_name = "dark" if is_windows_dark_mode() else "light"
        self.theme = APP_CONFIG["themes"][self.theme_name]

        self.menu_items_map = {}
        self.build_ui_from_config()
        self.apply_theme()

        # 【重点】状态守护定时器：每秒检查一次后台进程是否意外死亡
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.check_process_health)
        self.monitor_timer.start(1000)

    def check_process_health(self):
        """如果UI显示Running，但底层进程已经死了，自动纠正UI状态"""
        if self.current_state == "running" and not self.service_mgr.is_running():
            print("检测到服务意外关闭，更新UI状态...")
            self.current_state = "stopped"
            self.update_ui_state()

    def build_ui_from_config(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_widget = QWidget()
        self.bg_widget.setObjectName("bg_widget")
        self.bg_layout = QVBoxLayout(self.bg_widget)
        self.bg_layout.setContentsMargins(6, 12, 6, 6)
        self.bg_layout.setSpacing(2)

        header_cfg = APP_CONFIG["header"]
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(12, 0, 12, 8)
        header_layout.setSpacing(6)
        self.title_label = QLabel(header_cfg["title"])
        font = self.title_label.font()
        font.setPixelSize(11)
        font.setBold(True)
        self.title_label.setFont(font)

        status_layout = QHBoxLayout()
        self.dot_label = QLabel("●")
        self.status_label = QLabel()
        status_font = self.status_label.font()
        status_font.setPixelSize(13)
        self.status_label.setFont(status_font)
        status_layout.addWidget(self.dot_label)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        header_layout.addWidget(self.title_label)
        header_layout.addLayout(status_layout)
        self.bg_layout.addLayout(header_layout)

        for group_idx, group_items in enumerate(MENU_CONFIG["groups"]):
            if group_idx > 0:
                self.add_separator()

            for item_cfg in group_items:
                item_widget = MenuItem(item_cfg)
                action_name = item_cfg.get("action")
                if hasattr(self, action_name):
                    item_widget.clicked.connect(getattr(self, action_name))
                else:
                    print(f"警告: 未找到绑定的动作方法 {action_name}")

                self.bg_layout.addWidget(item_widget)
                self.menu_items_map[item_cfg["id"]] = {
                    "widget": item_widget,
                    "enabled_in": item_cfg.get("enabled_in", ["all"]),
                    "cmd": item_cfg.get("cmd", None)  # 记录命令
                }

        self.main_layout.addWidget(self.bg_widget)
        self.update_ui_state()

    def add_separator(self):
        line = QWidget()
        line.setFixedHeight(1)
        line.setObjectName("separator")
        self.bg_layout.addWidget(line)

    def apply_theme(self):
        self.theme = APP_CONFIG["themes"][self.theme_name]
        self.bg_widget.setStyleSheet(f"""
            #bg_widget {{ background-color: {self.theme['bg']}; border: 1px solid {self.theme['border']}; border-radius: 8px; }}
            #separator {{ background-color: {self.theme['border']}; margin: 4px 0px; }}
        """)
        self.title_label.setStyleSheet(f"color: {self.theme['text_muted']};")
        for item_data in self.menu_items_map.values():
            item_data["widget"].update_theme(self.theme)
        self.update_ui_state()

    def update_ui_state(self):
        state_cfg = APP_CONFIG["header"]["states"][self.current_state]
        self.status_label.setText(state_cfg["text"])
        self.status_label.setStyleSheet(f"color: {self.theme['text_main']};")
        self.dot_label.setStyleSheet(f"color: {self.theme[state_cfg['dot_color_key']]}; font-size: 14px;")

        for item_data in self.menu_items_map.values():
            allowed_states = item_data["enabled_in"]
            widget = item_data["widget"]
            if "all" in allowed_states or self.current_state in allowed_states:
                widget.set_item_enabled(True)
            else:
                widget.set_item_enabled(False)

    # ----------------------------------------
    # 动作回调区 (注入底层逻辑)
    # ----------------------------------------
    def cmd_start(self):
        cmd = self.menu_items_map["start"]["cmd"]
        if cmd and self.service_mgr.start_process(cmd):
            self.current_state = "running"
            self.update_ui_state()
        self.hide()

    def cmd_stop(self):
        self.service_mgr.stop_process()
        self.current_state = "stopped"
        self.update_ui_state()
        self.hide()

    def cmd_restart(self):
        """重启 = 停止 -> 等待一瞬 -> 启动"""
        self.service_mgr.stop_process()
        cmd = self.menu_items_map["start"]["cmd"]
        if cmd and self.service_mgr.start_process(cmd):
            self.current_state = "running"
            self.update_ui_state()
        self.hide()

    def cmd_update(self):
        # Update 通常是跑一下就结束的短任务，我们可以用另一个独立进程跑
        cmd = self.menu_items_map["update"]["cmd"]
        if cmd:
            print(f"正在启动更新任务: {cmd}")
            subprocess.Popen(cmd, shell=True)
        self.hide()

    def cmd_show_status(self):
        print("执行: 显示状态窗口")
        self.hide()

    def cmd_exit(self):
        # 退出前一定要清理后台进程！
        if self.service_mgr.is_running():
            self.service_mgr.stop_process()
        sys.exit()

    def cmd_default(self):
        print("执行: 恢复默认")
        self.hide()

    def cmd_default(self):
        """处理所有用户自定义的扩展动作"""
        # 核心魔法：直接获取是被哪个 MenuItem 触发的
        clicked_item = self.sender()
        if not clicked_item:
            return

        # 直接从组件身上把配置项扒下来
        cmd = clicked_item.config.get("cmd")
        text = clicked_item.config.get("text", "Unknown")

        if cmd:
            print(f"执行自定义选项 [{text}]: {cmd}")
            try:
                # 作为独立进程运行，阅后即焚，不阻塞
                subprocess.Popen(cmd, shell=True)
            except Exception as e:
                print(f"执行自定义命令失败 [{text}]: {e}")
        else:
            print(f"警告: 自定义选项 [{text}] 未配置 'cmd' 字段！")

        self.hide()


# ==========================================
# 5. 启动入口
# ==========================================
class AppController:
    # ...(保持不变)...
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.menu_window = CustomTrayMenu()
        self.tray_icon = QSystemTrayIcon()

        icon_path = APP_CONFIG.get("app", {}).get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            tray_icon_obj = QIcon(icon_path)
            self.tray_icon.setIcon(tray_icon_obj)
            self.tray_icon.setToolTip(APP_CONFIG["app"]["tooltip"])
            self.tray_icon.activated.connect(self.on_tray_clicked)
            self.tray_icon.show()

    def on_tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.Context):
            self.show_menu()

    def show_menu(self):
        system_theme = "dark" if is_windows_dark_mode() else "light"
        if self.menu_window.theme_name != system_theme:
            print(f"检测到系统主题切换，正在自动应用: {system_theme}")
            self.menu_window.theme_name = system_theme
            self.menu_window.apply_theme()

        cursor_pos = QCursor.pos()
        menu_width = self.menu_window.width()
        menu_height = self.menu_window.height()

        x = cursor_pos.x() - menu_width // 2
        y = cursor_pos.y() - menu_height - 15

        self.menu_window.move(QPoint(x, y))
        self.menu_window.show()
        self.menu_window.activateWindow()

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    controller = AppController()
    controller.run()