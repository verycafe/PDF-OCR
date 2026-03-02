"""
文档处理器 - PDF 解析、OCR 识别、内容清理的核心处理逻辑
处理流程：PDF → Markdown 解析 → 图片 OCR → 内容合并 → 文本清理
"""
import os
import time
import re
import hashlib
import threading
import logging
import pymupdf4llm
from PIL import Image
import numpy as np
from paddleocr import PaddleOCR
from app.models.document import Document
from app.services.task_queue import task_queue
from app.services.event_bus import event_bus
from config import Config
import json

logger = logging.getLogger(__name__)

# OCR 引擎全局单例（避免重复加载模型）
ocr_lock = threading.Lock()  # 线程锁，确保线程安全
_ocr_engine = None

def get_ocr_engine():
    """
    获取 OCR 引擎单例
    使用 PaddleOCR 进行中文文字识别
    """
    global _ocr_engine
    with ocr_lock:
        if _ocr_engine is None:
            _ocr_engine = PaddleOCR(
                use_angle_cls=False,       # 关闭角度分类（假设图片方向正确，提升速度）
                lang='ch',                 # 中文识别
                det_db_thresh=0.6,        # 文本检测阈值（提高以过滤噪点）
                det_db_box_thresh=0.7,    # 文本框阈值
                det_db_unclip_ratio=1.6,  # 文本框扩展比例
                det_limit_side_len=960,   # 图片最大边长限制
                det_limit_type='max'      # 限制类型
            )
    return _ocr_engine

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
        文档处理主流程
        1. PDF 解析为 Markdown（pymupdf4llm）
        2. 提取图片并进行 OCR 识别（PaddleOCR）
        3. 将 OCR 结果合并到 Markdown
        4. 清理文本内容

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

            # ========== 阶段 1: PDF 解析为 Markdown ==========
            doc.processing_stage = 'parsing'
            doc.progress = 0
            doc.save()
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'parsing', 'progress': 0}))

            # 创建图片输出目录
            image_dir = os.path.join(os.path.dirname(doc.file_path), f"images_{doc_id}")
            os.makedirs(image_dir, exist_ok=True)

            try:
                # 使用 pymupdf4llm 将 PDF 转换为 Markdown，同时提取图片
                md_text = pymupdf4llm.to_markdown(doc.file_path, write_images=True, image_path=image_dir)

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

            # ========== 阶段 2: 图片 OCR 识别 ==========
            doc.processing_stage = 'ocr'
            doc.progress = 0
            doc.save()
            event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'processing', 'stage': 'ocr', 'progress': 0}))

            logger.info(f"Markdown preview for doc {doc_id}: {md_text[:500]}")

            # 从 Markdown 中提取所有图片链接
            # 正则匹配：(xxx.png) 或 (xxx.jpg) 等
            potential_links = re.findall(r'\(([^)]+\.(?:png|jpg|jpeg|bmp|tiff))', md_text, re.IGNORECASE)

            # 去重
            image_links = list(set(potential_links))

            total_images = len(image_links)
            logger.info(f"Found {total_images} images in document {doc_id}")

            ocr = None
            if total_images == 0:
                 # 没有图片，保存空 OCR 数据
                 doc.ocr_data = "[]"
                 doc.save()

            if total_images > 0:
                # 初始化 OCR 引擎
                ocr = get_ocr_engine()

            processed_images = 0
            ocr_results = []

            # 加载已有的 OCR 数据（支持断点续传）
            if doc.ocr_data:
                try:
                    existing_data = json.loads(doc.ocr_data)
                    if isinstance(existing_data, list):
                        ocr_results = existing_data
                        logger.info(f"Loaded {len(ocr_results)} existing OCR results for resumption.")
                except Exception as e:
                    logger.warning(f"Failed to load existing OCR data: {e}")

            # 已处理图片的文件名集合（用于跳过）
            processed_img_ids = {item.get('image_name') for item in ocr_results if item.get('image_name')}

            # 遍历每张图片进行 OCR
            for img_rel_path in image_links:
                if cancel_event.is_set():
                    doc.status = 'cancelled'
                    doc.save()
                    event_bus.emit('status', json.dumps({'doc_id': doc_id, 'status': 'cancelled'}))
                    return

                # 检查是否已处理过
                img_filename_check = os.path.basename(img_rel_path)
                if img_filename_check in processed_img_ids:
                    logger.info(f"Skipping already processed image: {img_filename_check}")
                    processed_images += 1
                    continue

                # 解析图片的绝对路径
                img_full_path = img_rel_path
                if not os.path.isabs(img_full_path):
                     img_name = os.path.basename(img_rel_path)
                     img_full_path = os.path.join(image_dir, img_name)

                if not os.path.exists(img_full_path):
                    img_name = os.path.basename(img_rel_path)
                    img_full_path = os.path.join(image_dir, img_name)

                if os.path.exists(img_full_path):
                    try:
                        logger.info(f"Running OCR on image: {img_full_path}")
                        # 加载图片
                        image = Image.open(img_full_path).convert('RGB')
                        img_np = np.array(image)

                        if ocr is None:
                            logger.error("OCR engine is None, skipping")
                            continue

                        ocr_text = ""
                        try:
                            # 调用 PaddleOCR 进行识别
                            result = ocr.ocr(img_np, cls=False)
                            logger.info(f"OCR finished for {os.path.basename(img_full_path)}. Result type: {type(result)}")

                            if result is None:
                                logger.warning(f"OCR result is None for {img_full_path}")
                            else:
                                # 解析 OCR 结果（兼容不同版本的返回格式）
                                if isinstance(result, list) and len(result) > 0:
                                    if result[0] is None:
                                        logger.warning("OCR result[0] is None (no text found)")
                                    elif isinstance(result[0], list):
                                        # 标准格式：[[box, (text, score)], ...]
                                        logger.info("Detected standard list-of-lists OCR result format")
                                        lines = []
                                        for line in result[0]:
                                            if line and len(line) >= 2 and isinstance(line[1], (list, tuple)):
                                                lines.append(line[1][0])
                                        ocr_text = "\n".join(lines)
                                    elif hasattr(result[0], 'rec_texts'):
                                        # 新格式：对象包含 rec_texts 属性
                                        logger.info("Detected new OCR result format (object in list)")
                                        ocr_text = "\n".join(result[0].rec_texts)

                        except Exception as e:
                            logger.error(f"Standard ocr.ocr() parsing failed: {e}")

                        # 如果标准方法失败，尝试 predict() 方法（新版本 PaddleOCR）
                        if not ocr_text and hasattr(ocr, 'predict'):
                            try:
                                logger.info("Attempting ocr.predict() for new PaddleOCR version...")
                                pred_res = ocr.predict(img_np)
                                if isinstance(pred_res, list) and len(pred_res) > 0:
                                    res_obj = pred_res[0]
                                    if hasattr(res_obj, 'rec_texts'):
                                        ocr_text = "\n".join(res_obj.rec_texts)
                                    elif isinstance(res_obj, dict) and 'rec_texts' in res_obj:
                                         ocr_text = "\n".join(res_obj['rec_texts'])
                            except Exception as e:
                                logger.error(f"ocr.predict() failed: {e}")

                        if not ocr_text:
                            logger.warning(f"No text extracted for {img_full_path} (or empty result)")

                        # 将 OCR 结果插入到 Markdown 中
                        img_filename = os.path.basename(img_rel_path)
                        escaped_filename = re.escape(img_filename)

                        # 生成图片 ID（用于追踪）
                        img_id = f"IMG-{hashlib.md5(img_filename.encode()).hexdigest()[:6].upper()}"

                        # 构建正则匹配图片链接
                        pattern = r'(!?\[[^\]]*?\]\([^)]*?' + escaped_filename + r'[^)]*?\))'

                        # 格式化 OCR 内容（使用引用块格式）
                        if ocr_text:
                            ocr_content = f"\n> [OCR Content - {img_id}]:\n> {ocr_text.replace(chr(10), chr(10) + '> ')}\n"
                        else:
                            ocr_content = f"\n> [OCR Content - {img_id}]: (No text detected)\n"

                        # 在图片链接后追加 OCR 内容
                        match = re.search(pattern, md_text)
                        if match:
                            md_text = re.sub(pattern, lambda m: m.group(0) + ocr_content, md_text, count=1)
                        else:
                            # 备用方案：直接在文件名后插入
                            if img_filename in md_text:
                                idx = md_text.find(img_filename)
                                if idx != -1:
                                    closing_paren_idx = md_text.find(')', idx)
                                    if closing_paren_idx != -1:
                                        md_text = md_text[:closing_paren_idx+1] + ocr_content + md_text[closing_paren_idx+1:]
                                    else:
                                        md_text = md_text[:idx+len(img_filename)] + ocr_content + md_text[idx+len(img_filename):]

                        # 保存 OCR 结果
                        ocr_results.append({
                            'id': img_id,
                            'image_name': os.path.basename(img_full_path),
                            'text': ocr_text
                        })

                    except Exception as e:
                        logger.error(f"OCR failed for image {img_full_path}: {e}")

                processed_images += 1
                # 更新进度
                current_progress = int((processed_images / total_images) * 100)
                doc.progress = current_progress
                doc.status_message = f"Processing image {processed_images}/{total_images}"
                # 保存部分结果（支持断点续传）
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
