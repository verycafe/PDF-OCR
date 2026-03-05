"""
文档处理器 - PDF 解析、OCR 识别、内容清理的核心处理逻辑
处理流程：
1. PDF 页面元素分析（文本/表格/图片）
2. 分类提取：文本直接提取、PDF表格转Markdown、图片导出
3. 图片识别：表格图片用表格识别、普通图片用OCR
4. 按页面顺序合并内容 → 文本清理
"""
import os
import time
import re
import hashlib
import threading
import logging
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from paddleocr import PaddleOCR, PPStructureV3
from app.models.document import Document
from app.services.task_queue import task_queue
from app.services.event_bus import event_bus
from config import Config
import json

logger = logging.getLogger(__name__)

# OCR 引擎全局单例（避免重复加载模型）
ocr_lock = threading.Lock()  # 线程锁，确保线程安全
_ocr_engine = None
_structure_engine = None  # 表格识别引擎

def get_ocr_engine():
    """
    获取 OCR 引擎单例
    使用 PaddleOCR 3.4.0+ 进行中文文字识别
    """
    global _ocr_engine
    with ocr_lock:
        if _ocr_engine is None:
            _ocr_engine = PaddleOCR(
                use_textline_orientation=False,  # 关闭文本行方向分类（新版参数名）
                lang='ch',                       # 中文识别
                text_det_thresh=0.6,            # 文本检测阈值（新版参数名）
                text_det_box_thresh=0.7,        # 文本框阈值（新版参数名）
                text_det_unclip_ratio=1.6,      # 文本框扩展比例（新版参数名）
                text_det_limit_side_len=960,    # 图片最大边长限制（新版参数名）
                text_det_limit_type='max'       # 限制类型（新版参数名）
            )
    return _ocr_engine

def get_structure_engine():
    """
    获取表格识别引擎单例
    使用 PPStructureV3 进行文档结构分析和表格识别
    """
    global _structure_engine
    with ocr_lock:
        if _structure_engine is None:
            _structure_engine = PPStructureV3(
                use_table_recognition=True,      # 启用表格识别
                use_formula_recognition=False,   # 禁用公式识别（节省资源）
                use_chart_recognition=False,     # 禁用图表识别
                lang='ch'                        # 中文
            )
    return _structure_engine

def convert_table_to_markdown(table_result):
    """
    将表格识别结果转换为 Markdown 表格格式

    Args:
        table_result: PPStructureV3 返回的表格结果

    Returns:
        str: Markdown 格式的表格
    """
    try:
        # 检查是否有表格数据
        if not table_result or 'html' not in table_result:
            return ""

        # PPStructureV3 返回 HTML 格式的表格，需要转换为 Markdown
        html_table = table_result['html']

        # 简单的 HTML 表格转 Markdown（可以后续优化）
        # 这里先返回 HTML，因为 Markdown 也支持内嵌 HTML
        return f"\n{html_table}\n"

    except Exception as e:
        logger.error(f"Table to Markdown conversion failed: {e}")
        return ""

def extract_pdf_table_to_markdown(page, table_obj):
    """
    从 PDF 页面提取原生表格并转换为 Markdown

    Args:
        page: PyMuPDF 页面对象
        table_obj: PyMuPDF 的 Table 对象

    Returns:
        str: Markdown 格式的表格
    """
    try:
        # 使用 PyMuPDF 的表格提取功能
        table_data = table_obj.extract()

        if not table_data:
            return ""

        md_lines = []

        for row_idx, row in enumerate(table_data):
            # 清理单元格内容（去除换行符和多余空格）
            cells = [str(cell).replace('\n', ' ').strip() if cell else '' for cell in row]

            # 构建表格行
            md_lines.append("| " + " | ".join(cells) + " |")

            # 第一行后添加分隔符
            if row_idx == 0:
                md_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")

        return "\n" + "\n".join(md_lines) + "\n"

    except Exception as e:
        logger.error(f"PDF table extraction failed: {e}")
        return ""

