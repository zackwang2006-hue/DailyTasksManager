# 计划炼金台 ScheduleApp 2.0.1

一个基于 Python + PySide6 开发的桌面任务管理软件。支持四种任务分类和计划体系（日／周／月／季／年／五年），提供桌面悬浮窗、每日打卡、历史记录、优先级别、富文本速记、AI 周期报告自动生成与邮件发送等功能。

项目目标是做一个轻量但实用的个人日程管理工具，让任务不只是被记录下来，而是能在桌面上持续提醒、分类展示，并通过打卡和历史记录形成可追踪的完成反馈。

---

## 已实现的主要功能

### 任务管理
- 支持创建、编辑、删除任务
- 任务描述、截止时间、优先级别（重要／紧急）、固定事件时间
- 任务置顶显示，按截止时间颜色提示
- 最小行动（Minimal Action）——将大任务拆解为最小可执行步骤
- 任务完成后自动进入历史记录

### 计划体系（Plan System）
- 多层级计划：**日计划、周计划、月计划、季计划、年计划、五年计划**
- 每个层级独立展示任务卡片，支持上下期切换
- 每日任务可从计划层级规则自动生成（如每天写日记）
- 每日任务归档与过期管理

### 每日打卡
- 每日任务独立打卡页面
- 日历网格展示打卡状态（完成／未完成／未来／跳过）
- 统计连续坚持天数（Streak）
- 每日 00:00 自动刷新当日打卡状态

### 历史记录
- 按日期查看已完成任务记录
- 日历区域与完成记录区域分区显示，可拖动分隔条调整大小
- 支持查看完成备注

### 桌面悬浮窗
- 桌面悬浮任务清单，始终置顶可选
- 筛选模式：今日截止、近三日、近七日、全部任务
- 透明度调节，折叠／展开
- 自动贴边吸附与自动隐藏
- 右键菜单快速完成、置顶、打开主窗口
- **快速速记（Quick Note）**：悬浮窗内直接打开富文本编辑器

### 快速速记（Quick Note）
- 富文本编辑器，支持字体、字号、粗体、斜体、标题、正文样式
- 图片插入（剪贴板粘贴 / 文件拖入）
- 图片批注（画笔、擦除、颜色、粗细可调，支持撤销／重做）
- 自动保存，支持撤销／重做历史

### AI 周期报告（Integration）
- 支持 OpenAI Compatible Chat Completions API
- 周期报告自动生成：基于 LLM 分析周期内任务完成情况
- 周期报告邮件自动发送（SMTP）
- 支持日、周、月、季、年、五年各层级
- 发送失败自动重试，已成功发送不重复
- 报告 Markdown 本地保存

### API 与邮件配置
- “设置 → API 与邮件配置”入口
- 填写 API Key、模型、SMTP 服务器、邮箱授权码
- 支持 SSL / STARTTLS 切换
- 一键测试 API 连接和邮件发送
- **密钥通过 Windows DPAPI 加密保存**，绑定当前 Windows 用户，不进入 Git

### 系统托盘与自启动
- 最小化到系统托盘，托盘菜单快速操作
- 开机自启动（注册表方式）
- 支持开发环境（python.exe）与打包 exe 模式切换
- 需要管理员权限时通过启动辅助进程请求 UAC

### 全局热键
- Windows 原生全局热键注册
- 支持自定义快捷键（如 Win+Shift+F 唤出悬浮窗）

### 主题与界面
- 深色主题，统一的对话框样式
- 任务卡片根据截止状态自动着色
- 计划卡片根据关联图片自动提取配色
- 布局自适应窗口大小

### 数据存储
- SQLite 本地数据库，不依赖网络
- 打包为 exe 后数据库位于用户本地应用数据目录
- 覆盖安装或正常卸载**不会主动删除用户数据**

### 本地化
- 界面语言：简体中文
- 日期、时间格式符合中文习惯

---

## 技术栈

- Python 3.10+
- PySide6
- SQLite
- Windows DPAPI (CryptProtectData / CryptUnprotectData)
- Windows Registry
- PyInstaller
- Inno Setup 7
- Git

---

## 安装包

当前版本安装包位于仓库内以下相对位置：

```
installer/output/计划炼金台-Setup-2.0.1.exe
```

（开发电脑中的完整路径示例：`C:\Users\27726\PycharmProjects\ScheduleApp\installer\output\计划炼金台-Setup-2.0.1.exe`）

### 安装说明

