"""
文档 API - 处理文档上传、删除、查询和内容获取
"""
import os
import shutil
import uuid
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from app.models.document import Document
from app.models.project import Project
from playhouse.shortcuts import model_to_dict
from config import Config
from app.services.document_conversion import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    OFFICE_DOCUMENT_EXTENSIONS,
    DocumentConversionError,
    convert_office_document_to_pdf,
    get_file_extension,
)
from app.services.document_processor import build_document_task_id, start_document_processing
from app.services.task_queue import task_queue

documents_bp = Blueprint('documents', __name__)

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = SUPPORTED_DOCUMENT_EXTENSIONS

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def build_storage_filename(filename, fallback='document'):
    """生成安全的磁盘文件名，保留原始扩展名"""
    base_name, ext = os.path.splitext(filename or '')
    safe_base_name = secure_filename(base_name)
    if not safe_base_name:
        safe_base_name = fallback
    return f"{safe_base_name}{ext.lower()}"

def build_markdown_filename(filename, fallback='document'):
    """根据原始文件名生成 Markdown 下载文件名"""
    base_name, _ = os.path.splitext(filename or '')
    safe_name = base_name.strip() or fallback
    return f"{safe_name}.md"


def _resolve_data_path(file_path):
    """Best-effort path resolution for host/container absolute paths inside ./data."""
    candidates = []
    raw_path = (file_path or '').strip()
    if not raw_path:
        return None

    candidates.append(raw_path)

    for marker in (f'{os.sep}data{os.sep}', f'{os.sep}app{os.sep}data{os.sep}'):
        marker_index = raw_path.rfind(marker)
        if marker_index != -1:
            relative_path = raw_path[marker_index + len(marker):]
            candidates.append(os.path.join(Config.DATA_DIR, relative_path))

    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.exists(normalized):
            return normalized

    return os.path.abspath(candidates[-1])


def _cleanup_document_artifacts(doc):
    """Remove file-system artifacts tied to a document."""
    resolved_file_path = _resolve_data_path(doc.file_path)
    project_upload_dir = os.path.join(Config.UPLOAD_FOLDER, str(doc.project_id))

    paths_to_remove = [
        resolved_file_path,
        os.path.join(project_upload_dir, f'images_{doc.id}'),
    ]

    for target_path in paths_to_remove:
        if not target_path or not os.path.exists(target_path):
            continue
        if os.path.isdir(target_path):
            shutil.rmtree(target_path, ignore_errors=True)
        else:
            os.remove(target_path)

@documents_bp.route('/upload/<int:project_id>', methods=['POST'])
def upload_file(project_id):
    """
    上传文档到指定项目
    支持单个或多个文件同时上传
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # 验证项目是否存在
    try:
        project = Project.get_by_id(project_id)
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404

    project_upload_dir = os.path.join(Config.UPLOAD_FOLDER, str(project_id))
    os.makedirs(project_upload_dir, exist_ok=True)

    def cleanup_paths(paths):
        for path in paths:
            if path and os.path.exists(path):
                os.remove(path)

    prepared_files = []
    uploaded_docs = []

    # 处理每个上传的文件
    for file in files:
        if file and allowed_file(file.filename):
            original_filename = file.filename
            extension = get_file_extension(original_filename)
            storage_name = build_storage_filename(original_filename)
            unique_source_name = f"{uuid.uuid4().hex}_{storage_name}"
            source_path = os.path.join(project_upload_dir, unique_source_name)
            processing_path = source_path

            try:
                file.save(source_path)

                if extension in OFFICE_DOCUMENT_EXTENSIONS:
                    processing_path = os.path.join(
                        project_upload_dir,
                        f"{os.path.splitext(unique_source_name)[0]}.pdf"
                    )
                    convert_office_document_to_pdf(source_path, processing_path)
                    os.remove(source_path)

                prepared_files.append({
                    'filename': original_filename,
                    'file_path': processing_path,
                })
            except DocumentConversionError as exc:
                cleanup_paths([source_path, processing_path, *[item['file_path'] for item in prepared_files]])
                return jsonify({'error': f'Failed to convert {original_filename}: {exc}'}), 400
            except Exception as exc:
                cleanup_paths([source_path, processing_path, *[item['file_path'] for item in prepared_files]])
                return jsonify({'error': f'Failed to prepare {original_filename}: {exc}'}), 400

    for prepared_file in prepared_files:
        doc = Document.create(
            project=project,
            filename=prepared_file['filename'],
            file_path=prepared_file['file_path'],
            status='queued'
        )

        # 启动文档处理任务
        task_id = start_document_processing(doc.id)

        doc_dict = model_to_dict(doc)
        doc_dict['task_id'] = task_id
        uploaded_docs.append(doc_dict)

    if not uploaded_docs:
        return jsonify({'error': 'No valid files uploaded'}), 400

    return jsonify(uploaded_docs), 201

@documents_bp.route('/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档（同时删除数据库记录和磁盘文件）"""
    try:
        doc = Document.get_by_id(doc_id)

        task_queue.cancel_task(build_document_task_id(doc.id))
        _cleanup_document_artifacts(doc)

        # 从数据库删除记录
        doc.delete_instance()
        return jsonify({'message': 'Document deleted'})
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404

