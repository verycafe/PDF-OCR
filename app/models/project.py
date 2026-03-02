"""
项目模型 - 定义项目的数据结构
"""
from peewee import *
from app.models.base import BaseModel
import datetime

class Project(BaseModel):
    """项目表 - 用于组织和管理多个文档"""
    name = CharField()  # 项目名称
    description = TextField(null=True)  # 项目描述
    created_at = DateTimeField(default=datetime.datetime.now)  # 创建时间
    updated_at = DateTimeField(default=datetime.datetime.now)  # 更新时间
    status = CharField(default='active')  # 项目状态: active(活跃), archived(归档)
