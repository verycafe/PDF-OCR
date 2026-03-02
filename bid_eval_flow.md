# PDF-OCR 系统流程文档

## 步骤1: 上传招标文件

**用户操作:** 点击上传区域，选择招标PDF文件

**前端处理:**
- 调用 `uploadFile(input, 'tender')`
- `FormData` 添加文件
- 发送请求: `POST /api/project/{id}/upload`

**后端处理:**
1. 保存文件到 `data/uploads/{project_id}/{filename}`
2. 插入数据库: `INSERT INTO documents (project_id, filename, doc_type, file_path)`
3. 初始化状态: `_extract_status[doc_id] = {status: 'idle'}`
4. 返回: `{uploaded: [{doc_id, filename}]}`

**工具:** Flask文件上传、SQLite

---

## 步骤2: 提取招标文件内容

**前端触发:**
收到 `doc_id` → `POST /api/document/{doc_id}/extract`

**后端处理:**
1. 加入队列（信号量控制并发=2）
2. 启动后台线程执行提取

**提取工具链:**

### 2.1 文本提取 (pymupdf4llm)
```python
md = pymupdf4llm.to_markdown(pdf_path, write_images=True)
# 输出: markdown文本 + 图片占位符 ![](path)
```

### 2.2 图片OCR (PaddleOCR)
```python
for 每张图片:
    1. Image.open(图片路径) → PIL Image
    2. np.array(img) → numpy数组
    3. ocr.ocr(img_np) → OCR结果
    4. 提取文字 → 替换markdown中的占位符
```

### 2.3 保存结果
执行 SQL: `UPDATE documents SET text_content = 合并后的文本 WHERE id = doc_id`

**工具:** pymupdf4llm、PaddleOCR、PIL、numpy

---

## 步骤3: 前端显示进度

**轮询机制:**
每1.5秒: `GET /api/project/{id}/extract_status`

**后端返回:**
```json
{
  "documents": [
    {
      "doc_id": 1,
      "status": "running",
      "phase": "ocr",
      "current": 15,
      "total": 29,
      "text_length": 68535
    }
  ]
}
```

**前端渲染:**
```javascript
if (status === 'running' && phase === 'ocr') {
    // 显示进度条: current/total
    // 显示文字: "图片OCR 15/29"
}
if (status === 'done') {
    // 显示: "已完成 68.5k字"
    // 启用: "下一步"按钮
}
```

**工具:** JavaScript fetch、定时器

---

## 步骤4: 上传投标文件

**用户操作:** 点击"下一步" → 上传多个投标PDF

**处理流程:** 与步骤1-3相同，但 `doc_type='bid'`

**并发控制:** 最多2个文件同时提取，其余排队

**工具:** 同步骤1-3

---

## 步骤5: 配置评标API

**用户操作:** 输入API配置

**前端收集:**
```json
{
  "api_base": "https://api.example.com/v1",
  "api_key": "sk-xxx",
  "model_name": "gpt-4"
}
```

**后端验证:**
`POST /api/project/{id}/test_api`
  → 发送测试请求到LLM
  → 返回: `{ok: true/false, error: "..."}`

**工具:** requests库

---

## 步骤6: 运行评标流程

**前端触发:**
`POST /api/project/{id}/run_pipeline`
  → 建立SSE连接

**后端执行:**

### Stage 1: 初审提取（招标文件）
- **工具:** LLM API
- **输入:** 招标文件全文
- **Prompt:** "提取资质要求、评分标准、技术要求"
- **输出:** JSON结构化数据
- **保存:** `stage_results`表 (`stage=1`)

### Stage 2: 详审提取（每个投标文件）
- **工具:** LLM API
- **输入:** 投标文件全文
- **Prompt:** "提取公司资质、技术方案、报价"
- **输出:** JSON结构化数据
- **保存:** `stage_results`表 (`stage=2`, `doc_id`=投标文件ID)

### Stage 3: 初审评审（每个投标文件）
- **工具:** LLM API
- **输入:** Stage1结果 + Stage2结果
- **Prompt:** "对比投标内容与招标要求，判断符合性"
- **输出:** 符合/不符合 + 理由
- **保存:** `stage_results`表 (`stage=3`)

### Stage 4: 详审评分（每个投标文件）
- **工具:** LLM API
- **输入:** Stage1评分标准 + Stage2投标内容
- **Prompt:** "按评分标准打分"
- **输出:** 各项得分 + 总分
- **保存:** `stage_results`表 (`stage=4`)

**实时推送:**
每完成一个任务:
  `yield` SSE事件 → 前端更新进度

**工具:** requests、SSE、LLM API

---

## 步骤7: 查看结果

**前端展示:**
4个标签页:
  - **初审提取:** 显示Stage1 JSON
  - **详审提取:** 显示Stage2 JSON（每个投标文件）
  - **初审评审:** 显示Stage3结果
  - **详审评分:** 显示Stage4评分表

**数据来源:**
`GET /api/project/{id}/results`
  → 查询: `SELECT * FROM stage_results WHERE run_id = 最新run_id`
  → 返回: 按stage分组的结果

**工具:** SQLite查询、JSON解析

---

## 关键工具总结

| 步骤 | 工具 | 用途 |
| :--- | :--- | :--- |
| 文件上传 | Flask | HTTP接收文件 |
| 文本提取 | pymupdf4llm | PDF转markdown |
| 图片OCR | PaddleOCR | 识别图片文字 |
| 图片处理 | PIL + numpy | 格式转换 |
| 并发控制 | threading.Semaphore | 限制同时提取数 |
| 数据存储 | SQLite | 保存文档/结果 |
| 状态同步 | JavaScript轮询 | 实时更新UI |
| LLM调用 | requests | 发送API请求 |
| 实时推送 | SSE | 流式返回进度 |
| 结果展示 | JSON解析 | 格式化显示 |

---

## 工具参考

### pymupdf4llm
- **用途:** 将PDF转换为markdown格式，专为RAG（检索增强生成）优化，保留文档结构、表格、图片位置
- **GitHub:** [https://github.com/pymupdf/RAG](https://github.com/pymupdf/RAG)
- **PyPI:** [https://pypi.org/project/pymupdf4llm/](https://pypi.org/project/pymupdf4llm/)
- **文档:** [https://pymupdf.readthedocs.io/en/latest/rag.html](https://pymupdf.readthedocs.io/en/latest/rag.html)
- **安装:** `pip install pymupdf4llm`

### PaddleOCR
- **用途:** 百度开源的OCR工具，支持80+语言，可识别图片中的文字、表格、版面
- **GitHub:** [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- **文档:** [https://paddlepaddle.github.io/PaddleOCR/](https://paddlepaddle.github.io/PaddleOCR/)
- **PyPI:** [https://pypi.org/project/paddleocr/](https://pypi.org/project/paddleocr/)
- **安装:** `pip install paddleocr`

### 当前项目版本检查
```bash
pip list | grep -E "pymupdf4llm|paddleocr"
```
