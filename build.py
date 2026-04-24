# -*- coding: utf-8 -*-
"""
自动化打包脚本
"""

import os
import shutil
import subprocess


def build_project():
    print("开始打包 anpi...")

    # 1. 定义 PyInstaller 打包命令
    # --noconsole: 隐藏背后的 CMD 黑窗口
    # --noconfirm: 覆盖之前打包的旧文件
    # --icon: 设置 exe 的图标
    # --name: 设置 exe 的名字
    command = [
        "pyinstaller",
        "--noconsole",
        "--noconfirm",
        "--icon=assets/anpi.ico",
        "--name=anpi",
        "--exclude-module=PyQt6.QtNetwork",
        "--exclude-module=PyQt6.QtQml",
        "--exclude-module=PyQt6.QtQuick",
        "--exclude-module=PyQt6.QtSql",
        "--exclude-module=PyQt6.QtTest",
        "--exclude-module=PyQt6.QtWebEngine",
        "--exclude-module=PyQt6.QtWebEngineCore",
        "--exclude-module=PyQt6.QtWebEngineWidgets",
        "--exclude-module=PyQt6.QtBluetooth",
        "--exclude-module=PyQt6.QtMultimedia",
        "--exclude-module=PyQt6.QtMultimediaWidgets",
        "--exclude-module=PyQt6.QtNfc",
        "--exclude-module=PyQt6.QtPositioning",
        "--exclude-module=PyQt6.QtSensors",
        "--exclude-module=PyQt6.QtSerialPort",
        "--exclude-module=PyQt6.QtTextToSpeech",
        "--exclude-module=PyQt6.QtWebSockets",
        "--exclude-module=PyQt6.Qt3DCore",
        "--exclude-module=PyQt6.Qt3DRender",
        "--exclude-module=PyQt6.QtPdf",
        "--exclude-module=PyQt6.QtNetwork",
        "--exclude-module=PyQt6.QtQml",
        "--upx-dir=.",
        "main.py"
    ]

    # 2. 执行打包
    subprocess.run(command, check=True)

    # 3. 打包完成后，整理目录
    print("\n编译完成，正在拷贝配置文件和依赖资源...")

    dist_dir = os.path.join("dist", "anpi")

    # 需要拷贝到 exe 同级目录的文件夹
    folders_to_copy = ["configs", "scripts", "assets"]

    for folder in folders_to_copy:
        src = folder
        dst = os.path.join(dist_dir, folder)
        if os.path.exists(src):
            # 如果目标文件夹已存在，先删除，保持最新
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"已拷贝 -> {folder}/")

    print("\n✅ 打包成功！")
    print(f"请前往 {os.path.abspath(dist_dir)} 找到你的 exe 程序。")


if __name__ == "__main__":
    build_project()
