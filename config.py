"""
配置文件 - 定义应用的全局配置
"""
import os

class Config:
    # 基础路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 项目根目录
    DATA_DIR = os.path.join(BASE_DIR, 'data')  # 数据存储目录
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')  # PDF 上传目录
    DATABASE_PATH = os.path.join(DATA_DIR, 'pdf_ocr.db')  # SQLite 数据库路径
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key')  # Flask 密钥

    # 任务队列配置
    OCR_MAX_WORKERS = 2  # OCR 处理的最大并发工作线程数

    @staticmethod
    def init_app(app):
        """初始化应用时创建必要的目录"""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
