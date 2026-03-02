# 产品需求文档 (PRD)

## 1. 项目概述
构建一个基于大语言模型 (LLM) 的本地自动化评标 Web 工具。系统处理招标文件和投标文件（PDF格式），利用 OCR 和文本解析技术提取内容，并使用智谱 AI (GLM 模型) 提取评审标准并对投标文件进行评分。

## 2. 用户流程
1.  **配置**: 用户设置智谱 AI API Key 和模型偏好。
2.  **上传招标文件**: 用户上传招标文件 (PDF)。系统提取文本并识别评审标准。
3.  **上传投标文件**: 用户上传多份投标文件 (PDF)。系统并行处理（OCR + 文本提取）。
4.  **标准提取**: 系统使用 LLM 从招标文件中提取结构化的评审标准。
5.  **评分**: 系统根据提取的标准，使用 LLM 对每份投标文件进行评分。
6.  **结果**: 用户在 Web 界面查看详细的评分结果和理由。

## 3. 功能需求

### 3.1 文档处理
-   **输入**: PDF 文件（招标文件和投标文件）。
-   **处理流程**:
    -   使用 `pymupdf4llm` 将 PDF 转换为 Markdown。
    -   检测 PDF 中的图片。
    -   对图片应用 OCR (PaddleOCR) 以提取文本。
    -   将 OCR 文本合并回 Markdown 内容中。
-   **并发**: 限制高负载处理（OCR）的并发数，防止系统过载（例如，最大 2 个并行任务）。

### 3.2 AI 集成
-   **提供商**: 智谱 AI (GLM-4 或兼容模型)。
-   **用户配置**: 允许用户输入自己的 API Key。
-   **提示词来源**: 初始提示词将从 `/Users/tvwoo/Projects/PDF-OCR/AI评标提示词v0.7.pdf` 中提取。
-   **任务**:
    -   **提取**: 从招标文件中提取评审标准（资质、技术要求、报价）。
    -   **评分**: 根据提取的标准评估投标文件。

### 3.3 Web 界面
-   **仪表盘**: 项目管理的主视图。
-   **上传区域**: 招标文件和投标文件的拖拽上传区。
-   **进度跟踪**: 文件处理和 AI 任务的实时进度条 (通过 SSE)。
-   **结果视图**: 表格化显示分数，支持向下钻取查看详细理由。

### 3.4 并发与性能
-   **任务队列**: 实现健壮的任务队列（使用 `queue.Queue` 或 `celery`，本地单用户场景下 `queue` 已足够）来管理文档处理作业。
-   **并发控制**:
    -   **OCR/重型任务**: 限制为 `max_workers=2`（可配置），防止 CPU/内存耗尽。
    -   **LLM API 调用**: 可以处理更高的并发（例如 `max_workers=5`），因为它们是 I/O 密集型的，但需遵守 API 速率限制。
-   **性能优化**:
    -   **分块**: 分块处理大型 PDF 以避免 OOM（内存溢出）。
    -   **缓存**: 缓存中间 OCR 结果，避免重复处理相同文件（基于哈希）。

### 3.5 实时反馈与交互
-   **细粒度状态更新**: 后端必须通过 SSE (Server-Sent Events) 发送详细的进度事件。
    -   事件: `QUEUED`, `PROCESSING_OCR` (带页码), `PROCESSING_LLM` (带步骤名), `COMPLETED`, `FAILED`。
    -   示例载荷: `{"doc_id": 123, "status": "processing", "stage": "ocr", "progress": 45, "message": "OCR Processing page 5/12..."}`
-   **UI 响应性**:
    -   **进度条**: 整体任务和单个文件进度的可视化条。
    -   **日志/控制台**: UI 中的可折叠“活动日志”，显示详细的系统步骤以提高透明度。
    -   **取消**: 允许用户取消挂起或运行中的任务。

## 4. 技术架构

### 4.1 后端
-   **语言**: Python 3.10+
-   **框架**: Flask (轻量级 Web 服务器)
-   **数据库**: SQLite (存储项目元数据、文档状态和结果)
-   **关键库**:
    -   `flask`, `flask-cors`: Web 服务器与跨域支持。
    -   `pymupdf4llm`: PDF 转 Markdown 转换。
    -   `paddleocr`, `paddlepaddle`: OCR 引擎。
    -   `zhipuai`: AI SDK。
    -   `numpy`, `Pillow`: 图像处理。

