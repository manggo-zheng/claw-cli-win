# claw-cli-win

一个通用的 Windows 托盘服务管理器。

它的目标不是给 OpenClaw 单独写一个 GUI，而是提供一个可复用的托盘壳：

- 托盘启动时自动拉起一个 CLI 服务子进程
- 托盘退出时自动关闭这个子进程
- 右键菜单实时显示服务状态
- 右键菜单支持启动、停止、重启、更新和自定义命令
- 所有菜单和命令都由 `config.json` 驱动，换配置即可托管别的服务

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python -m claw_tray --config .\config.json
```

兼容旧习惯：

```powershell
python .\demo.py --config .\config.json
```

## 配置说明

- `service.start`：托盘托管的主服务启动命令。
- `service.status.mode`：默认使用 `managed_process`，直接以子进程生命周期作为状态来源。
- `commands`：可复用的自定义命令，比如更新、打开面板、打开日志。
- `menu_items`：右键菜单定义，支持 `status`、`text`、`separator`、`service_action`、`command`、`app_action`。
- 菜单条件只支持显式的 `states_in` / `states_not_in`，不再使用 `eval`。

## 开发验证

```powershell
python -m unittest discover -s tests
python - <<'PY'
from pathlib import Path
paths = [Path('demo.py')] + sorted(Path('claw_tray').glob('*.py'))
for path in paths:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
print('syntax ok')
PY
```