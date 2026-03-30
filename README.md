# TransTool

<a id="top"></a>

[![Homepage](https://img.shields.io/badge/Homepage-Citation--Generator-181717?logo=github)](https://github.com/f-u-t-u-r-e/Citation-Generator)
[![Release](https://img.shields.io/github/v/release/f-u-t-u-r-e/Citation-Generator?display_name=tag)](https://github.com/f-u-t-u-r-e/Citation-Generator/releases)
[![License](https://img.shields.io/badge/License-Not%20Specified-lightgrey)](https://github.com/f-u-t-u-r-e/Citation-Generator)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![GUI](https://img.shields.io/badge/GUI-CustomTkinter-2E7B5A)](https://github.com/TomSchimansky/CustomTkinter)
[![Build](https://img.shields.io/badge/Build-PyInstaller-6E4C13)](https://pyinstaller.org/)

[![Stars](https://img.shields.io/github/stars/f-u-t-u-r-e/Citation-Generator?style=social)](https://github.com/f-u-t-u-r-e/Citation-Generator/stargazers)
[![Issues](https://img.shields.io/github/issues/f-u-t-u-r-e/Citation-Generator)](https://github.com/f-u-t-u-r-e/Citation-Generator/issues)
[![Last Commit](https://img.shields.io/github/last-commit/f-u-t-u-r-e/Citation-Generator)](https://github.com/f-u-t-u-r-e/Citation-Generator/commits/main)

[中文说明](#中文说明) | [English](#english)

---

## 中文说明

[Jump to English](#english) | [回到顶部](#top)

### 项目简介
TransTool 是一个桌面 GUI 工具，用于把 DOI、论文链接、BibTeX、RIS 或纯文本参考文献转换为目标引用格式。

### 主要功能
- 输入来源自动识别：DOI / URL / BibTeX / RIS / 纯文本
- 支持从网页链接中提取 DOI（含 IEEE Xplore 场景兜底）
- 支持通过 Crossref 对纯文本文献进行 DOI 匹配
- 支持 RIS 文本直接转 BibTeX（本地转换）
- 一键输出并自动复制结果到剪贴板
- 支持 Light / Dark / System 风格切换

### 支持的输出格式
- BibTeX
- IEEE
- APA
- MLA
- Chicago
- Harvard
- Vancouver
- RIS

### 运行环境
- Python 3.10+
- Windows（已在当前项目环境下验证）

### 安装与运行
1. 创建并激活虚拟环境（可选）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖

```powershell
python -m pip install -U pip
python -m pip install customtkinter requests pyperclip beautifulsoup4
```

3. 启动程序

```powershell
python Trans_Tool.py
```

### 打包为 EXE（PyInstaller）
1. 安装 PyInstaller

```powershell
python -m pip install -U pyinstaller
```

2. 按 spec 打包

```powershell
python -m PyInstaller Trans_Tool.spec
```

### 项目结构
- `Trans_Tool.py`：主程序
- `Trans_Tool.spec`：PyInstaller 打包配置
- `.gitignore`：Git 忽略规则

### 注意事项
- 本工具依赖外部服务（doi.org、Crossref、目标网站页面），网络异常时可能导致转换失败。
- 某些站点存在反爬策略，可能影响 DOI 提取成功率。

---

## English

[跳转中文](#中文说明) | [Back to Top](#top)

### Overview
TransTool is a desktop GUI application that converts DOI, paper URLs, BibTeX, RIS, or plain-text citations into target reference formats.

### Key Features
- Auto-detect input type: DOI / URL / BibTeX / RIS / plain text
- DOI extraction from web pages (including IEEE Xplore fallback)
- Plain-text citation DOI lookup via Crossref
- Direct RIS-to-BibTeX local conversion
- One-click output with automatic clipboard copy
- Light / Dark / System theme switching

### Supported Output Formats
- BibTeX
- IEEE
- APA
- MLA
- Chicago
- Harvard
- Vancouver
- RIS

### Requirements
- Python 3.10+
- Windows (validated in the current project environment)

### Install and Run
1. Create and activate virtual environment (optional)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
python -m pip install -U pip
python -m pip install customtkinter requests pyperclip beautifulsoup4
```

3. Run the app

```powershell
python Trans_Tool.py
```

### Build EXE with PyInstaller
1. Install PyInstaller

```powershell
python -m pip install -U pyinstaller
```

2. Build from spec

```powershell
python -m PyInstaller Trans_Tool.spec
```

### Project Files
- `Trans_Tool.py`: main application
- `Trans_Tool.spec`: PyInstaller configuration
- `.gitignore`: git ignore rules

### Notes
- The app depends on external services (doi.org, Crossref, publisher websites). Network issues may cause conversion failures.
- Some websites may block automated requests, which can affect DOI extraction.
