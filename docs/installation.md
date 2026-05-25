# Installation

qmtserver 服务端运行在 Windows 上，并依赖 Python 3.12/3.13、MiniQMT / QMT 客户端和
`xtquant`。

## 环境要求

- Windows
- Python 3.12 or 3.13
- uv
- 已启动并登录的 MiniQMT / QMT 客户端

服务端支持范围由 `pyproject.toml` 的 `requires-python` 决定，当前为
`>=3.12,<3.14`。这是因为 MiniQMT / QMT / `xtquant` 目前只面向 Windows，且
`xtquant` 暂不支持 Python 3.14。

其他系统可以通过 HTTP、WebSocket 或 Python SDK 作为客户端访问 Windows 上运行的
qmtserver。

## 初始化项目环境

```powershell
uv sync
```

## 安装 xtquant

qmtserver 默认不把 `xtquant` 放进主依赖，因为客户端 SDK 和部分开发任务不需要直连
MiniQMT。需要本机连接 MiniQMT 时，可以选择下面两种方式。

CI 固定使用 Windows runner 并安装 `xtquant` extra；不规划 Linux/macOS 服务端 CI。

### 方式一：安装 PyPI 版本

如果只想快速初始化，可以安装 PyPI 上的 `xtquant` 版本。Python 3.12/3.13 需要
`xtquant>=250516.1.1`：

```powershell
uv sync --extra xtquant
```

### 方式二：下载新版并覆盖安装

如果 PyPI 版本落后于券商客户端随附或迅投发布的版本，可以从迅投知识库下载新版：

- [xtquant 版本下载](https://dict.thinktrader.net/nativeApi/download_xtquant.html)

覆盖安装步骤：

1. 正常同步项目环境：

```powershell
uv sync
```

2. 从上面的下载页下载需要的 `xtquant` 压缩包，并解压到临时目录。解压后应能看到
   `xtquant` 文件夹。

3. 将解压出来的 `xtquant` 文件夹复制到当前项目虚拟环境：

```text
.venv\Lib\site-packages\xtquant
```

如果该目录已经存在，先关闭正在运行的 Python、qmtserver、Notebook 等进程，然后用新版
`xtquant` 文件夹覆盖旧目录。

也可以先安装 PyPI 版本，再用下载的新版本覆盖：

```powershell
uv sync --extra xtquant
```

4. 验证导入路径：

```powershell
uv run python -c "import xtquant; print(xtquant.__file__)"
```

输出路径应位于当前项目的 `.venv\Lib\site-packages\xtquant` 下。

如果以后删除并重建 `.venv`，需要重新执行 PyPI 安装或覆盖安装步骤。