@documents_bp.route('/project/<int:project_id>', methods=['GET'])
def list_documents(project_id):
    """获取项目下的所有文档列表（不包含大文本内容以提升性能）"""
    try:
        project = Project.get_by_id(project_id)
        docs = Document.select().where(Document.project == project).order_by(Document.created_at.desc())
        # 排除大字段以提升列表查询性能
        return jsonify([model_to_dict(d, exclude=[Document.text_content, Document.ocr_data]) for d in docs])
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404

@documents_bp.route('/<int:doc_id>/file', methods=['GET'])
def get_document_file(doc_id):
    """获取用于预览的 PDF 文件"""
    try:
        doc = Document.get_by_id(doc_id)
        resolved_file_path = _resolve_data_path(doc.file_path)
        if not resolved_file_path or not os.path.exists(resolved_file_path):
            return jsonify({'error': 'File not found on disk'}), 404
        return send_file(resolved_file_path, mimetype='application/pdf')
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404

@documents_bp.route('/<int:doc_id>/content', methods=['GET'])
def get_document_content(doc_id):
    """
    获取文档的所有处理内容
    包括：最终清理内容、原始合并内容、纯解析内容、OCR 数据
    """
    try:
        doc = Document.get_by_id(doc_id)
        return jsonify({
            'id': doc.id,
            'text_content': doc.text_content,  # 最终清理后的内容
            'raw_text_content': doc.raw_text_content,  # 原始合并内容（Markdown + OCR）
            'parsing_content': doc.parsing_content,  # 纯解析结果（仅 Markdown）
            'status': doc.status,
            'status_message': doc.status_message,
            'processing_stage': doc.processing_stage,
            'ocr_data': doc.ocr_data  # OCR 识别详情（JSON）
        })
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404

@documents_bp.route('/<int:doc_id>/markdown', methods=['GET'])
def download_document_markdown(doc_id):
    """下载文档最终清理后的 Markdown 文件"""
    try:
        doc = Document.get_by_id(doc_id)

        if doc.status != 'completed' or not doc.text_content:
            return jsonify({'error': 'Markdown not ready'}), 409

        markdown_buffer = BytesIO(doc.text_content.encode('utf-8'))
        markdown_buffer.seek(0)

        return send_file(
            markdown_buffer,
            mimetype='text/markdown; charset=utf-8',
            as_attachment=True,
            download_name=build_markdown_filename(doc.filename, f'document_{doc.id}')
        )
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404

@documents_bp.route('/<int:doc_id>/images/<path:image_name>', methods=['GET'])
def get_document_image(doc_id, image_name):
    """获取文档中提取的图片文件"""
    try:
        doc = Document.get_by_id(doc_id)
        # 图片存储在 images_<doc_id> 目录下
        resolved_file_path = _resolve_data_path(doc.file_path)
        if not resolved_file_path:
            return jsonify({'error': 'Image not found'}), 404

        doc_dir = os.path.dirname(resolved_file_path)
        image_dir = os.path.join(doc_dir, f"images_{doc_id}")
        image_path = os.path.join(image_dir, image_name)

        if not os.path.exists(image_path):
             return jsonify({'error': 'Image not found'}), 404

        return send_file(image_path)
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404
