# PDF-OCR 全面问题排查报告

> 生成日期：2026-02-25

用户反馈"从第一步就走不通"。经过对后端、前端、Spec 文档的全面交叉审查，共发现以下问题。

---

## 一、致命问题（会直接导致功能不可用）

### 1. PaddleOCR API 不兼容（OCR 完全不工作）
- **文件**：`app/services/document_processor.py:183`
- 代码用的是旧版 API `ocr.ocr(img_np, cls=False)`，但安装的是 PaddleOCR 3.4.0
- 3.4.0 的 `ocr()` 方法已重定向到 `predict()`，不接受 `cls` 参数，直接报 `TypeError`
- 新版 API 是 `ocr.predict(img)`，返回 `OCRResult` 对象（`rec_texts`/`rec_scores`），不是旧版的 `[[polygon, (text, conf)]]`
- 初始化参数 `use_angle_cls` 也已废弃，新版是 `use_textline_orientation`
- **影响**：所有 PDF 中的图片 OCR 全部失败

### 2. TaskQueue 被绕过（OCR 任务不走队列）
- **文件**：`app/services/document_processor.py:269-280`
- `task_queue.add_ocr_task()` 被注释掉了，替换为裸 `threading.Thread` 直接执行
- 注释写着 "DEBUG: Direct thread execution to bypass TaskQueue issues"
- **影响**：OCR 并发不受控，TaskQueue 的优先级、取消、worker 限制全部失效；`run.py` 启动的 2 个 OCR worker 线程空转

### 3. 评标结果 API 返回原始 JSON 字符串
- **文件**：`app/api/evaluation.py:28`
- `r.result_json` 是 TextField 存的 JSON 字符串，直接放进 `jsonify([...])` 会双重编码
- 前端收到的是 `["{\\"total_score\\": ...}"]`（字符串数组），不是对象数组
- **影响**：前端 `EvaluationResults.jsx` 访问 `result.total_score` 全部是 `undefined`，评分结果页面完全空白

### 4. 图片路径解析是空操作
- **文件**：`app/services/document_processor.py:162-165`
- 相对路径解析逻辑只有一个 `pass`，什么都没做
- 从数据库看，`pymupdf4llm` 输出的是绝对路径，所以这个 bug 碰巧没触发
- 后续 fallback（line 169-170）用 `os.path.basename` + `image_dir` 拼接，只在绝对路径不存在时才走

### 5. 数据库连接管理缺失
- **文件**：`app/models/base.py:19-21`
- `init_db()` 调用 `db.connect()` → `create_tables()` → `db.close()`
- 关闭后没有配置自动重连，后续请求可能报 `OperationalError: database is closed`
- SQLite 没设置 `pragmas={'journal_mode': 'wal'}`，多线程写入会 `database is locked`

---

## 二、严重问题（功能异常或数据错误）

### 6. 前端结果组件数据结构不匹配
- **文件**：`frontend/src/components/EvaluationResults.jsx:39,43,56`
- 期望每个 result 有 `{ total_score, summary, scores: [{ item, score, reasoning }] }`
- 后端 `EvaluationResult` 模型只有 `stage`, `result_json`, `score`, `reasoning`
- 即使修复了 #3 的双重编码，`result_json` 的内容结构取决于 LLM 输出，不保证有这些字段

### 7. datetime 序列化问题
- **文件**：`app/api/projects.py:36` 等所有用 `model_to_dict()` 的地方
- Peewee 的 `model_to_dict()` 返回 `datetime.datetime` 对象，Flask 的 `jsonify` 不能直接序列化
- 会导致 `TypeError: Object of type datetime is not JSON serializable`
- **影响**：项目列表、项目详情、文档列表等 GET 接口可能全部 500

### 8. model_to_dict 泄露敏感数据和大字段
- **文件**：`app/api/documents.py:59,84`、`app/api/projects.py:36`
- 文档列表返回完整的 `text_content`（可达 83KB）和 `ocr_data`
- 项目列表/详情返回 `api_key` 明文
- **影响**：前端轮询每 2 秒拉一次文档列表，每次传输大量无用数据；API Key 暴露在浏览器 DevTools

### 9. 评标流水线缺少 Stage 3（合规审查）
- **文件**：`app/services/evaluation_service.py:50-113`
- bid_eval_flow.md 定义 4 阶段：提取标准 → 提取投标信息 → 合规审查 → 评分
- 代码只实现了 3 阶段，跳过了合规审查，直接从投标信息提取跳到评分
- 所有结果都存为 `stage=4`

### 10. SSE 事件流前端未使用
- 后端 `app/api/stream.py` 实现了完整的 SSE
- 前端完全没用 `EventSource`，用的是 `setInterval` 每 2 秒轮询 `documentsApi.list()`
- 轮询的还不是状态接口（`/api/project/{id}/status`），而是完整文档列表接口

### 11. request.json 无空值检查
- **文件**：`app/api/projects.py:46`
- 如果请求没有 `Content-Type: application/json`，`request.json` 返回 `None`
- `'name' in data` 会抛 `TypeError: argument of type 'NoneType' is not iterable`

### 12. PriorityQueue 元素比较会崩溃
- **文件**：`app/services/task_queue.py:52`
- `PriorityQueue.put((priority, task_id, func, args))` — 当 priority 相同时，Python 会比较 task_id（字符串），再比较 func（函数对象）
- 函数对象不支持 `<` 比较，会抛 `TypeError`

---

## 三、中等问题（功能缺失或体验差）

