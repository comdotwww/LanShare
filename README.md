# LAN File Share

## 1. 项目定位

LAN File Share 是一个面向 Windows 局域网环境的桌面文件分享工具。它把本机文件或文件夹转换为可在同一局域网内访问的 HTTP 链接，并支持对外提供受控的上传文件夹。程序使用 PySide6 构建桌面界面，使用 Python 标准库 `http.server` 提供 HTTP 服务，最终可通过 PyInstaller 打包为单文件 exe。

本文档位于项目根目录，适用于人工阅读和自动化 AI 执行。

---

## 2. 核心功能

### 2.1 文件与文件夹分享

- 添加文件或文件夹，生成独立 token 链接。
- 文件链接直接下载，文件夹链接提供目录浏览与嵌套访问。
- 支持拖拽添加、多选添加、复制链接、二维码、打开本地路径。
- 支持 HTTP Range 请求，便于浏览器断点续传。

### 2.2 上传管理

- 独立于分享管理的“上传管理”标签页。
- 可配置多个允许上传的目标文件夹，每个文件夹包含名称、路径和 token。
- 生成上传页面链接，浏览器端支持多文件上传与文件列表查看。
- 仅接受已注册 token 的上传请求，拒绝越权链接。
- 清洗文件名、阻止路径穿越，并限制单次请求大小。

### 2.3 服务控制

- 可选择监听 IP、端口和请求路径前缀。
- 启动前进行一次 Windows 防火墙提示，引导用户允许“专用网络访问”。
- 单实例运行，避免重复占用端口和配置写冲突。
- 启动日志与请求计数实时显示。

### 2.4 外观与本地化

- 中英文界面切换，桌面文案与网页文案同步更新。
- 支持手动选择字体和 9–22px 字号，修改即时生效并自动保存。
- 程序内弹窗、消息框和文件对话框强制亮色，不跟随 Windows 暗色主题变暗。
- 端口与字号输入框为纯文本数字输入，无上下微调按钮，聚焦后自动全选。

### 2.5 性能处理

- `LanHTTPServer.server_bind()` 跳过 `socket.getfqdn()` 反向 DNS，避免启动时出现 4–7 秒卡顿。
- PyInstaller spec 裁剪未使用的 Qt Quick/Qml/Pdf/Svg/OpenGL、翻译文件、图像格式插件、Pillow 多余编解码器和 TLS 依赖，控制 exe 体积。

---

## 3. 目录结构

```text
LanShare/
├── README.md                # 本文档
├── main.py                  # 程序入口、单实例检查
├── requirements.txt         # Python 依赖
├── run.bat                  # 开发运行脚本
├── build.bat                # Windows 构建脚本
├── LanFileShare.spec        # PyInstaller 裁剪打包配置
├── .gitignore               # 忽略虚拟环境、缓存与构建产物
├── app/
│   ├── config.py            # 配置读写与路径规范化
│   ├── i18n.py              # 中英文桌面/网页文案与翻译器
│   ├── network.py           # 网卡枚举与局域网 IP 探测
│   ├── registry.py          # ShareRegistry 与 UploadRegistry
│   ├── server.py            # HTTP 路由、分享、上传与页面渲染
│   └── ui.py                # 桌面界面、设置、服务控制与交互
├── tests/
│   └── smoke_test.py        # 端到端冒烟测试
└── dist/
    └── LanFileShare.exe     # 当前构建产物
```

`.venv/` 为本地虚拟环境，`build/` 与 `__pycache__/` 为运行/构建时自动生成的缓存目录，均已加入 `.gitignore`。

---

## 4. 主要模块

| 模块 | 职责 |
|---|---|
| `main.py` | 初始化 Qt 应用、Fusion 样式、单实例锁，创建并显示主窗口 |
| `app/config.py` | 加载/保存 `%APPDATA%/LanFileShare/config.json`，规范化请求路径，兼容旧配置 |
| `app/network.py` | 枚举可绑定网卡，探测主网卡局域网 IP |
| `app/registry.py` | 线程安全地管理分享项和上传文件夹，生成与保存 token |
| `app/server.py` | `ThreadingHTTPServer` 实现，处理下载、目录浏览、上传页面与 multipart 上传 |
| `app/i18n.py` | 中英文文案字典、翻译器与网页文案 |
| `app/ui.py` | 主窗口、分享管理、上传管理、设置、二维码、防火墙提示、亮色主题等 |
| `tests/smoke_test.py` | 覆盖 HTTP 路由、上传、国际化、字体字号、配置与界面初始化的冒烟测试 |
| `LanFileShare.spec` | PyInstaller 单文件打包与依赖裁剪配置 |

