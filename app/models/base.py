"""
数据库基础模型 - 定义数据库连接和基础模型类
"""
from peewee import *
from config import Config
import os
import datetime

# 初始化 SQLite 数据库连接
db = SqliteDatabase(Config.DATABASE_PATH)

class BaseModel(Model):
    """所有模型的基类，提供通用功能"""
    class Meta:
        database = db

    def save(self, *args, **kwargs):
        """保存时自动更新 updated_at 字段"""
        if hasattr(self, 'updated_at'):
            self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)

def init_db():
    """初始化数据库，创建所有表"""
    from app.models.project import Project
    from app.models.document import Document

    # 确保数据目录存在
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)

    # 连接数据库并创建表
    db.connect()
    db.create_tables([Project, Document], safe=True)
    db.close()