### 4.2 前端
-   **框架**: React (Vite)
-   **样式**: Tailwind CSS
-   **状态管理**: React Context 或 Zustand
-   **通信**: Axios (HTTP) + EventSource (SSE)

### 4.3 数据模型 (SQLite)
-   `projects`: id, name, created_at, status
-   `documents`: id, project_id, type (tender/bid), filename, status, text_content, file_path
-   `evaluation_criteria`: id, project_id, criteria_json
-   `scores`: id, project_id, bid_doc_id, criteria_id, score, reasoning

## 5. 非功能性需求
-   **本地执行**: 所有文件处理都在本地进行；仅文本发送到 LLM API。
-   **性能**: OCR 可能较慢；UI 必须提供反馈。
-   **错误处理**: 优雅处理 API 失败或格式错误的 PDF。

---

## 6. 文档处理流程与工具 (Technical Specification)

本节详细记录了当前的文档处理逻辑和使用的工具链，**严禁随意更改核心工具选型**，除非经过充分验证。

### 6.1 核心工具链

| 工具名称 | 用途 | 版本/链接 | 备注 |
| :--- | :--- | :--- | :--- |
| **PyMuPDF4LLM** | PDF 转 Markdown | `pymupdf4llm` ([PyPI](https://pypi.org/project/pymupdf4llm/)) | 核心预处理工具，支持提取图片和表格布局还原 |
| **PaddleOCR** | 图片文字识别 | `paddleocr>=2.7` ([GitHub](https://github.com/PaddlePaddle/PaddleOCR)) | 必须支持中文 (`lang='ch'`)，用于识别 PDF 中的扫描件/图片内容 |
| **ZhipuAI SDK** | 大模型调用 | `zhipuai` ([Docs](https://open.bigmodel.cn/dev/api#sdk)) | 模型：GLM-4，用于语义理解、标准提取和评分 |
| **Flask** | 后端服务 | `flask==3.0.0` | 提供 API 和 SSE 事件流 |
| **SQLite** | 数据存储 | 内置 | 轻量级本地数据库，存储解析后的文本和评分结果 |

### 6.2 详细处理逻辑 (Pipeline)

文档处理（`DocumentProcessor`）遵循严格的线性流程，任何环节失败都应标记为 `failed` 并保留错误日志。

1.  **初始化与哈希校验**
    *   计算文件 SHA256 哈希值。
    *   （可选）检查数据库中是否已存在相同哈希的文件，若存在则复用结果（当前暂未完全实现，预留接口）。

2.  **PDF 解析 (Parsing)**
    *   **工具**: `pymupdf4llm.to_markdown(file_path, write_images=True, image_path=output_dir)`
    *   **输出**:
        *   Markdown 文本（保留了标题、表格结构）。
        *   图片文件（提取并保存到本地 `images_{doc_id}` 目录）。
    *   **关键点**: 此步骤会将 PDF 中的所有图片提取出来，并在 Markdown 中生成类似 `![](images/img1.png)` 的链接。
    *   **存储**: 将生成的原始 Markdown 存入 `documents.parsing_content` 字段。此字段仅存储 PDF 转换结果，不包含任何 OCR 注入内容，用于 "Parsing Result" 预览。
    *   **初始赋值**: 同时将此内容赋值给 `documents.raw_text_content`，作为后续 OCR 处理的起点。

3.  **OCR 处理 (Text Extraction)**
    *   **输入**: 数据库中的 `raw_text_content` (初始为 Markdown)。
    *   **逻辑**:
        1.  解析 Markdown，使用正则 `!\[.*?\]\((.*?)\)` 提取所有图片链接。
        2.  遍历每张图片，使用 **PaddleOCR** 进行识别。
            *   **OCR 配置**: 
                *   `use_angle_cls=False` (关闭方向分类以提速)
                *   `lang='ch'` (中文支持)
                *   `det_db_thresh=0.5` (提高检测阈值，过滤噪点)
                *   `det_db_box_thresh=0.5` (调整框阈值)
                *   `det_limit_side_len=960` + `det_limit_type='max'` (限制图片尺寸防止OOM)
        3.  **并发控制**: 使用全局锁 `ocr_lock` 或单例模式初始化 OCR 引擎。
        4.  **结果合并**: 将 OCR 识别出的文本追加到 `raw_text_content` 中对应图片链接的**下方**，格式为：
            ```markdown
            > [OCR Content - IMG-ID]:
            > 识别出的文字内容...
            ```
    *   **存储**: 更新 `documents.raw_text_content` 字段。
    *   **目的**: 确保 LLM 既能看到图片占位符（了解布局），又能读取到图片中的文字信息。

4.  **内容清洗与压缩 (Cleaning)**
    *   **输入**: 合并 OCR 后的 Markdown 文本。
    *   **逻辑**: 执行 `_clean_markdown` 清洗策略：
        1.  去除重复的页眉页脚（检测连续出现 3 次以上的短文本）。
        2.  去除敏感水印（"机密", "内部资料" 等）。
        3.  压缩连续空行。
        4.  去除目录页码（`... 1`）。
        5.  合并重复的表格标题行。
    *   **目的**: 减少 LLM Token 消耗，提高分析准确度。

5.  **数据存储**
    *   将清洗后的 Markdown 文本存入 `documents` 表的 `text_content` 字段。
    *   状态更新为 `completed`。

6.  **AI 分析 (LLM Analysis)**
    *   **触发**: 用户手动点击“提取标准”或“开始评分”。
    *   **输入**: 数据库中的 `text_content`。
    *   **处理**: 调用 ZhipuAI 接口，传入特定的 Prompt（提示词）。
    *   **输出**: 结构化的 JSON 数据（评审标准或评分结果）。

### 6.3 前端交互反馈规范 (Frontend Interaction)

本节规定了用户在文件上传和处理过程中应看到的视觉反馈。

#### 6.3.1 状态流转可视化
前端通过 `ProcessingSteps` 组件展示三个核心阶段，对应后端 `Document.processing_stage` 字段：

1.  **PDF Parsing (PDF 解析)**
    *   **后端状态**: `processing_stage='parsing'` 或 `init`
    *   **UI 表现**: 第一阶段图标旋转 (Loader)，进度条根据文件读取进度变化。
    *   **描述**: 将 PDF 转换为 Markdown 并提取图片。

2.  **OCR Processing (OCR 处理)**
    *   **后端状态**: `processing_stage='ocr'`
    *   **UI 表现**:
        *   第一阶段显示为完成 (Green Check)。
        *   第二阶段图标旋转 (Loader)。
        *   进度条显示 OCR 进度 (已处理图片数 / 总图片数)。
        *   下方显示详细文本: "Processing image X/Y"。
    *   **描述**: 对提取的图片逐一进行 OCR 识别。

3.  **Content Merging (内容合并)**
    *   **后端状态**: `processing_stage='done'` 或 `status='completed'`
    *   **UI 表现**: 所有阶段显示为完成 (Green Check)，进度条满 (100%)。
    *   **描述**: 文本与 OCR 结果合并完成，准备好进行 AI 分析。

4.  **Cleaning (清洗与优化)**
    *   **后端状态**: `processing_stage='cleaning'` -> `done`
    *   **UI 表现**: 
        *   第四阶段显示为完成 (Green Check)。
        *   文件列表显示最终状态 "Completed"。
    *   **描述**: 移除图片链接和元数据，优化文本格式。

#### 6.3.2 实时预览与调试
为了让用户（及开发者）信任处理结果，必须提供以下预览功能（通过点击对应阶段的“眼睛”图标）：

*   **Original PDF**: 查看原始上传的 PDF 文件（支持浏览器内嵌预览）。
*   **Parsing Result**: 查看仅包含 PDF 文本层和图片占位符的初步 Markdown（对应 `raw_text_content` 的初始状态）。
*   **OCR Details**: 这是一个关键的调试视图。
    *   左侧: 显示从 PDF 提取的原始图片切片。
    *   右侧: 显示该图片的 OCR 识别结果文本。
    *   **目的**: 验证 OCR 质量，确认是否识别到了关键信息（如公章、手写签名等）。
*   **Raw Merged**: 查看合并了 OCR 内容的原始 Markdown。
    *   包含图片链接 `![](...png)`。
    *   包含 OCR 标记 `> [OCR Content - ID]: ...`。
    *   用于调试 OCR 内容是否正确插入到了对应位置。
*   **Cleaned Result**: 查看最终发送给 LLM 的清洗后文本。
    *   **不包含**图片链接和 OCR 标记。
    *   OCR 文本已作为普通文本融入。
    *   上方显示绿色徽章统计信息：`Cleaned X chars`。