def analyze_page_layout(page):
    """
    分析 PDF 页面布局，识别文本、表格、图片区域

    Args:
        page: PyMuPDF 页面对象

    Returns:
        dict: {
            'text_blocks': [(bbox, text), ...],
            'tables': [bbox, ...],
            'images': [(bbox, image_data), ...]
        }
    """
    layout = {
        'text_blocks': [],
        'tables': [],
        'images': []
    }

    try:
        # 1. 提取图片
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            bbox = page.get_image_bbox(img)
            base_image = page.parent.extract_image(xref)
            layout['images'].append((bbox, base_image))

        # 2. 检测表格（使用 PyMuPDF 的表格检测）
        tables = page.find_tables()
        if tables:
            for table in tables:
                # 保存 table 对象和 bbox（用于排除文本）
                layout['tables'].append(table)

        # 3. 提取文本块（排除表格和图片区域）
        text_blocks = page.get_text("blocks")

        for block in text_blocks:
            if len(block) >= 5:
                bbox = fitz.Rect(block[:4])
                text = block[4].strip()

                if not text:
                    continue

                # 检查是否与表格或图片重叠
                is_overlap = False

                for table in layout['tables']:
                    if bbox.intersects(table.bbox):
                        is_overlap = True
                        break

                if not is_overlap:
                    for img_bbox, _ in layout['images']:
                        if bbox.intersects(img_bbox):
                            is_overlap = True
                            break

                if not is_overlap:
                    layout['text_blocks'].append((bbox, text))

        return layout

    except Exception as e:
        logger.error(f"Page layout analysis failed: {e}")
        return layout

