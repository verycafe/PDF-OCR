"""
文档模型 - 定义 PDF 文档及其处理状态的数据结构
"""
from peewee import *
from app.models.base import BaseModel
from app.models.project import Project
import datetime

class Document(BaseModel):
    """文档表 - 存储 PDF 文档及其处理结果"""
    # 基础信息
    project = ForeignKeyField(Project, backref='documents', on_delete='CASCADE')  # 所属项目
    filename = CharField()  # 原始文件名
    file_path = CharField()  # 文件在服务器上的绝对路径

    # 处理状态
    status = CharField(default='pending')  # 处理状态: pending(待处理), queued(队列中), processing(处理中), completed(完成), failed(失败)
    processing_stage = CharField(null=True)  # 当前处理阶段: parsing(解析), ocr(OCR识别), cleaning(清理)
    status_message = CharField(null=True)  # 详细状态信息，如 "处理图片 3/10"
    progress = IntegerField(default=0)  # 处理进度 (0-100)
    error_message = TextField(null=True)  # 错误信息

    # 提取的内容
    text_content = TextField(null=True)  # 最终清理后的文本内容（用于展示和分析）
    raw_text_content = TextField(null=True)  # 原始合并内容（Markdown + OCR，未清理）
    parsing_content = TextField(null=True)  # 纯解析结果（仅 PyMuPDF4LLM 输出的 Markdown）
    ocr_data = TextField(null=True)  # OCR 识别结果的 JSON 数据: [{image_name, text, id}, ...]
    ocr_hash = CharField(null=True, index=True)  # 文件哈希值，用于缓存 OCR 结果

    # 时间戳
    created_at = DateTimeField(default=datetime.datetime.now)  # 创建时间
    updated_at = DateTimeField(default=datetime.datetime.now)  # 更新时间
