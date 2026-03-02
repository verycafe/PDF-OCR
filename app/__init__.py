"""
Flask 应用工厂 - 创建和配置 Flask 应用
"""
from flask import Flask, request
from flask_cors import CORS
from config import Config
import datetime
from flask.json.provider import DefaultJSONProvider

class CustomJSONProvider(DefaultJSONProvider):
    """自定义 JSON 序列化器，支持 datetime 对象"""
    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return super().default(o)

def create_app(config_class=Config):
    """创建并配置 Flask 应用实例"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 使用自定义 JSON 序列化器处理 datetime
    app.json = CustomJSONProvider(app)

    # 启用 CORS，允许前端跨域访问
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 抑制 werkzeug 日志输出，保持终端清爽
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # 数据库连接管理
    from app.models.base import db

    @app.before_request
    def before_request():
        """每个请求前确保数据库连接打开"""
        if db.is_closed():
            db.connect()

    @app.teardown_request
    def teardown_request(exc):
        """每个请求后关闭数据库连接"""
        if not db.is_closed():
            db.close()

    @app.before_request
    def log_request_info():
        """记录请求信息（用于调试）"""
        print(f"Request: {request.method} {request.url}")
        if request.is_json:
            print(f"Body: {request.json}")

    # 确保上传目录存在
    config_class.init_app(app)

    # 注册 API 蓝图
    from app.api.projects import projects_bp
    from app.api.documents import documents_bp
    from app.api.status import status_bp
    from app.api.stream import stream_bp

    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(status_bp, url_prefix='/api')
    app.register_blueprint(stream_bp, url_prefix='/api')

    return app