class DocumentProcessor:
    """文档处理器 - 负责 PDF 的解析、OCR 和清理"""

    @staticmethod
    def calculate_file_hash(file_path):
        """计算文件的 SHA256 哈希值（用于缓存判断）"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def _clean_markdown(text):
        """
        清理 Markdown 文本
        - 去除页眉页脚
        - 去除水印
        - 去除图片链接和 OCR 标记
        - 去除多余空行
        - 去除目录页码
        - 合并重复表格标题
        - 展开 OCR 引用内容（去除 > 前缀）
        """
        if not text:
            return "", 0

        lines = text.splitlines()
        cleaned = []

        # 1. 统计短行频率（用于识别页眉页脚）
        line_freq = {}
        for line in lines:
            stripped = line.strip()
            if len(stripped) < 50:  # 短行才可能是页眉页脚
                line_freq[stripped] = line_freq.get(stripped, 0) + 1

        # 连续出现 3 次以上的短行视为页眉页脚
        repeated_headers = {k for k, v in line_freq.items() if v >= 3}
        # 水印关键词
        watermark_keywords = ['机密', '内部资料', '仅供参考', 'CONFIDENTIAL']

        empty_count = 0

        # 正则：匹配图片链接和 OCR 标记
        img_link_pattern = re.compile(r'^!?\[.*?\]\(.*?\)$')
        ocr_header_pattern = re.compile(r'^> \[OCR Content - IMG-[A-F0-9]+\]:.*$')

        # 第一轮清理：去除页眉页脚、水印、图片链接、OCR 标记
        for i, line in enumerate(lines):
            stripped = line.strip()

            # 跳过图片链接
            if img_link_pattern.match(stripped):
                continue

            # 跳过 OCR 标记行
            if ocr_header_pattern.match(stripped):
                continue

            # 跳过重复的页眉页脚
            if stripped in repeated_headers:
                continue

            # 跳过水印（出现 2 次以上）
            if any(kw in stripped for kw in watermark_keywords) and line_freq.get(stripped, 0) >= 2:
                continue

            # 处理空行（最多保留 1 个连续空行）
            if not stripped:
                empty_count += 1
                if empty_count <= 1:
                    cleaned.append(line)
                continue

            empty_count = 0
            cleaned.append(line)

        # 2. 去除目录页码（如 "第一章 ......... 1"）
        cleaned = [re.sub(r'\.{3,}\s*\d+$', '', line) for line in cleaned]

        # 3. 合并重复表格标题 + 展开 OCR 内容
        final = []
        prev_line = None
        repeat_count = 0

        for line in cleaned:
            # 展开 OCR 引用内容（去除 "> " 前缀，使其融入正文）
            if line.startswith('> '):
                line = line[2:]

            # 检测并去除重复的表格标题行
            if line == prev_line and '|' in line:
                repeat_count += 1
                if repeat_count < 2:  # 保留第一次出现
                    final.append(line)
            else:
                repeat_count = 0
                final.append(line)
                prev_line = line

        result = '\n'.join(final)
        saved_chars = 0
        if text:
            saved_chars = len(text) - len(result)

        return result, saved_chars

    @staticmethod
    def process_document(cancel_event, doc_id):
        """
        文档处理主流程（新版）
        1. 打开 PDF，逐页分析布局（文本/表格/图片）
        2. 分类提取：文本直接提取、PDF表格转Markdown、图片导出
        3. 图片识别：表格图片用表格识别、普通图片用OCR
        4. 按页面顺序合并内容 → 清理

        Args:
            cancel_event: 取消事件（用于中断处理）
            doc_id: 文档 ID
        """
        try:
            doc = Document.get_by_id(doc_id)
            doc.status = 'processing'
            doc.processing_stage = 'init'
            doc.progress = 0
            doc.save()

            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'init'}))

            logger.info(f"Starting processing for document {doc_id}: {doc.filename}")

            # 检查是否取消
            if cancel_event.is_set():
                doc.status = 'cancelled'
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'cancelled'}))
                return

            # ========== 阶段 1: PDF 页面分析 ==========
            doc.processing_stage = 'parsing'
            doc.progress = 0
            doc.save()
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'parsing', 'progress': 0}))

            # 创建图片输出目录
            image_dir = os.path.join(os.path.dirname(doc.file_path), f"images_{doc_id}")
            os.makedirs(image_dir, exist_ok=True)

            try:
                # 打开 PDF 文档
                pdf_doc = fitz.open(doc.file_path)
                total_pages = len(pdf_doc)
                logger.info(f"PDF has {total_pages} pages")

                # 存储每页的内容
                page_contents = []
                all_images = []  # 存储所有导出的图片信息

                # 逐页处理
                for page_num in range(total_pages):
                    if cancel_event.is_set():
                        pdf_doc.close()
                        doc.status = 'cancelled'
                        doc.save()
                        event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'cancelled'}))
                        return

                    page = pdf_doc[page_num]
                    logger.info(f"Processing page {page_num + 1}/{total_pages}")

                    # 分析页面布局
                    layout = analyze_page_layout(page)

                    page_content = []

                    # 1. 处理文本块
                    for bbox, text in layout['text_blocks']:
                        page_content.append(('text', text))

                    # 2. 处理 PDF 原生表格
                    for table in layout['tables']:
                        table_md = extract_pdf_table_to_markdown(page, table)
                        if table_md:
                            page_content.append(('table', table_md))

                    # 3. 导出图片
                    for img_index, (img_bbox, img_data) in enumerate(layout['images']):
                        img_filename = f"page{page_num + 1}_img{img_index + 1}.png"
                        img_path = os.path.join(image_dir, img_filename)

                        # 保存图片
                        with open(img_path, "wb") as img_file:
                            img_file.write(img_data["image"])

                        all_images.append({
                            'path': img_path,
                            'filename': img_filename,
                            'page': page_num + 1,
                            'bbox': img_bbox
                        })

                        # 在内容中标记图片位置
                        page_content.append(('image', img_filename))

                    page_contents.append(page_content)

                    # 更新进度
                    progress = int((page_num + 1) / total_pages * 100)
                    doc.progress = progress
                    doc.save()
                    event_bus.emit('status', json.dumps({
                        'doc_id': doc_id,
                        'status': 'processing',
                        'stage': 'parsing',
                        'progress': progress
                    }))

                pdf_doc.close()

                # 构建初始 Markdown（不含图片识别结果）
                md_lines = []
                for page_num, page_content in enumerate(page_contents):
                    md_lines.append(f"\n## Page {page_num + 1}\n")
                    for content_type, content in page_content:
                        if content_type == 'text':
                            md_lines.append(content)
                        elif content_type == 'table':
                            md_lines.append(content)
                        elif content_type == 'image':
                            md_lines.append(f"\n![{content}]({content})\n")

                md_text = "\n".join(md_lines)

                # 保存纯解析结果
                doc.parsing_content = md_text
                doc.raw_text_content = md_text
                doc.save()

            except Exception as e:
                logger.error(f"PDF parsing failed: {e}")
                doc.status = 'failed'
                doc.error_message = f"PDF Parsing Error: {str(e)}"
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'failed', 'error': str(e)}))
                return

                # 保存纯解析结果（未经 OCR 修改）
                doc.parsing_content = md_text
                # 初始化原始内容（后续会被 OCR 结果更新）
                doc.raw_text_content = md_text

                doc.progress = 100
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'parsing', 'progress': 100}))
            except Exception as e:
                logger.error(f"PDF parsing failed: {e}")
                doc.status = 'failed'
                doc.error_message = f"PDF Parsing Error: {str(e)}"
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'failed', 'error': str(e)}))
                return

            if cancel_event.is_set():
                doc.status = 'cancelled'
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'cancelled'}))
                return

            # ========== 阶段 2: 图片识别（表格/文字） ==========
            doc.processing_stage = 'ocr'
            doc.progress = 0
            doc.save()
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'ocr', 'progress': 0}))

            total_images = len(all_images)
            logger.info(f"Found {total_images} images in document {doc_id}")

            ocr = None
            structure = None
            ocr_results = []

            if total_images == 0:
                # 没有图片，保存空 OCR 数据
                doc.ocr_data = "[]"
                doc.save()
            else:
                # 初始化 OCR 引擎和表格识别引擎
                ocr = get_ocr_engine()
                structure = get_structure_engine()

            processed_images = 0

            # 遍历每张图片进行识别
            for img_info in all_images:
                if cancel_event.is_set():
                    doc.status = 'cancelled'
                    doc.save()
                    event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'cancelled'}))
                    return

                img_path = img_info['path']
                img_filename = img_info['filename']

                if not os.path.exists(img_path):
                    logger.warning(f"Image not found: {img_path}")
                    processed_images += 1
                    continue

                try:
                    logger.info(f"Processing image: {img_filename}")
                    # 加载图片
                    image = Image.open(img_path).convert('RGB')
                    img_np = np.array(image)

                    ocr_text = ""
                    is_table = False

                    # 第一步：使用 PPStructureV3 检测图片类型
                    try:
                        logger.info(f"Detecting layout for: {img_filename}")
                        structure_result = structure(img_np)

                        # 检查是否包含表格
                        if structure_result and len(structure_result) > 0:
                            for item in structure_result:
                                if item.get('type') == 'table':
                                    is_table = True
                                    logger.info(f"Table detected in {img_filename}")
                                    # 提取表格内容
                                    table_md = convert_table_to_markdown(item)
                                    if table_md:
                                        ocr_text = table_md
                                    break

                    except Exception as e:
                        logger.error(f"Layout detection failed for {img_filename}: {e}")

                    # 第二步：如果不是表格，使用普通 OCR
                    if not is_table:
                        try:
                            logger.info(f"Running OCR on {img_filename}")
                            result = ocr.ocr(img_np)

                            if result is None:
                                logger.warning(f"OCR result is None for {img_filename}")
                            elif isinstance(result, list) and len(result) > 0:
                                ocr_result = result[0]

                                if ocr_result is None:
                                    logger.warning("OCR result[0] is None (no text found)")
                                elif hasattr(ocr_result, '__getitem__') and 'rec_texts' in ocr_result:
                                    rec_texts = ocr_result['rec_texts']
                                    if rec_texts:
                                        ocr_text = "\n".join(rec_texts)
                                        logger.info(f"Extracted {len(rec_texts)} text lines from OCR")
                                    else:
                                        logger.warning("rec_texts is empty")
                                else:
                                    logger.warning(f"Unknown OCR result format: {type(ocr_result)}")
                            else:
                                logger.warning(f"Unexpected OCR result structure: {type(result)}")

                        except Exception as e:
                            logger.error(f"OCR failed for {img_filename}: {e}", exc_info=True)

                    if not ocr_text:
                        logger.warning(f"No text extracted for {img_filename}")

                    # 生成图片 ID
                    img_id = f"IMG-{hashlib.md5(img_filename.encode()).hexdigest()[:6].upper()}"

                    # 在 Markdown 中插入识别结果
                    escaped_filename = re.escape(img_filename)
                    pattern = r'(!?\[[^\]]*?\]\([^)]*?' + escaped_filename + r'[^)]*?\))'

                    # 格式化内容
                    if ocr_text:
                        if is_table:
                            ocr_content = f"\n> [Table Content - {img_id}]:\n{ocr_text}\n"
                        else:
                            ocr_content = f"\n> [OCR Content - {img_id}]:\n> {ocr_text.replace(chr(10), chr(10) + '> ')}\n"
                    else:
                        ocr_content = f"\n> [OCR Content - {img_id}]: (No text detected)\n"

                    # 在图片链接后追加识别内容
                    match = re.search(pattern, md_text)
                    if match:
                        md_text = re.sub(pattern, lambda m: m.group(0) + ocr_content, md_text, count=1)

                    # 保存识别结果
                    ocr_results.append({
                        'id': img_id,
                        'image_name': img_filename,
                        'text': ocr_text,
                        'is_table': is_table
                    })

                except Exception as e:
                    logger.error(f"Image processing failed for {img_filename}: {e}")

                processed_images += 1
                # 更新进度
                current_progress = int((processed_images / total_images) * 100)
                doc.progress = current_progress
                doc.status_message = f"Processing image {processed_images}/{total_images}"
                doc.ocr_data = json.dumps(ocr_results)
                doc.save()
                event_bus.emit('status', json.dumps({
                    'doc_id': doc_id,
                    'status': 'processing',
                    'stage': 'ocr',
                    'progress': doc.progress,
                    'message': doc.status_message
                }))

            # ========== 阶段 3: 保存合并后的原始内容 ==========
            doc.raw_text_content = md_text
            doc.save()

            # ========== 阶段 4: 清理文本 ==========
            doc.processing_stage = 'cleaning'
            doc.save()
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'cleaning', 'progress': 0}))

            cleaned_text, saved_chars = DocumentProcessor._clean_markdown(md_text)
            doc.text_content = cleaned_text

            # 记录清理统计
            doc.status_message = f"Cleaned {saved_chars} chars"

            doc.status = 'completed'
            doc.processing_stage = 'done'
            doc.progress = 100
            doc.save()

            logger.info(f"Document {doc_id} processing completed.")
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'completed'}))

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            try:
                doc = Document.get_by_id(doc_id)
                doc.status = 'failed'
                doc.error_message = str(e)
                doc.save()
                event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'failed', 'error': str(e)}))
            except:
                pass

def start_document_processing(doc_id):
    """
    启动文档处理任务
    将处理任务加入队列，由工作线程异步执行

    Args:
        doc_id: 文档 ID

    Returns:
        task_id: 任务 ID
    """
    try:
        doc = Document.get_by_id(doc_id)
        doc.status = 'queued'
        doc.save()

        task_id = task_queue.add_ocr_task(
            DocumentProcessor.process_document,
            args=(doc_id,)
        )
        return task_id
    except Exception as e:
        logger.error(f"Failed to start processing: {e}")
        return None
