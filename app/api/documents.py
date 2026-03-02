"""
文档 API - 处理 PDF 文档的上传、删除、查询和内容获取
"""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from app.models.document import Document
from app.models.project import Project
from playhouse.shortcuts import model_to_dict
from config import Config

documents_bp = Blueprint('documents', __name__)

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from app.services.document_processor import start_document_processing

@documents_bp.route('/upload/<int:project_id>', methods=['POST'])
def upload_file(project_id):
    """
    上传 PDF 文件到指定项目
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

    uploaded_docs = []

    # 处理每个上传的文件
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # 生成唯一文件名防止覆盖
            unique_filename = f"{uuid.uuid4().hex}_{filename}"

            # 创建项目专属上传目录
            project_upload_dir = os.path.join(Config.UPLOAD_FOLDER, str(project_id))
            os.makedirs(project_upload_dir, exist_ok=True)

            # 保存文件到磁盘
            file_path = os.path.join(project_upload_dir, unique_filename)
            file.save(file_path)

            # 保存到数据库
            doc = Document.create(
                project=project,
                filename=filename,
                file_path=file_path,
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
        # 从磁盘删除文件
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

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
    """获取原始 PDF 文件（用于预览）"""
    try:
        doc = Document.get_by_id(doc_id)
        if not os.path.exists(doc.file_path):
            return jsonify({'error': 'File not found on disk'}), 404
        response = send_file(doc.file_path, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename="{doc.filename}"'
        return response
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

@documents_bp.route('/<int:doc_id>/images/<path:image_name>', methods=['GET'])
def get_document_image(doc_id, image_name):
    """获取文档中提取的图片文件"""
    try:
        doc = Document.get_by_id(doc_id)
        # 图片存储在 images_<doc_id> 目录下
        doc_dir = os.path.dirname(doc.file_path)
        image_dir = os.path.join(doc_dir, f"images_{doc_id}")
        image_path = os.path.join(image_dir, image_name)

        if not os.path.exists(image_path):
             return jsonify({'error': 'Image not found'}), 404

        return send_file(image_path)
    except Document.DoesNotExist:
        return jsonify({'error': 'Document not found'}), 404
