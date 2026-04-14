import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSystemTrayIcon)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QByteArray
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QColor
from PyQt6.QtSvg import QSvgRenderer

# ==========================================
# 1. 主题与 SVG 资源库
# ==========================================
THEMES = {
    "dark": {
        "bg": "#1A1B1E", "border": "#2C2D31", "text_main": "#E1E1E1", "text_muted": "#6E6E6E",
        "hover_bg": "#2A2B2F", "exit_text": "#F35260", "dot_stopped": "#F35260", "dot_running": "#22C55E"
    },
    "light": {
        "bg": "#FFFFFF", "border": "#F0F0F0", "text_main": "#111827", "text_muted": "#9CA3AF",
        "hover_bg": "#F3F4F6", "exit_text": "#DC2626", "dot_stopped": "#DC2626", "dot_running": "#16A34A"
    }
}

SVG_ICONS = {
    "start": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>',
    "stop": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>',
    "restart": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><polyline points="3 3 3 8 8 8"></polyline></svg>',
    "update": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    "status": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>',
    "settings": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
    "exit": '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
}


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


# ==========================================
# 2. 核心配置文件 (完全数据驱动)
# ==========================================
MENU_CONFIG = {
    # 1. 头部配置
    "header": {
        "title": "OPEN CLAW SERVICE",
        # 定义系统中可能存在的所有状态，以及该状态下的表现
        "states": {
            "stopped": {"text": "Stopped", "dot_color_key": "dot_stopped"},
            "running": {"text": "Running", "dot_color_key": "dot_running"}
        },
        "initial_state": "stopped"
    },

    # 2 & 3. 菜单分组配置 (外层列表代表组，会自动在组之间插入分割线)
    "groups": [
        # 第一组：服务控制
        [
            # enabled_in: 定义该选项在什么状态下允许被点击。 "all" 代表永远可用
            {"id": "start", "icon": "start", "text": "Start Service", "action": "cmd_start", "enabled_in": ["stopped"]},
            {"id": "stop", "icon": "stop", "text": "Stop Service", "action": "cmd_stop", "enabled_in": ["running"]},
            {"id": "restart", "icon": "restart", "text": "Restart Service", "action": "cmd_restart", "enabled_in": ["all"]},
            {"id": "update", "icon": "update", "text": "Check for Updates", "action": "cmd_update", "enabled_in": ["all"]}
        ],
        # 第二组：界面与设置
        [
            {"id": "status", "icon": "status", "text": "Show Status Window", "action": "cmd_show_status", "enabled_in": ["all"]},
            {"id": "settings", "icon": "settings", "text": "Settings (Toggle Theme)", "action": "cmd_toggle_theme", "enabled_in": ["all"]}
        ],
        # 第三组：退出
        [
            {"id": "exit", "icon": "exit", "text": "Exit Manager", "is_exit": True, "action": "cmd_exit", "enabled_in": ["all"]}
        ]
    ]
}


# ==========================================
# 3. 基础组件
# ==========================================
class MenuItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, item_config, parent=None):
        super().__init__(parent)
        self.config = item_config
        self.is_exit = item_config.get("is_exit", False)
        self.is_enabled = True
        self.current_theme = THEMES["dark"]

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
        self.icon_label.setPixmap(render_svg_to_pixmap(SVG_ICONS[self.config["icon"]], color))
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

        # 状态管理
        self.current_state = MENU_CONFIG["header"]["initial_state"]
        self.theme_name = "dark"
        self.theme = THEMES[self.theme_name]

        # 存放动态生成的组件以便后续更新
        self.menu_items_map = {}

        self.build_ui_from_config()
        self.apply_theme()

    def build_ui_from_config(self):
        """解析配置字典，自动化构建UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_widget = QWidget()
        self.bg_widget.setObjectName("bg_widget")
        self.bg_layout = QVBoxLayout(self.bg_widget)
        self.bg_layout.setContentsMargins(6, 12, 6, 6)
        self.bg_layout.setSpacing(2)

        # 1. 构建头部
        header_cfg = MENU_CONFIG["header"]
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

        # 2. 循环构建选项组
        for group_idx, group_items in enumerate(MENU_CONFIG["groups"]):
            # 每组之间插入分割线
            if group_idx > 0:
                self.add_separator()

            # 构建组内选项
            for item_cfg in group_items:
                item_widget = MenuItem(item_cfg)

                # 动态绑定点击事件 (寻找 self 下同名的方法)
                action_name = item_cfg.get("action")
                if hasattr(self, action_name):
                    item_widget.clicked.connect(getattr(self, action_name))

                self.bg_layout.addWidget(item_widget)

                # 记录到字典，方便后续根据 state 统一控制启用/禁用
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
        self.theme = THEMES[self.theme_name]

        self.bg_widget.setStyleSheet(f"""
            #bg_widget {{
                background-color: {self.theme['bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
            }}
            #separator {{
                background-color: {self.theme['border']};
                margin: 4px 0px;
            }}
        """)

        self.title_label.setStyleSheet(f"color: {self.theme['text_muted']};")

        # 递归更新所有子菜单的主题
        for item_data in self.menu_items_map.values():
            item_data["widget"].update_theme(self.theme)

        self.update_ui_state()

    def update_ui_state(self):
        """核心状态引擎：根据 current_state 更新头部文字、颜色，以及所有菜单项的可用状态"""
        # 1. 更新头部
        state_cfg = MENU_CONFIG["header"]["states"][self.current_state]
        self.status_label.setText(state_cfg["text"])
        self.status_label.setStyleSheet(f"color: {self.theme['text_main']};")
        self.dot_label.setStyleSheet(f"color: {self.theme[state_cfg['dot_color_key']]}; font-size: 14px;")

        # 2. 遍历并更新每一个菜单项
        for item_data in self.menu_items_map.values():
            allowed_states = item_data["enabled_in"]
            widget = item_data["widget"]

            if "all" in allowed_states or self.current_state in allowed_states:
                widget.set_item_enabled(True)
            else:
                widget.set_item_enabled(False)

    # ----------------------------------------
    # 动作回调区 (名称必须和配置字典的 action 一致)
    # ----------------------------------------
    def cmd_start(self):
        self.current_state = "running"
        self.update_ui_state()
        self.hide()

    def cmd_stop(self):
        self.current_state = "stopped"
        self.update_ui_state()
        self.hide()

    def cmd_restart(self):
        print("执行: 重启服务")
        self.hide()

    def cmd_update(self):
        print("执行: 检查更新")
        self.hide()

    def cmd_show_status(self):
        print("执行: 显示状态窗口")
        self.hide()

    def cmd_toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.apply_theme()
        self.hide()

    def cmd_exit(self):
        sys.exit()


# ==========================================
# 5. 启动入口
# ==========================================
class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.menu_window = CustomTrayMenu()
        self.tray_icon = QSystemTrayIcon()

        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#222222"))
        from PyQt6.QtGui import QPainter, QBrush
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#F35260")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(45, 45, 15, 15)
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("Open Claw Manager")
        self.tray_icon.activated.connect(self.on_tray_clicked)
        self.tray_icon.show()

    def on_tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.Context):
            self.show_menu()

    def show_menu(self):
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