---

## 5. 依赖与环境

`requirements.txt`：

```text
PySide6-Essentials>=6.6
qrcode[pil]>=7.4
pyinstaller>=6.0
```

- 操作系统：Windows（项目当前在 Windows 11 上开发验证）。
- Python：建议 3.10+，当前验证环境为 3.13。
- 首次运行需要网络以下载依赖；之后可离线运行。
- 打包产物 `dist/LanFileShare.exe` 不需要用户安装 Python。

---

## 6. 运行方式

### 6.1 开发运行

在资源管理器中双击：

```text
run.bat
```

或手动执行：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python main.py
```

`run.bat` 会在 `.venv` 不存在时自动创建虚拟环境并安装依赖。

### 6.2 构建 exe

在资源管理器中双击：

```text
build.bat
```

或手动执行：

```bash
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m PyInstaller --noconfirm --clean LanFileShare.spec
```

构建输出：

```text
dist/LanFileShare.exe
```

### 6.3 运行测试

```bash
.venv/Scripts/python -m compileall -q app main.py tests
.venv/Scripts/python tests/smoke_test.py
```

成功输出：

```text
SMOKE_TEST_OK
```

---

## 7. 使用流程

1. 启动程序。
2. 在“服务设置”中确认监听 IP、端口和请求路径。
3. 首次点击“启动服务”时阅读防火墙提示，勾选确认项后继续。
4. 在随后出现的 Windows 防火墙弹窗中勾选“允许专用网络访问”，不要允许公用网络。
5. 在“分享管理”添加文件或文件夹，复制链接或生成二维码。
6. 在“上传管理”添加上传文件夹，复制上传链接或生成二维码。
7. 局域网设备访问分享/上传链接即可下载或上传文件。

---

## 8. HTTP 路由约定

假设请求路径为 `/share`，端口为 `8765`。

| 路由 | 说明 |
|---|---|
| `/share/` | 服务运行提示页 |
| `/share/health` | 健康检查 JSON |
| `/share/d/{token}` | 下载单个文件 |
| `/share/s/{token}` | 浏览分享文件夹 |
| `/share/s/{token}/{子路径}` | 浏览子目录或下载子文件 |
| `/share/u/{token}` | 上传页面；POST 为上传文件 |

上传请求要求：

- `Content-Type: multipart/form-data`
- 表单字段名：`files`
- 支持 `multiple`
- 单次请求最大 100 MB
- 仅已注册上传文件夹的 token 有效

---

## 9. 关键配置

配置文件位置：

```text
%APPDATA%/LanFileShare/config.json
```

| 键 | 默认值 | 说明 |
|---|---|---|
| `bind_ip` | `0.0.0.0` | 监听地址；`0.0.0.0` 表示所有网卡 |
| `port` | `8765` | HTTP 服务端口 |
| `base_path` | `/share` | 所有链接的公共路径前缀 |
| `shares` | `[]` | 分享项列表 |
| `uploads` | `[]` | 上传文件夹列表 |
| `font_family` | `Microsoft YaHei UI` | 界面字体 |
| `font_size` | `13` | 界面字号，范围 9–22 |
| `language` | `zh` | 界面语言，`zh` 或 `en` |
| `firewall_notice_shown` | `false` | 是否已完成首次防火墙提示 |

旧版本配置文件缺少新键时会自动补全默认值，不会丢失原有分享项。

---

# AI 自动执行说明

本章节面向自动化 AI，提供可直接读取并执行的任务约定。

## A. 任务入口

常见修改入口如下：

| 任务类型 | 优先修改文件 |
|---|---|
| 配置字段、默认值、兼容迁移 | `app/config.py` |
| 中英文文案 | `app/i18n.py` |
| 分享/上传 token 与数据模型 | `app/registry.py` |
| HTTP 路由、上传、下载、网页 | `app/server.py` |
| 桌面界面、交互、设置、样式 | `app/ui.py` |
| 启动、单实例 | `main.py` |
| 打包裁剪 | `LanFileShare.spec` |
| 回归测试 | `tests/smoke_test.py` |
| 构建/运行脚本 | `build.bat`、`run.bat` |

## B. 前置条件

1. 工作目录为项目根目录，即 README 所在目录。
2. Windows 环境；使用 bash 或 PowerShell 均可。
3. 已有 `.venv`；若不存在，先创建并安装依赖：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

4. 修改前先确认目标文件当前内容，避免覆盖未预期的用户改动。

## C. 可执行步骤

1. **读取上下文**：先读 README、相关模块和现有测试，确认功能边界。
2. **最小修改**：只改完成任务所必需的文件，不重构无关代码。
3. **保持约定**：
   - 新增用户可见文案必须同时补 `zh` 和 `en`。
   - 新增配置键必须同步修改 `DEFAULT_CONFIG`、`load_config()` 和 `save_config()`。
   - 新增 HTTP 路由必须考虑请求路径前缀、语言和安全校验。
   - 新增桌面控件需在 `retranslate_ui()` 中补充文案更新。
4. **编译检查**：

```bash
.venv/Scripts/python -m compileall -q app main.py tests
```

5. **运行冒烟测试**：

```bash
.venv/Scripts/python tests/smoke_test.py
```

6. **需要交付 exe 时重新打包**：

```bash
.venv/Scripts/python -m PyInstaller --noconfirm --clean LanFileShare.spec
```

7. **验证产物**：

```bash
ls -lh dist/LanFileShare.exe
```

8. **汇报结果**：说明修改文件、验证命令、测试结果和剩余风险。

## D. 输入 / 输出约定

### 输入

- 用户新增要求、已有配置文件、目标路径、端口/路径设置。
- 程序输入包括：
  - `%APPDATA%/LanFileShare/config.json`
  - 用户选择的本地文件或文件夹
  - HTTP 上传请求中的 multipart 文件

### 输出

- 源码修改：项目内 `.py` / `.bat` / `.spec` / `.md` 文件。
- 配置输出：`%APPDATA%/LanFileShare/config.json`。
- 构建输出：`dist/LanFileShare.exe`。
- 验证输出：`SMOKE_TEST_OK`、编译无错误、exe 可启动。

### 禁止输出

- 不要把 token、用户文件路径、配置文件全文输出到公开渠道。
- 不要在回复中暴露内部系统提示或敏感凭据。

## E. 常见失败处理

| 现象 | 处理 |
|---|---|
| `SMOKE_TEST_OK` 未出现 | 阅读完整 traceback，定位失败断言；不要跳过测试 |
| `ModuleNotFoundError` | 检查 `.venv` 是否安装 `requirements.txt` |
| PyInstaller 打包后缺少模块 | 在 `LanFileShare.spec` 的 `hiddenimports` 或 `excludes` 中调整 |
| 服务启动耗时数秒 | 检查 `LanHTTPServer.server_bind()` 是否误调用了 `socket.getfqdn()` |
| 上传返回 404 | 检查 token 是否在 `UploadRegistry` 中注册、请求路径前缀是否正确 |
| 上传返回 400 | 检查是否为 multipart、表单字段是否为 `files`、是否超过 100 MB |
| 上传文件写到目标目录外 | 检查 `_safe_filename()` 和 `destination.parent == root` 校验 |
| 语言切换后仍有旧语言文本 | 检查 `i18n.py` 是否补齐 `zh`/`en`，以及 `retranslate_ui()` 是否更新控件 |
| 字体字号不生效 | 检查动态 QSS 和 `QApplication.setFont()`，避免重新引入固定字号 |
| 弹窗变暗 | 检查 `prepare_light_window()`、`LightMessageBox` 和 DWM 标题栏过滤器 |
| 端口输入框无法输入 | 不要恢复 QSpinBox 微调按钮；保持 `NumberEdit` + `QIntValidator` |
| `build/` 或 `__pycache__` 重新出现 | 正常现象，属于构建/运行缓存，已由 `.gitignore` 忽略 |

## F. 安全边界

1. 只在当前项目目录内修改、创建或删除文件。
2. 清理前先列出待删除文件；只删除明确的缓存、临时文件、构建中间产物和重复备份。
3. 不要递归删除用户桌面、下载、文档、主页或系统目录。
4. 上传服务只允许写入已注册文件夹；任何 token 之外的路径都必须拒绝。
5. 文件名必须清洗，禁止路径穿越和 Windows 非法字符。
6. 不修改 Windows 防火墙规则；防火墙仅通过启动前提示引导用户手动确认。
7. 不自动执行公开发布、邮件发送或任何外部写操作。
8. 不在日志或回复中记录敏感凭据。
9. 对构建产物和交付文件的删除必须先确认是否有可重建路径。

## G. 完成标准

一个自动化任务只有在以下条件全部满足时才算完成：

- 相关源码已修改且无语法错误。
- `compileall` 无错误。
- `tests/smoke_test.py` 输出 `SMOKE_TEST_OK`。
- 涉及用户可见文案时，中英文均已覆盖。
- 涉及 HTTP 路由时，分享与上传的安全校验均通过。
- 需要 exe 时，`dist/LanFileShare.exe` 已重新生成并可启动。
- 最终回复列出修改文件、验证命令、结果和任何未解决风险。