- 默认安装目录：`%LOCALAPPDATA%\Programs\计划炼金台`
- 安装后的主程序：`%LOCALAPPDATA%\Programs\计划炼金台\计划炼金台.exe`
- 用户数据目录：`%LOCALAPPDATA%\计划炼金台`
  - 数据库文件：`schedule.db`
  - 配置文件：`config\report_delivery.json`
  - 图片速记资源：`notes\`
  - 日志文件：`logs\`
  - 报告文件：`reports\`
- **覆盖安装和正常卸载不会主动删除用户数据。** 如需清除用户数据，请手动删除 `%LOCALAPPDATA%\计划炼金台` 目录。
- 当前安装包**未进行 Authenticode 代码签名**，Windows 可能显示“未知发布者”，属正常现象，可继续安装。
- Git 仓库通常不提交 `installer/output` 中的 exe 文件（已在 `.gitignore` 中忽略）；正式安装包应作为 GitHub Release 附件发布。

### 首次使用配置

1. 启动程序后，在菜单中进入 **设置 → API 与邮件配置**。
2. 填写以下信息（全部为必填）：
   - **API Base URL**：OpenAI Compatible Chat Completions 地址（如 `https://api.openai.com/v1`）
   - **API Key**：你的 API 密钥
   - **模型**：模型名称（如 `gpt-4o`）
   - **SMTP 主机**：发件邮箱的 SMTP 服务器地址
   - **SMTP 端口**：SSL 通常 465，STARTTLS 通常 587
   - **加密方式**：SSL 或 STARTTLS
   - **发件邮箱**：完整邮箱地址
   - **邮箱授权码**：客户端专用授权码（非网页登录密码）
   - **收件邮箱**：接收报告的邮箱地址
3. 点击 **测试 API 连接** 和 **测试邮件发送** 验证配置正确。
4. 保存配置。
5. 在设置页面开启“启用自动报告”，程序即会在每个周期结束后自动生成并发送报告。

> **安全说明：** API Key 和邮箱授权码通过 Windows DPAPI 加密后保存在当前 Windows 用户专用的存储中，不会以明文形式出现在配置文件或 Git 提交中。

---

## 源码运行

### 前置要求
- Python 3.10 及以上版本
- Windows 系统（部分功能如全局热键、注册表自启动、DPAPI 依赖 Windows API）

### 步骤

```bash
# 1. 克隆项目
git clone https://github.com/你的用户名/ScheduleApp.git
cd ScheduleApp

# 2. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动程序
python main.py
```

程序启动后默认只显示桌面悬浮窗。可通过托盘图标或悬浮窗入口打开主窗口。

---

## 构建与本地发布

通过 `release-local.ps1` 脚本一键完成 **PyInstaller 构建 → 写入版本资源 → Inno Setup 编译安装包 → 静默覆盖安装 → 启动安装版本**。

### 前置条件

- Inno Setup 7 已安装（默认路径 `%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe`）
- 项目虚拟环境已创建并安装了 `PyInstaller` 和 `requirements.txt` 中的依赖

### 使用方式

```powershell
# 使用 VERSION 文件中的版本号
.\release-local.ps1

# 或手动指定版本号
.\release-local.ps1 -Version "2.0.1"
```

### 脚本执行流程

1. 清理旧的 `build/`、`dist/`、`installer/output/` 目录
2. 使用项目虚拟环境的 PyInstaller 构建 exe（依据 `计划炼金台.spec`）
3. 强制写入并验证 exe 的文件版本、产品版本、产品名称
4. 使用 Inno Setup 7 编译安装程序
5. 静默覆盖安装到 `%LOCALAPPDATA%\Programs\计划炼金台`
6. 启动已安装版本
7. 安装过程中自动检测并保护用户数据目录不被误删

### 构建产物

```
installer/output/计划炼金台-Setup-2.0.1.exe
```

---

## 项目结构

```text
ScheduleApp/
├── app/
│   ├── database/          # 数据库层
│   ├── models/            # 数据模型
│   ├── security/          # DPAPI 密钥存储
│   ├── services/          # 业务逻辑（任务、打卡、报告、自启动等）
│   ├── ui/                # 界面组件（主窗口、悬浮窗、速记、设置等）
│   ├── utils/             # 工具函数
│   ├── config.py          # 路径与基础配置
│   └── version.py         # 版本信息
├── assets/
│   ├── icons/             # 程序图标
│   └── pictures/          # 计划配图
├── config/
│   └── report_delivery.example.json   # 报告配置示例
├── data/                  # 开发环境数据目录（非打包模式）
├── installer/
│   ├── 计划炼金台.iss      # Inno Setup 安装脚本
│   └── output/            # 安装包输出目录
├── scripts/               # 辅助脚本
├── tests/                 # 测试用例
├── main.py                # 程序入口
├── 计划炼金台.spec         # PyInstaller spec 文件
├── startup_elevated_helper.py   # UAC 提权辅助进程
├── startup_launcher.pyw         # 自启动启动器
├── release-local.ps1      # 本地发布脚本
├── requirements.txt       # 项目依赖
├── VERSION                # 版本号文件
├── CHANGELOG.md           # 更新日志
└── README.md
```

---

## 许可证

本项目为个人学习与开发项目，暂未指定开源协议。