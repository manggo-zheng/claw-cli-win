import pystray
from PIL import Image
import subprocess
import json


class TrayApp:
    def __init__(self, config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.status = "stopped"
        self.icon = pystray.Icon("Manager",
                                 Image.open(self.config["icon_path"]),
                                 self.config["app_name"])

        # 预定义回调字典，这样 MenuItem 就只绑定明确的方法名
        self.icon.menu = self._build_menu()

    def _build_menu(self):
        menu_items = []
        for item in self.config["menu_items"]:
            if item["condition"] == "always" or eval(item["condition"], {"status": self.status}):
                # 2. 这里不使用闭包，而是根据 action 名字动态指向一个特定的方法
                # 将 action 名称存入菜单项的 text 中，或者创建一个唯一的名称方法
                action_name = item["action"]
                action_type = item["type"]

                # 创建一个具名的方法，名字由 action 决定
                # 这样 pystray 看到的就是一个标准的 def func(icon, item)
                handler = self._create_handler(action_type, action_name)
                menu_items.append(pystray.MenuItem(item["label"], handler))

        return pystray.Menu(*menu_items)

    def _create_handler(self, action_type, action_name):
        def handler(icon, item):
            try:
                if action_type == "cmd":
                    subprocess.Popen(action_name, shell=True, creationflags=0x08000000)
                elif action_type == "func":
                    getattr(self, action_name)()
            except Exception as e:
                print(f"执行出错: {e}")

            # 更新状态
            self._update_status()
            self.icon.menu = self._build_menu()

        return handler

    def _update_status(self):
        res = subprocess.getoutput('tasklist | findstr notepad.exe')
        self.status = "running" if "notepad.exe" in res else "stopped"
        self.icon.icon = Image.new('RGB', (64, 64), color='green' if self.status == 'running' else 'gray')

    # --- 具体的业务逻辑 ---
    def check_health(self):
        print("执行健康检查...")

    def exit_app(self):
        self.icon.stop()

    def run(self):
        self.icon.run()


if __name__ == "__main__":
    app = TrayApp("config.json")
    app.run()