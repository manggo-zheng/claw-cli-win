# -*- coding: utf-8 -*-
"""托盘菜单 UI 与应用控制器。"""
from __future__ import annotations

import os
import sys
from typing import Any

from PyQt6.QtCore import QByteArray, QPoint, QProcess, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSystemTrayIcon, QVBoxLayout, QWidget

from app.core import is_windows_dark_mode, load_yaml
from app.gateway_client import GatewayClient
from app.gateway_protocol import GatewayConfig, GatewaySecrets, build_connect_request
from app.logger import ASSETS_DIR, SCRIPTS_DIR, log
from app.process_controller import ProcessController
from app.state import AppState, RuntimeState

APP_CONFIG = load_yaml("config.yaml")
MENU_CONFIG = load_yaml("menu.yaml")
GATEWAY_CONFIG = GatewayConfig.from_dict(load_yaml("gateway.yaml"))


def render_svg_to_pixmap(svg_string: str, color: str, size: int = 16) -> QPixmap:
    """将 SVG 模板渲染为指定颜色的图标。"""
    colored_svg = svg_string.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(colored_svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


def _get_by_dot_path(data: dict[str, Any], path: str, default: Any = "") -> Any:
    """通过点路径读取嵌套字典。"""
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


class MenuItem(QWidget):
    """单个菜单项组件。"""

    clicked = pyqtSignal()  # 菜单点击信号

    def __init__(self, item_config: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)

        # 初始化菜单项配置和基础状态。
        self.config = item_config
        self.is_exit = item_config.get("is_exit", False)
        self.is_enabled = True
        self.current_theme = APP_CONFIG["themes"]["dark"]
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(34)

        # 构建菜单项布局和文本图标控件。
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        self.icon_label = QLabel()
        self.text_label = QLabel(item_config["text"])
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # 统一菜单项文字字号。
        font = self.text_label.font()
        font.setPixelSize(13)
        self.text_label.setFont(font)

        # 将图标和文字加入布局。
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()

    def update_theme(self, theme: dict[str, str]) -> None:
        """切换主题并刷新样式。"""
        self.current_theme = theme
        self.update_ui()

    def update_ui(self) -> None:
        """按照当前主题与可用状态更新菜单项样式。"""
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

    def set_item_enabled(self, enabled: bool) -> None:
        """更新菜单项启用状态。"""
        self.is_enabled = enabled
        self.update_ui()

    def enterEvent(self, event):  # noqa: N802
        """鼠标移入时显示悬停背景。"""
        if self.is_enabled:
            self.setStyleSheet(f"background-color: {self.current_theme['hover_bg']}; border-radius: 6px;")
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        """鼠标移出时恢复透明背景。"""
        self.setStyleSheet("background-color: transparent; border-radius: 6px;")
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        """鼠标左键释放时触发点击信号。"""
        if self.is_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CustomTrayMenu(QWidget):
    """仅负责托盘菜单的 UI 展示与动作上报。"""

    start_requested = pyqtSignal()  # 请求启动信号
    stop_requested = pyqtSignal()  # 请求停止信号
    restart_requested = pyqtSignal()  # 请求重启信号
    exit_requested = pyqtSignal()  # 请求退出信号
    script_requested = pyqtSignal(str)  # 请求执行外部脚本信号

    def __init__(self, ui_state_map: dict[str, str]):
        super().__init__()

        # 初始化弹出菜单窗口属性。
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(240)

        # 保存 UI 状态映射与主题信息。
        self.ui_state_map = ui_state_map
        self.app_state = AppState.STOPPED
        self.theme_name = "dark" if is_windows_dark_mode() else "light"
        self.theme = APP_CONFIG["themes"][self.theme_name]
        self.menu_items_map: dict[str, dict[str, Any]] = {}

        # 构建菜单视图并初始化默认状态。
        self.build_ui_from_config()
        self.apply_theme()
        self.set_state(AppState.STOPPED)

    def build_ui_from_config(self) -> None:
        """根据 YAML 菜单配置构建视图。"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_widget = QWidget()
        self.bg_widget.setObjectName("bg_widget")
        self.bg_layout = QVBoxLayout(self.bg_widget)
        self.bg_layout.setContentsMargins(6, 12, 6, 6)
        self.bg_layout.setSpacing(2)

        # 构建菜单头部标题和状态展示。
        header_cfg = APP_CONFIG["header"]
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(12, 0, 12, 8)
        header_layout.setSpacing(6)
        self.title_label = QLabel(header_cfg["title"])
        title_font = self.title_label.font()
        title_font.setPixelSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        # 构建菜单头部状态行。
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

        # 按分组创建菜单项并绑定 UI 事件。
        for group_idx, group_items in enumerate(MENU_CONFIG.get("groups", [])):
            if group_idx > 0:
                self._add_separator()
            for item_cfg in group_items:
                item_widget = MenuItem(item_cfg)
                self._bind_menu_action(item_widget, item_cfg)
                self.bg_layout.addWidget(item_widget)
                self.menu_items_map[item_cfg["id"]] = {
                    "widget": item_widget,
                    "enabled_in": item_cfg.get("enabled_in", ["all"]),
                }

        self.main_layout.addWidget(self.bg_widget)

    def _bind_menu_action(self, item_widget: MenuItem, item_cfg: dict[str, Any]) -> None:
        """将配置动作绑定到菜单信号。"""
        action_name = str(item_cfg.get("action", "")).strip()
        cmd = str(item_cfg.get("cmd", "")).strip()
        if action_name == "cmd_start":
            item_widget.clicked.connect(self.start_requested.emit)
        elif action_name == "cmd_stop":
            item_widget.clicked.connect(self.stop_requested.emit)
        elif action_name == "cmd_restart":
            item_widget.clicked.connect(self.restart_requested.emit)
        elif action_name == "cmd_exit":
            item_widget.clicked.connect(self.exit_requested.emit)
        elif action_name == "cmd_default" and cmd:
            item_widget.clicked.connect(lambda checked=False, script=cmd: self.script_requested.emit(script))
        else:
            log.warning("menu action missing: %s", action_name)

    def _add_separator(self) -> None:
        """添加菜单分隔线。"""
        line = QWidget()
        line.setFixedHeight(1)
        line.setObjectName("separator")
        self.bg_layout.addWidget(line)

    def set_state(self, new_state: AppState) -> None:
        """从控制器接收状态并刷新 UI。"""
        self.app_state = new_state
        self.update_ui_state()

    def apply_theme(self) -> None:
        """应用当前主题配色。"""
        self.theme = APP_CONFIG["themes"][self.theme_name]
        self.bg_widget.setStyleSheet(
            f"""
            #bg_widget {{ background-color: {self.theme['bg']}; border: 1px solid {self.theme['border']}; border-radius: 8px; }}
            #separator {{ background-color: {self.theme['border']}; margin: 4px 0px; }}
            """
        )
        self.title_label.setStyleSheet(f"color: {self.theme['text_muted']};")
        for item_data in self.menu_items_map.values():
            item_data["widget"].update_theme(self.theme)
        self.update_ui_state()

    def _to_ui_state_key(self) -> str:
        """将运行态枚举映射到 UI 状态 key。"""
        key = self.ui_state_map.get(self.app_state.value)
        if key:
            return key
        if self.app_state == AppState.STOPPED:
            return "stopped"
        return "running"

    def update_ui_state(self) -> None:
        """同步状态文本和菜单项可用性。"""
        ui_state_key = self._to_ui_state_key()
        state_cfg = APP_CONFIG["header"]["states"].get(ui_state_key, APP_CONFIG["header"]["states"]["stopped"])
        self.status_label.setText(state_cfg["text"])
        self.status_label.setStyleSheet(f"color: {self.theme['text_main']};")
        self.dot_label.setStyleSheet(f"color: {self.theme[state_cfg['dot_color_key']]}; font-size: 14px;")

        # 根据状态刷新菜单项启用禁用。
        for item_data in self.menu_items_map.values():
            allowed_states = item_data["enabled_in"]
            enabled = "all" in allowed_states or ui_state_key in allowed_states
            item_data["widget"].set_item_enabled(enabled)


class AppController:
    """负责 UI、进程、网关和状态机的应用控制器。"""

    def __init__(self):
        # 初始化 Qt 应用与托盘菜单视图。
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.runtime = RuntimeState()
        self.menu_window = CustomTrayMenu(GATEWAY_CONFIG.ui_state_map)
        self.tray_icon = QSystemTrayIcon()

        # 初始化网关协作对象与运行时标记。
        self.process_controller = ProcessController(GATEWAY_CONFIG.cli, self.menu_window)
        self.ws_client = GatewayClient(GATEWAY_CONFIG.ws, self.menu_window)
        self.working_states = set(GATEWAY_CONFIG.working_states)
        self._pending_restart = False
        self._pending_quit = False
        self._auth_failed_terminal = False

        # 初始化状态探测、重连和退出保护定时器。
        self.status_timer = QTimer(self.menu_window)
        self.status_timer.setInterval(GATEWAY_CONFIG.startup.status_poll_ms)
        self.status_timer.timeout.connect(self.process_controller.query_status)
        self.startup_timeout_timer = QTimer(self.menu_window)
        self.startup_timeout_timer.setSingleShot(True)
        self.startup_timeout_timer.timeout.connect(self._on_startup_timeout)
        self.reconnect_timer = QTimer(self.menu_window)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self._connect_gateway_ws)
        self.quit_guard_timer = QTimer(self.menu_window)
        self.quit_guard_timer.setSingleShot(True)
        self.quit_guard_timer.timeout.connect(self.app.quit)
        self.runtime.reset_reconnect(GATEWAY_CONFIG.reconnect.initial_ms)

        # 初始化托盘图标和菜单相关信号。
        self._setup_tray_icon()
        self._bind_menu_signals()
        self._bind_runtime_signals()
        self._set_state(AppState.STOPPED)
        self.tray_icon.show()

    def _setup_tray_icon(self) -> None:
        """配置托盘图标与基础提示信息。"""
        icon_name = APP_CONFIG.get("app", {}).get("icon_path", "anpi.ico")
        icon_path = os.path.join(ASSETS_DIR, icon_name)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            log.warning("tray icon not found: %s", icon_path)
        self.tray_icon.setToolTip(APP_CONFIG.get("app", {}).get("tooltip", "OpenClaw"))
        self.tray_icon.activated.connect(self.on_tray_clicked)

    def _bind_menu_signals(self) -> None:
        """绑定菜单 UI 发出的用户动作信号。"""
        self.menu_window.start_requested.connect(self.cmd_start)
        self.menu_window.stop_requested.connect(self.cmd_stop)
        self.menu_window.restart_requested.connect(self.cmd_restart)
        self.menu_window.exit_requested.connect(self.cmd_exit)
        self.menu_window.script_requested.connect(self.cmd_script)

    def _bind_runtime_signals(self) -> None:
        """绑定进程控制器与网关客户端事件。"""
        self.process_controller.start_dispatched.connect(self._on_cli_start_dispatched)
        self.process_controller.status_ready.connect(self._on_status_ready)
        self.process_controller.stop_finished.connect(self._on_stop_finished)
        self.ws_client.connected.connect(self._on_ws_connected)
        self.ws_client.disconnected.connect(self._on_ws_disconnected)
        self.ws_client.socket_error.connect(self._on_ws_error)
        self.ws_client.challenge_received.connect(self._on_ws_challenge)
        self.ws_client.connect_succeeded.connect(self._on_connect_succeeded)
        self.ws_client.connect_failed.connect(self._on_connect_failed)
        self.ws_client.health_state.connect(self._on_health_state)
        self.ws_client.notify.connect(self.on_notify)

    def _set_state(self, new_state: AppState) -> None:
        """统一更新运行态和菜单视图。"""
        self.runtime.app_state = new_state
        self.menu_window.set_state(new_state)

    def _reset_auth_failure(self) -> None:
        """清空终止型鉴权失败标记。"""
        self._auth_failed_terminal = False

    def _is_gateway_ready(self, status_payload: dict[str, Any]) -> bool:
        """根据状态命令输出判断网关是否已可连接。"""
        rpc_ok = bool(_get_by_dot_path(status_payload, "rpc.ok", False))
        health_ok = bool(_get_by_dot_path(status_payload, "health.healthy", False))
        port_status = str(_get_by_dot_path(status_payload, "port.status", "")).lower()
        listeners = _get_by_dot_path(status_payload, "port.listeners", [])
        has_listener = isinstance(listeners, list) and len(listeners) > 0
        return rpc_ok or health_ok or (port_status != "free" and has_listener)

    def _start_status_probe(self) -> None:
        """启动网关状态轮询与超时控制。"""
        self.status_timer.start()
        self.startup_timeout_timer.start(GATEWAY_CONFIG.startup.status_timeout_ms)
        self.process_controller.query_status()

    def _stop_status_probe(self) -> None:
        """停止状态轮询与启动超时计时。"""
        self.status_timer.stop()
        self.startup_timeout_timer.stop()

    def _connect_gateway_ws(self) -> None:
        """在网关可用后发起 WebSocket 连接。"""
        if not self.runtime.want_running or self._auth_failed_terminal:
            return
        if self.runtime.app_state == AppState.WS_AUTHENTICATING:
            return
        self._set_state(AppState.WS_CONNECTING)
        self.ws_client.open()

    def _schedule_reconnect(self) -> None:
        """按照退避策略安排下一次重连。"""
        if not self.runtime.want_running or self._auth_failed_terminal:
            self._set_state(AppState.STOPPED if not self.runtime.want_running else AppState.ERROR)
            return
        if self.reconnect_timer.isActive():
            return
        delay = self.runtime.reconnect_delay_ms
        self._set_state(AppState.WS_CONNECTING)
        self.reconnect_timer.start(delay)
        self.runtime.bump_reconnect(GATEWAY_CONFIG.reconnect.factor, GATEWAY_CONFIG.reconnect.max_ms)
        log.info("schedule reconnect in %sms", delay)

    def _request_stop_gateway(self) -> None:
        """停止定时任务、断开 WebSocket 并请求关闭网关。"""
        self._stop_status_probe()
        self.reconnect_timer.stop()
        self.ws_client.close()
        self.process_controller.stop_gateway()

    def cmd_start(self) -> None:
        """处理开始运行动作。"""
        self.menu_window.hide()
        self.runtime.want_running = True
        self._pending_restart = False
        self._pending_quit = False
        self._reset_auth_failure()
        self.runtime.reset_reconnect(GATEWAY_CONFIG.reconnect.initial_ms)
        self._set_state(AppState.STARTING_CLI)
        self.process_controller.start_gateway()

    def cmd_stop(self) -> None:
        """处理停止动作。"""
        self.menu_window.hide()
        self.runtime.want_running = False
        self._pending_restart = False
        self._pending_quit = False
        self._reset_auth_failure()
        self._request_stop_gateway()
        self._set_state(AppState.STOPPED)

    def cmd_restart(self) -> None:
        """处理重启动作。"""
        self.menu_window.hide()
        self.runtime.want_running = True
        self._pending_restart = True
        self._pending_quit = False
        self._reset_auth_failure()
        self._request_stop_gateway()
        self._set_state(AppState.STARTING_CLI)

    def cmd_exit(self) -> None:
        """处理退出动作。"""
        self.menu_window.hide()
        self.runtime.want_running = False
        self._pending_restart = False
        self._pending_quit = True
        self._reset_auth_failure()
        self._request_stop_gateway()
        self.quit_guard_timer.start(5000)

    def cmd_script(self, script_name: str) -> None:
        """执行菜单里配置的外部脚本。"""
        self.menu_window.hide()
        target_script = os.path.join(SCRIPTS_DIR, script_name)
        program = target_script if os.path.exists(target_script) else script_name
        try:
            QProcess.startDetached("cmd.exe", ["/c", program])
        except Exception as exc:
            log.warning("run external script failed %s: %s", script_name, exc)

    def _on_cli_start_dispatched(self, ok: bool, err: str) -> None:
        """处理网关启动命令分发结果。"""
        if not ok:
            self._set_state(AppState.ERROR)
            self.on_notify("OpenClaw", f"启动失败: {err}")
            return
        self._start_status_probe()

    def _on_status_ready(self, ok: bool, payload: dict[str, Any], err: str) -> None:
        """处理网关状态轮询结果。"""
        if not self.runtime.want_running:
            return
        if ok and self._is_gateway_ready(payload):
            self._stop_status_probe()
            self._connect_gateway_ws()
            return
        if err:
            log.debug("status probe not ready: %s", err)

    def _on_stop_finished(self, _ok: bool, _msg: str) -> None:
        """处理网关停止命令完成事件。"""
        if self._pending_quit:
            self.app.quit()
            return
        if self._pending_restart:
            self._pending_restart = False
            self.runtime.reset_reconnect(GATEWAY_CONFIG.reconnect.initial_ms)
            self._set_state(AppState.STARTING_CLI)
            self.process_controller.start_gateway()
            return
        if not self.runtime.want_running:
            self._set_state(AppState.STOPPED)

    def _on_startup_timeout(self) -> None:
        """处理网关启动超时。"""
        if not self.runtime.want_running:
            return
        self._stop_status_probe()
        self._set_state(AppState.ERROR)
        self.on_notify("OpenClaw", "网关启动超时，请检查 openclaw 状态")

    def _on_ws_connected(self) -> None:
        """底层 WebSocket 连接建立后更新状态。"""
        if self.runtime.want_running:
            self._set_state(AppState.WS_CONNECTING)

    def _on_ws_disconnected(self) -> None:
        """底层 WebSocket 断开后决定是否重连。"""
        if not self.runtime.want_running:
            self._set_state(AppState.STOPPED)
            return
        self._schedule_reconnect()

    def _on_ws_error(self, message: str) -> None:
        """记录 WebSocket 错误并尝试重连。"""
        log.warning("websocket error: %s", message)
        if self.runtime.want_running and not self._auth_failed_terminal:
            self._schedule_reconnect()

    def _on_ws_challenge(self, nonce: str) -> None:
        """收到 challenge 后构造并发送 connect 请求。"""
        if not self.runtime.want_running:
            return
        self._set_state(AppState.WS_AUTHENTICATING)
        try:
            secrets = GatewaySecrets.load_or_create(GATEWAY_CONFIG.auth_config_path)
            request = build_connect_request(
                secrets=secrets,
                nonce=nonce,
                locale=GATEWAY_CONFIG.locale,
                user_agent=GATEWAY_CONFIG.user_agent,
            )
        except Exception as exc:
            self._on_connect_failed(str(exc))
            return
        self.ws_client.send_connect(request)

    def _on_connect_succeeded(self, payload: dict[str, Any]) -> None:
        """处理 connect 请求成功响应。"""
        if not self.runtime.want_running:
            return
        self._reset_auth_failure()
        self.runtime.reset_reconnect(GATEWAY_CONFIG.reconnect.initial_ms)
        self._set_state(AppState.ONLINE_IDLE)
        device_token = _get_by_dot_path(payload, "auth.deviceToken", "")
        if device_token:
            log.info("gateway connect succeeded with deviceToken")

    def _on_connect_failed(self, message: str) -> None:
        """处理 connect 请求失败响应。"""
        self._auth_failed_terminal = True
        log.warning("gateway auth failed: %s", message)
        self._set_state(AppState.ERROR)
        self.on_notify("OpenClaw", f"网关鉴权失败: {message}")

    def _on_health_state(self, state: str) -> None:
        """根据 health/status 事件更新 UI 状态。"""
        if not self.runtime.want_running:
            return
        if state in self.working_states:
            self._set_state(AppState.ONLINE_WORKING)
        else:
            self._set_state(AppState.ONLINE_IDLE)

    def on_notify(self, title: str, content: str) -> None:
        """显示系统托盘通知。"""
        self.tray_icon.showMessage(title, content)

    def on_tray_clicked(self, reason) -> None:
        """处理托盘图标点击事件。"""
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.Context):
            self.show_menu()

    def show_menu(self) -> None:
        """显示托盘菜单并按系统主题刷新外观。"""
        system_theme = "dark" if is_windows_dark_mode() else "light"
        if self.menu_window.theme_name != system_theme:
            self.menu_window.theme_name = system_theme
            self.menu_window.apply_theme()

        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.menu_window.width() // 2
        y = cursor_pos.y() - self.menu_window.height() - 15
        self.menu_window.move(QPoint(x, y))
        self.menu_window.show()
        self.menu_window.activateWindow()

    def run(self) -> None:
        """进入 Qt 事件循环。"""
        sys.exit(self.app.exec())


if __name__ == "__main__":
    controller = AppController()
    controller.run()
