import json
import subprocess
from infi.systray import SysTrayIcon

# Windows 隐藏 CMD 窗口的特定标志
CREATE_NO_WINDOW = 0x08000000


class ServiceManager:
    """负责管理 CLI 子进程"""

    def __init__(self, main_command):
        self.main_command = main_command
        self.process = None

    def start(self):
        if self.process and self.process.poll() is None:
            return  # 已经在运行

        # 隐藏黑框启动
        self.process = subprocess.Popen(
            self.main_command,
            shell=True,
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process = None

    def run_custom(self, cmd):
        subprocess.run(cmd, shell=True, creationflags=CREATE_NO_WINDOW)


class TrayApp:
    def __init__(self, config_file, icon_path):
        # 1. 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.service = ServiceManager(self.config["main_command"])
        self.icon_path = icon_path

        # 2. 将 JSON 配置解析为 infi.systray 需要的元组列表
        menu_options = self._build_menu_from_config()

        # 3. 初始化托盘对象 (图标路径, 悬浮提示文字, 菜单选项)
        self.systray = SysTrayIcon(
            self.icon_path,
            self.config["app_name"],
            menu_options,
            on_quit=self._on_quit  # 绑定默认的退出事件
        )

    def _build_menu_from_config(self):
        """将配置列表映射为 infi.systray 的菜单元组: (菜单文本, 图标路径(可为None), 回调函数)"""
        menu_options = []

        for item in self.config["menu_items"]:
            action_type = item.get("action")
            label = item.get("label")

            # infi.systray 不原生支持单独的分隔符，通常用空或者略过，这里我们略过分隔符配置
            if action_type == "separator":
                continue

            # 这里依然需要使用默认参数来固定闭包中的 action 和 cmd
            def callback(systray_obj, action=action_type, cmd=item.get("cmd")):
                if action == "start_main":
                    self.service.start()
                elif action == "stop_main":
                    self.service.stop()
                elif action == "run_custom":
                    self.service.run_custom(cmd)

            # 组装元组: (显示文本, 菜单项图标(不需要填None), 回调)
            menu_options.append((label, None, callback))

        return tuple(menu_options)  # infi.systray 要求是 tuple 或 list

    def _on_quit(self, systray_obj):
        """右键菜单自带一个 Quit 选项，退出前确保杀掉服务"""
        self.service.stop()

    def run(self):
        # 启动时自动运行服务
        self.service.start()
        # 启动托盘 (阻塞当前线程，直到退出)
        self.systray.start()


if __name__ == "__main__":
    # 请确保同级目录下有一个 app.ico 文件，否则会报错
    app = TrayApp("config.json", "app.ico")
    app.run()