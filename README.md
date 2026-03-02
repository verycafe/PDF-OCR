# PDF-OCR

一个基于 Flask 和 React 的智能 PDF OCR 识别工具。集成 PaddleOCR 和 LLM 辅助处理，支持多文件上传、实时进度显示、OCR 结果预览与导出。

![Project Preview](frontend/public/vite.svg)
*(注：此处可替换为实际项目截图)*

## ✨ 功能特性

- **PDF 解析与 OCR**：利用 PaddleOCR 强大的识别能力，将 PDF 文档转换为可编辑文本。
- **多任务处理**：后端支持多线程任务队列，可同时处理多个文档。
- **实时进度反馈**：前端实时展示文档解析、OCR 处理、内容合并等阶段的进度。
- **结果预览与清洗**：提供直观的界面查看 OCR 结果，并支持后续的数据清洗操作。
- **现代化 UI**：基于 React + Tailwind CSS 构建的响应式界面，操作便捷。

## 🛠️ 技术栈

### 后端 (Backend)
- **框架**：Flask 3.0
- **OCR 引擎**：PaddleOCR (基于 PaddlePaddle)
- **数据库**：SQLite (Peewee ORM)
- **PDF 处理**：PyMuPDF4LLM
- **其他依赖**：Torch, Transformers (用于辅助模型), ZhipuAI (智谱 AI 集成)

### 前端 (Frontend)
- **框架**：React 19
- **构建工具**：Vite
- **样式**：Tailwind CSS
- **组件库**：Radix UI, Lucide React
- **路由**：React Router v7

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+

### 1. 克隆项目

```bash
git clone https://github.com/verycafe/PDF-OCR.git
cd PDF-OCR
```

### 2. 后端设置

建议使用虚拟环境运行后端服务。

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**注意**：PaddlePaddle 的安装可能因操作系统和硬件（CPU/GPU）而异。如果默认安装失败，请参考 [PaddlePaddle 官网](https://www.paddlepaddle.org.cn/install/quick) 进行安装。

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install
# 或者使用 yarn
# yarn install
```

## 🏃‍♂️ 运行项目

### 启动后端服务

在项目根目录下（确保虚拟环境已激活）：

```bash
python run.py
```
后端服务默认运行在 `http://localhost:5001`。

### 启动前端服务

在 `frontend` 目录下：

```bash
npm run dev
```
前端服务默认运行在 `http://localhost:5173`。

打开浏览器访问 `http://localhost:5173` 即可使用。

## 📂 项目结构

```
PDF-OCR/
├── app/                 # 后端应用代码
│   ├── api/             # API 路由
│   ├── models/          # 数据库模型
│   ├── services/        # 业务逻辑 (OCR, 任务队列等)
│   └── __init__.py      # Flask 应用工厂
├── data/                # 数据存储 (SQLite, 上传文件)
├── frontend/            # 前端应用代码
│   ├── src/             # React 源码
│   └── ...
├── config.py            # 后端配置
├── run.py               # 后端启动脚本
└── requirements.txt     # Python 依赖
```

## 📝 配置说明

后端配置位于 `config.py`，主要包括：
- `UPLOAD_FOLDER`: 文件上传目录
- `DATABASE_PATH`: 数据库文件路径
- `OCR_MAX_WORKERS`: OCR 并发线程数

如有需要，可以通过设置环境变量 `PORT` 来修改后端监听端口。

## 📄 License

MIT