### 13. 前端 shadcn/ui CSS 变量未定义
- **文件**：`frontend/src/components/ui/button.jsx`
- 用了 `ring-offset-background`, `border-input`, `bg-background`, `bg-accent`, `bg-secondary`, `text-primary` 等 CSS 变量类
- `index.css` 和 `tailwind.config.js` 都没定义这些变量
- **影响**：outline/ghost/secondary/link 按钮样式全部失效（无边框、无背景、无 hover 效果）

### 14. 无 API Key 验证接口
- bid_eval_flow.md 要求 `POST /api/project/{id}/test_api`
- 代码中不存在此接口，用户无法在运行流水线前验证 Key 是否有效

### 15. 无拖拽上传
- spec.md 要求 "Drag-and-drop zones for Tender and Bid files"
- 前端用的是隐藏 `<input type="file">` + 按钮触发，无拖拽功能

### 16. 无进度条组件
- spec.md 要求 "Visual bars for overall task and individual file progress"
- 前端只有文字状态（"Processing image 3/10"），没有 `<progress>` 或可视化进度条

### 17. 无活动日志面板
- spec.md 要求 "A collapsible Activity Log in the UI"
- 前端没有任何活动日志组件

### 18. 评标按钮无禁用逻辑
- **文件**：`frontend/src/components/EvaluationConfig.jsx`
- "Start Evaluation" 按钮始终可点击，不检查文档是否已处理完成
- checklist.md 要求 "Start Evaluation button is disabled until documents are ready"

### 19. model_name 前端不可配置
- Project 模型有 `model_name` 字段（默认 `glm-4`）
- 创建项目表单只有 name/description/api_key，无法选择模型

### 20. 评标流水线串行执行，未利用 LLM worker 池
- **文件**：`app/services/evaluation_service.py:55`
- 整个流水线作为一个 LLM task 提交，内部 `for bid_doc in bid_docs` 串行处理
- 5 个 LLM worker 只用了 1 个，其余空转

### 21. SSE 无心跳/超时机制
- **文件**：`app/api/stream.py:12`
- `q.get()` 无超时，客户端断开后线程永久阻塞
- 无 keepalive 心跳，代理可能静默关闭连接

### 22. 事件总线队列无上限
- **文件**：`app/services/event_bus.py`
- listener 队列无 maxsize，慢消费者会导致内存泄漏

### 23. OCR 文本未合并回 Markdown
- **文件**：`app/services/document_processor.py:238`
- OCR 结果存在 `doc.ocr_data`，但 `doc.text_content` 保存的是原始 `md_text`
- Markdown 中仍然是 `![](path)` 占位符，OCR 文本没有替换进去
- （注：代码 line 205 有替换逻辑，但由于 OCR 调用在 line 183 就崩溃了，替换永远不会执行）

### 24. updated_at 字段不自动更新
- **文件**：所有 model（project.py, document.py, evaluation.py）
- `updated_at = DateTimeField(default=datetime.datetime.now)` 只在创建时设置
- `.save()` 不会刷新 `updated_at`

---

## 四、低优先级问题

### 25. 无 404 路由
- `frontend/src/App.jsx` 没有 catch-all 路由，访问不存在的 URL 显示空白页

### 26. 前端错误提示不友好
- `ProjectDetail.jsx:76` 用 `error.message` 而非 `error.response?.data?.error`，只显示 "Request failed with status code 500"

### 27. 无 .env 加载
- `requirements.txt` 有 `python-dotenv`，但代码中没有 `load_dotenv()` 调用

### 28. 死代码
- `frontend/src/App.css` — Vite 模板残留，未被任何组件导入
- `frontend/src/assets/react.svg` — 未使用
- `app/services/task_queue.py` 的 OCR worker — 启动了但永远收不到任务

---

## 五、Spec 合规差距（文档要求 vs 实际实现）

| 要求 | 来源 | 状态 |
|------|------|------|
| 4 阶段评标流水线 | bid_eval_flow.md | ❌ 只有 3 阶段，缺合规审查 |
| 结果页 4 个 Tab | bid_eval_flow.md | ❌ 只有平铺列表 |
| API Key 验证接口 | bid_eval_flow.md | ❌ 不存在 |
| api_base 配置 | bid_eval_flow.md | ❌ 不存在 |
| SSE 实时更新 | spec.md | ❌ 后端有，前端未接入 |
| 拖拽上传 | spec.md | ❌ 未实现 |
| 进度条 | spec.md | ❌ 未实现 |
| 活动日志面板 | spec.md | ❌ 未实现 |
| 任务取消 UI | spec.md | ❌ 后端有方法，无 API 和 UI |
| OCR 缓存（hash） | spec.md | ❌ 有字段和方法，未调用 |
| 大 PDF 分块处理 | spec.md | ❌ 未实现 |
| Prompt 来源于 PDF | spec.md | ❌ 硬编码通用 prompt |
| React Context/Zustand | spec.md | ❌ 用的 useState |
| scores 表按 criteria_id | spec.md | ❌ 用 result_json blob |

### 建议修复优先级

1. **先修致命问题 #1-#5** — 让基本流程跑通（OCR → 文档处理 → 评标 → 结果展示）
2. **再修严重问题 #6-#12** — 让数据正确、接口稳定
3. **最后补中等/低优先级** — 完善体验和 Spec 合规

---

## 总结

| 级别 | 数量 |
|------|------|
| 致命问题 | 5 |
| 严重问题 | 7 |
| 中等问题 | 12 |
| 低优先级 | 4 |
| Spec 差距 | 14 项 |

**最核心的阻塞链**：PaddleOCR 3.4.0 API 不兼容 → OCR 崩溃 → 图片文字无法提取 → 评标数据不完整。即使 OCR 修好，评标结果 API 返回双重编码 JSON + 前端数据结构不匹配，结果页面也无法正常显示。
