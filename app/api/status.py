"""
文档状态 API - 查询文档处理状态
"""
from flask import Blueprint, jsonify
from app.models.document import Document
from app.models.project import Project
from playhouse.shortcuts import model_to_dict

status_bp = Blueprint('status', __name__)

@status_bp.route('/project/<int:project_id>/doc_status', methods=['GET'])
def get_project_status(project_id):
    """获取项目下所有文档的处理状态"""
    try:
        project = Project.get_by_id(project_id)
        docs = Document.select().where(Document.project == project)

        # 构建状态列表
        status_list = []
        for doc in docs:
            status_list.append({
                'doc_id': doc.id,
                'filename': doc.filename,
                'status': doc.status,  # 处理状态
                'phase': doc.processing_stage,  # 当前阶段
                'progress': doc.progress,  # 进度百分比
                'error': doc.error_message  # 错误信息（如有）
            })

        return jsonify({'documents': status_list})
    except Project.DoesNotExist:
        return jsonify({'error': 'Project not found'}), 404
