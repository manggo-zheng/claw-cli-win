# 🚀 Open Claw Manager

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![平台](https://img.shields.io/badge/platform-windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![许可证](https://img.shields.io/badge/license-MIT-green.svg)](https://mit-license.org/)[](LICENSE)

**Open Claw Manager** 是一个为 Open Claw 服务量身定制的、优雅且轻量级的 Windows 系统托盘管理工具。它采用数据驱动设计，允许用户通过简单的 YAML 配置来自定义菜单功能、执行脚本并监控后台进程。

[✨ 核心功能](#-核心功能) | [🚀 快速开始](#-快速开始) | [⚙️ 配置指南](#-配置指南) | [📦 打包发布](#-打包发布)

---

## 📸 预览

[App Screenshot](assets/screenshot_preview.png)

---

## ✨ 核心功能

- 🎨 **自适应主题**：自动检测 Windows 系统深色/浅色模式并无缝切换界面主题。
- 🛠️ **完全数据驱动**：无需修改代码，只需编辑 `menu.yaml` 即可动态增删菜单选项、图标及动作。
- 🛡️ **智能进程管理**：基于 `psutil` 实现进程树精准击杀，确保关闭服务时不会留下孤儿进程（如僵尸 node/java 进程）。

- ⚡ **自定义扩展**：支持 `cmd_default` 通用动作，可轻松将常用的 `.bat` 或 `.cmd` 脚本集成到托盘菜单。
- 📊 **实时状态监控**：内置守护定时器，实时同步后台服务的存活状态至托盘 UI。

---

## 🚀 快速开始

### 方式 A：从源码运行

1. **克隆仓库**
    ```bash
    git clone https://github.com/你的用户名/OpenClawManager.git
    cd OpenClawManager
    ```

2. **安装依赖**

    ```bash
    pip install -r requirements.txt
    ```

3. **启动程序**

    ```bash
    python -m app.main
    ```

### 方法 B：直接运行编译版

前往 [Releases](https://github.com/你的用户名/OpenClawManager/releases) 下载最新的绿色版压缩包，解压后运行 `OpenClawManager.exe` 即可。

---

## ⚙️ 配置指南

项目所有的“灵魂”都存储在 `configs/` 目录下：

### 1. `menu.yaml` (菜单配置)

你可以随意添加组和选项：

```yaml
groups:
  - - id: "my_tool"
      icon: "settings"         # 对应 config.yaml 中的图标名
      text: "运行我的脚本"
      action: "cmd_default"    # 使用通用执行逻辑
      cmd: "myscript.
bat"      # scripts 目录下的文件名
enabled_in: [ "all" ]
```

### 2. `config.yaml` (程序设置)

定义主题颜色、标题以及 SVG 图标资源。


---

## 📂 项目结构

```text
OpenClawManager/
├── app/                # Python 核心逻辑代码
├── assets/             # 静态资源 (图标, 截图)
├── configs/            # YAML 配置文件 (核心)
├── scripts/            # 存放你的 .bat / .cmd 脚本
├── logs/               # 自动生成运行日志
└── build.py            # 一键打包瘦身脚本
```

---

## 🛠️ 技术栈

- **语言:** Python 3.x
- **UI 框架:** PyQt6
- **进程管理:** psutil

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

用户：郑坤淘 项目地址：[https://github.com/manggo-zheng/claw-cli-win]
