import pystray
from PIL import Image
import subprocess
import json
import threading
import time
import re  # 导入正则模块


class TrayApp:
    def __init__(self, config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.status = "stopped"
        self.icon = pystray.Icon(
            "Manager",
            self._create_image("gray"),
            self.config["app_name"],
            menu=pystray.Menu(lambda: self._menu_factory())
        )

        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _create_image(self, color):
        return Image.new('RGB', (64, 64), color=color)

    def _get_status_via_regex(self):
        """核心逻辑：运行命令并用正则解析结果"""
        cfg = self.config["status_check"]
        try:
            # 1. 执行检测命令
            output = subprocess.getoutput(cfg["cmd"])

            # 2. 正则匹配
            # 使用 search 查找整个输出文本
            match = re.search(cfg["regex"], output)

            if match:
                # 获取第一个捕获组的值 (即 \w+ 匹配到的部分)
                raw_value = match.group(1)

                # 3. 根据映射表转换状态
                # mapping.get(raw_value, "stopped") 表示如果没搜到对应映射，默认停止
                return cfg["mapping"].get(raw_value, "stopped")

            return "stopped"  # 没匹配到正则，认为没运行
        except Exception as e:
            print(f"检测出错: {e}")
            return "stopped"

    def _monitor_loop(self):
        interval = self.config.get("monitor_interval", 2)
        print(f"[*] 正则监控已启动，命令: {self.config['status_check']['cmd']}")

        while self.running:
            # 调用正则提取函数
            new_status = self._get_status_via_regex()

            if new_status != self.status:
                print(f"\n[!] 状态变更 (正则提取): {self.status} -> {new_status}")
                self.status = new_status
                self.icon.icon = self._create_image("green" if self.status == "running" else "gray")

            time.sleep(interval)

    def _menu_factory(self):
        items = []
        for item in self.config["menu_items"]:
            label = item["label"].replace("%status%", self.status)
            if item["condition"] == "always" or eval(item["condition"], {"status": self.status}):
                if item.get("type") == "text":
                    items.append(pystray.MenuItem(label, lambda: None, enabled=False))
                else:
                    handler = self._create_handler(item["action"])
                    items.append(pystray.MenuItem(label, handler))
        return items

    def _create_handler(self, action):
        def handler(icon, item):
            print(f"[*] 执行: {action}")
            subprocess.Popen(action, shell=True, creationflags=0x08000000)

        return handler

    def run(self):
        self.icon.run()


if __name__ == "__main__":
    app = TrayApp("config.json")
    app.run()