"""
项目 API - 处理项目的增删改查操作
"""
import os
import shutil
import zipfile
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file
from app.models.project import Project
from app.models.document import Document
from playhouse.shortcuts import model_to_dict
from config import Config
from app.services.document_processor import build_document_task_id
from app.services.task_queue import task_queue

projects_bp = Blueprint('projects', __name__)

def build_markdown_filename(filename, fallback='document'):
    """根据原始文件名生成 Markdown 文件名"""
    base_name, _ = os.path.splitext(filename or '')
    safe_name = base_name.strip() or fallback
    return f"{safe_name}.md"

def build_unique_archive_name(filename, used_names, fallback):
    """避免 ZIP 包中的重名文件互相覆盖"""
    candidate = build_markdown_filename(filename, fallback)
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    base_name, ext = os.path.splitext(candidate)
    suffix = 2
    while True:
        deduped_name = f"{base_name}_{suffix}{ext}"
        if deduped_name not in used_names:
            used_names.add(deduped_name)
            return deduped_name
        suffix += 1

@projects_bp.route('/', methods=['GET'])
def list_projects():
    """获取所有项目列表（按创建时间倒序）"""
    projects = Project.select().order_by(Project.created_at.desc())
    return jsonify([model_to_dict(p) for p in projects])

@projects_bp.route('/', methods=['POST'])
def create_project():
    """创建新项目"""
    # 处理空请求体或非 JSON 格式
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON or empty body'}), 400

    # 验证必填字段
    if 'name' not in data:
        return jsonify({'error': 'Project name is required'}), 400

    # 创建项目
    project = Project.create(
        name=data['name'],
        description=data.get('description', '')
    )

    return jsonify(model_to_dict(project)), 201

@projects_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """获取单个项目详情（包含文档数量统计）"""
    try:
        project = Project.get_by_id(project_id)
        project_dict = model_to_dict(project)

        # 添加文档数量统计
        docs = Document.select().where(Document.project == project)
        project_dict['documents_count'] = len(docs)

        return jsonify(project_dict)
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404

@projects_bp.route('/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """更新项目信息"""
    try:
        project = Project.get_by_id(project_id)
        data = request.json

        # 更新允许修改的字段
        if 'name' in data:
            project.name = data['name']
        if 'description' in data:
            project.description = data['description']

        project.save()
        return jsonify(model_to_dict(project))
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404

@projects_bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目及其磁盘文件，必要时可强制取消处理中任务"""
    try:
        project = Project.get_by_id(project_id)
    except Project.DoesNotExist:
        return jsonify({'error': '项目不存在'}), 404

    force_delete = request.args.get('force', '').lower() in ('1', 'true', 'yes')

    active_docs = list(
        Document.select()
        .where(
            (Document.project == project) &
            (Document.status.in_(['queued', 'processing']))
        )
    )

    if active_docs and not force_delete:
        return jsonify({
            'error': '项目中仍有文档正在处理中',
            'code': 'project_has_active_documents',
            'active_documents': len(active_docs),
        }), 409

    if active_docs:
        for doc in active_docs:
            task_queue.cancel_task(build_document_task_id(doc.id))

    project_upload_dir = os.path.join(Config.UPLOAD_FOLDER, str(project.id))
    if os.path.isdir(project_upload_dir):
        shutil.rmtree(project_upload_dir, ignore_errors=True)

    project.delete_instance(recursive=True)
    return jsonify({'message': '项目已删除'})

@projects_bp.route('/<int:project_id>/markdown-archive', methods=['GET'])
def download_project_markdown_archive(project_id):
    """下载项目下所有已完成文档的 Markdown ZIP 包"""
    try:
        project = Project.get_by_id(project_id)

        ready_docs = list(
            Document.select()
            .where(
                (Document.project == project) &
                (Document.status == 'completed') &
                Document.text_content.is_null(False) &
                (Document.text_content != '')
            )
            .order_by(Document.created_at.asc())
        )

        if not ready_docs:
            return jsonify({'error': 'No completed markdown files found'}), 404

        zip_buffer = BytesIO()
        used_names = set()

        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            for doc in ready_docs:
                archive_name = build_unique_archive_name(doc.filename, used_names, f'document_{doc.id}')
                zip_file.writestr(archive_name, doc.text_content)

        zip_buffer.seek(0)

        project_name = project.name.strip() or f'project_{project.id}'
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{project_name}_markdown.zip'
        )
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404
