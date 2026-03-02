"""
项目 API - 处理项目的增删改查操作
"""
from flask import Blueprint, request, jsonify
from app.models.project import Project
from app.models.document import Document
from playhouse.shortcuts import model_to_dict

projects_bp = Blueprint('projects', __name__)

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
