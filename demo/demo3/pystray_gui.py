# -*- coding: utf-8 -*-
"""

"""
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw, ImageFont
import sys

# --- 全局状态变量 ---
# 用于记录服务是否正在运行
is_service_running = False


# --- 托盘图标生成 ---
def create_tray_icon():
    # 生成一个类似原型图右下角的托盘图标 (黑底，带个红点)
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (30, 30, 30, 255))
    dc = ImageDraw.Draw(image)

    # 画一个简单的终端符号 ">_"
    dc.text((10, 15), ">_", fill=(200, 200, 200), font_size=24)

    # 画右下角的红点
    dot_radius = 8
    dot_x = width - dot_radius * 2 - 5
    dot_y = height - dot_radius * 2 - 5
    dc.ellipse(
        (dot_x, dot_y, dot_x + dot_radius * 2, dot_y + dot_radius * 2),
        fill=(255, 50, 50, 255)
    )
    return image


# --- 菜单动作处理函数 ---
def on_start(icon, item):
    global is_service_running
    is_service_running = True
    print("服务已启动...")
    # 在某些系统上可能需要手动更新菜单
    # icon.update_menu()


def on_stop(icon, item):
    global is_service_running
    is_service_running = False
    print("服务已停止...")


def on_restart(icon, item):
    print("重启服务中...")


def on_check_updates(icon, item):
    print("检查更新...")


def on_show_status(icon, item):
    print("显示状态窗口...")


def on_settings(icon, item):
    print("打开设置...")


def on_exit(icon, item):
    print("退出管理器...")
    icon.stop()
    sys.exit()


# --- 动态状态判断函数 ---
def get_status_text(item):
    """动态返回状态文本和前面的圆点"""
    if is_service_running:
        return "🟢 Running"
    else:
        return "🔴 Stopped"


def is_start_enabled(item):
    """如果服务没运行，则允许点击 Start"""
    return not is_service_running


def is_stop_enabled(item):
    """如果服务正在运行，则允许点击 Stop"""
    return is_service_running


# --- 构建菜单结构 ---
# 注意：我们使用 Unicode 字符来模拟原型图中的图标
menu = Menu(
    # 头部标题 (设置为不可点击)
    item('OPEN CLAW SERVICE', None, enabled=False),

    # 动态状态显示 (设置为不可点击)
    item(get_status_text, None, enabled=False),

    # 分割线
    Menu.SEPARATOR,

    # 服务控制组
    item('▷  Start Service', on_start, enabled=is_start_enabled),
    item('◻  Stop Service', on_stop, enabled=is_stop_enabled),
    item('↻  Restart Service', on_restart),
    item('⭳  Check for Updates', on_check_updates),

    # 分割线
    Menu.SEPARATOR,

    # 界面控制组
    item('📈 Show Status Window', on_show_status),
    item('⚙  Settings', on_settings),

    # 分割线
    Menu.SEPARATOR,

    # 退出 (无法单独设置红色字体，所以加上显眼的红色叉号)
    item('❌ Exit Manager', on_exit)
)

# --- 启动系统托盘 ---
if __name__ == "__main__":
    # 创建托盘对象
    icon = pystray.Icon(
        "claw_manager",
        create_tray_icon(),
        "Open Claw Manager",  # 鼠标悬停时的提示文字
        menu
    )

    print("系统托盘已启动，请查看系统右下角。")
    # 运行托盘程序 (这会阻塞主线程)
    icon.run()