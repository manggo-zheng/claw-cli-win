# -*- coding: utf-8 -*-
"""
GUI 渲染与程序入口
"""
import os
import subprocess
import sys

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QByteArray, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QCursor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSystemTrayIcon)

from app.core import load_yaml, is_windows_dark_mode, ServiceManager
# 导入我们自己拆分出去的模块
from app.logger import log, ASSETS_DIR, SCRIPTS_DIR

# 初始化配置
APP_CONFIG = load_yaml('config.yaml')
MENU_CONFIG = load_yaml('menu.yaml')


def render_svg_to_pixmap(svg_string, color, size=16):
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


class CustomTrayMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(240)

        self.service_mgr = ServiceManager()
        self.current_state = APP_CONFIG["header"]["initial_state"]
        self.theme_name = "dark" if is_windows_dark_mode() else "light"
        self.theme = APP_CONFIG["themes"][self.theme_name]

        self.menu_items_map = {}
        self.build_ui_from_config()
        self.apply_theme()

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.check_process_health)
        self.monitor_timer.start(1000)

    def check_process_health(self):
        if self.current_state == "running" and not self.service_mgr.is_running():
            log.warning("检测到主服务意外关闭，正在自动更新 UI 状态...")
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

        for group_idx, group_items in enumerate(MENU_CONFIG.get("groups", [])):
            if group_idx > 0:
                self.add_separator()

            for item_cfg in group_items:
                item_widget = MenuItem(item_cfg)
                action_name = item_cfg.get("action")
                if hasattr(self, action_name):
                    item_widget.clicked.connect(getattr(self, action_name))
                else:
                    log.warning(f"未找到绑定的动作方法: {action_name}")

                self.bg_layout.addWidget(item_widget)
                self.menu_items_map[item_cfg["id"]] = {
                    "widget": item_widget,
                    "enabled_in": item_cfg.get("enabled_in", ["all"])
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
            widget.set_item_enabled("all" in allowed_states or self.current_state in allowed_states)

    # ----------------------------------------
    # 动作回调区
    # ----------------------------------------
    def cmd_start(self):
        clicked_item = self.sender()
        cmd = clicked_item.config.get("cmd")
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
        self.service_mgr.stop_process()
        clicked_item = self.sender()
        # 注意：这里假设 restart 和 start 配的是同一个服务脚本，一般写死或从配置读
        cmd = clicked_item.config.get("cmd", "gateway.cmd")
        if cmd and self.service_mgr.start_process(cmd):
            self.current_state = "running"
            self.update_ui_state()
        self.hide()

    def cmd_exit(self):
        if self.service_mgr.is_running():
            log.info("退出前拦截：正在清理运行中的后台服务...")
            self.service_mgr.stop_process()
        log.info("Manager 已正常退出。")
        sys.exit()

    def cmd_default(self):
        clicked_item = self.sender()
        if not clicked_item: return

        cmd = clicked_item.config.get("cmd")
        text = clicked_item.config.get("text", "Unknown")

        if cmd:
            log.info(f"执行独立工具 [{text}]: {cmd}")
            try:
                # 针对非主服务脚本，直接去 scripts 目录下执行
                target_script = os.path.join(SCRIPTS_DIR, cmd)
                subprocess.Popen(target_script if os.path.exists(target_script) else cmd, shell=True, cwd=SCRIPTS_DIR)
            except Exception as e:
                log.error(f"执行 [{text}] 失败: {e}")
        else:
            log.warning(f"自定义选项 [{text}] 未配置 'cmd' 字段！")
        self.hide()


class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.menu_window = CustomTrayMenu()
        self.tray_icon = QSystemTrayIcon()

        # 读取 assets 文件夹下的图标
        icon_path = os.path.join(ASSETS_DIR, "anpi.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            log.warning(f"找不到系统托盘图标文件: {icon_path}")

        self.tray_icon.setToolTip(APP_CONFIG.get("app", {}).get("tooltip", "Manager"))
        self.tray_icon.activated.connect(self.on_tray_clicked)
        self.tray_icon.show()
        log.info("Open Claw Manager 启动成功，托盘图标已加载。")

    def on_tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.Context):
            self.show_menu()

    def show_menu(self):
        system_theme = "dark" if is_windows_dark_mode() else "light"
        if self.menu_window.theme_name != system_theme:
            log.info(f"检测到系统主题切换，自动应用: {system_theme}")
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
