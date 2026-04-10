from __future__ import annotations

from dataclasses import dataclass
import re
import threading
import time
from typing import Callable

from PIL import Image, ImageDraw
import pystray

from .config import AppConfig, CommandConfig, MenuItemConfig
from .process_manager import CommandResult, ProcessManager, run_command


@dataclass
class RuntimeState:
    service_state: str = "stopped"
    service_pid: int | None = None
    last_exit_code: int | None = None
    last_error: str = ""
    last_command_message: str = ""


class TrayApplication:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.runtime = RuntimeState()
        self._lock = threading.RLock()
        self._manager = ProcessManager(config.service)
        self._stop_event = threading.Event()

        self.icon = pystray.Icon(
            name="claw_tray",
            icon=self._build_icon("stopped"),
            title=self._render_template(self.config.tooltip_template),
            menu=self._build_menu(),
        )

    def run(self) -> None:
        self._refresh_runtime(force_status_probe=True)
        if self.config.service.auto_start:
            self._manager.start()
            self._refresh_runtime(force_status_probe=True)

        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()
        self.icon.run()

    def stop(self) -> None:
        self._stop_event.set()
        self._manager.close()
        self.icon.stop()

    def _monitor_loop(self) -> None:
        interval = max(self.config.service.status.refresh_interval_seconds, 0.5)
        while not self._stop_event.is_set():
            self._refresh_runtime(force_status_probe=True)
            time.sleep(interval)

    def _refresh_runtime(self, force_status_probe: bool) -> None:
        with self._lock:
            snapshot = self._manager.refresh()
            state = snapshot.state
            if force_status_probe and self.config.service.status.mode == "command":
                state = self._probe_status()

            self.runtime.service_state = state
            self.runtime.service_pid = snapshot.pid
            self.runtime.last_exit_code = snapshot.last_exit_code
            self.runtime.last_error = snapshot.last_error

            self.icon.icon = self._build_icon(state)
            self.icon.title = self._render_template(self.config.tooltip_template)
            self.icon.update_menu()

    def _probe_status(self) -> str:
        command = self.config.service.status.command
        if command is None:
            return self.runtime.service_state
        result = run_command(_force_wait(command), capture_output=True)
        if result.returncode not in command.success_codes:
            self.runtime.last_command_message = result.stderr.strip() or "status command failed"
            return "failed"

        output = (result.stdout or result.stderr).strip()
        if not output:
            return "unknown"

        regex = self.config.service.status.regex
        raw_value = output
        if regex:
            match = re.search(regex, output)
            if not match:
                return "unknown"
            raw_value = match.group(self.config.service.status.regex_group)

        return self.config.service.status.mapping.get(raw_value, raw_value)

    def _build_menu(self) -> pystray.Menu:
        items = [self._build_menu_item(item) for item in self.config.menu_items]
        return pystray.Menu(*items)

    def _build_menu_item(self, item: MenuItemConfig) -> pystray.MenuItem:
        if item.item_type == "separator":
            return pystray.Menu.SEPARATOR

        if item.item_type in {"status", "text"}:
            return pystray.MenuItem(
                lambda _: self._render_template(item.label),
                None,
                enabled=False,
                visible=lambda _: self._is_visible(item),
            )

        if item.item_type == "service_action":
            return pystray.MenuItem(
                lambda _: self._render_template(item.label),
                self._wrap_async(lambda: self._handle_service_action(item.action or "")),
                enabled=lambda _: self._is_enabled(item),
                visible=lambda _: self._is_visible(item),
            )

        if item.item_type == "app_action":
            return pystray.MenuItem(
                lambda _: self._render_template(item.label),
                self._wrap_async(lambda: self._handle_app_action(item.action or "")),
                enabled=lambda _: self._is_enabled(item),
                visible=lambda _: self._is_visible(item),
            )

        if item.item_type == "command":
            return pystray.MenuItem(
                lambda _: self._render_template(item.label),
                self._wrap_async(lambda: self._handle_custom_command(item)),
                enabled=lambda _: self._is_enabled(item),
                visible=lambda _: self._is_visible(item),
            )

        raise ValueError(f"Unsupported menu item type: {item.item_type}")

    def _handle_service_action(self, action: str) -> None:
        if action == "start":
            self._manager.start()
        elif action == "stop":
            self._manager.stop()
        elif action == "restart":
            self._manager.restart()
        else:
            self.runtime.last_command_message = f"Unsupported service action: {action}"
        self._refresh_runtime(force_status_probe=True)

    def _handle_app_action(self, action: str) -> None:
        if action == "refresh":
            self._refresh_runtime(force_status_probe=True)
            return
        if action == "exit":
            self.stop()
            return
        self.runtime.last_command_message = f"Unsupported app action: {action}"
        self._refresh_runtime(force_status_probe=False)

    def _handle_custom_command(self, item: MenuItemConfig) -> None:
        command = self._resolve_command(item)
        if command is None:
            self.runtime.last_command_message = f"Command not found: {item.command_ref}"
            self._refresh_runtime(force_status_probe=False)
            return

        result = run_command(command, capture_output=command.wait)
        self.runtime.last_command_message = _format_command_result(result)
        self._refresh_runtime(force_status_probe=True)

    def _resolve_command(self, item: MenuItemConfig) -> CommandConfig | None:
        if item.command is not None:
            return item.command
        if item.command_ref is not None:
            return self.config.commands.get(item.command_ref)
        return None

    def _is_visible(self, item: MenuItemConfig) -> bool:
        return item.visible_when.matches(self.runtime.service_state)

    def _is_enabled(self, item: MenuItemConfig) -> bool:
        return item.enabled_when.matches(self.runtime.service_state)

    def _render_template(self, template: str) -> str:
        labels = self.config.service.status.state_labels
        context = {
            "app_name": self.config.app_name,
            "service_state": self.runtime.service_state,
            "service_label": labels.get(self.runtime.service_state, self.runtime.service_state),
            "service_pid": str(self.runtime.service_pid or "-"),
            "last_exit_code": str(self.runtime.last_exit_code if self.runtime.last_exit_code is not None else "-"),
            "last_error": self.runtime.last_error or "-",
            "last_command_message": self.runtime.last_command_message or "-",
        }
        rendered = template
        for key, value in context.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    def _build_icon(self, state: str) -> Image.Image:
        size = self.config.icons.size
        color = self.config.icons.colors.get(state, self.config.icons.colors["unknown"])
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        padding = max(4, size // 8)
        draw.ellipse((padding, padding, size - padding, size - padding), fill=color)
        return image

    def _wrap_async(self, func: Callable[[], None]) -> Callable[[pystray.Icon, pystray.MenuItem], None]:
        def handler(icon: pystray.Icon, item: pystray.MenuItem) -> None:
            threading.Thread(target=func, daemon=True).start()

        return handler


def _force_wait(command: CommandConfig) -> CommandConfig:
    return CommandConfig(
        command=command.command,
        args=command.args,
        shell=command.shell,
        cwd=command.cwd,
        hide_window=command.hide_window,
        wait=True,
        env=command.env,
        success_codes=command.success_codes,
    )


def _format_command_result(result: CommandResult) -> str:
    if result.pid is not None:
        return f"started pid={result.pid}"
    output = result.stdout.strip() or result.stderr.strip()
    if output:
        return output
    return f"exit_code={result.returncode}"
