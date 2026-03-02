"""
应用启动入口 - 初始化数据库和任务队列，启动 Flask 服务器
"""
from app import create_app
from config import Config
from app.models.base import init_db
from app.services.task_queue import task_queue
import logging
import os

logger = logging.getLogger(__name__)

# 创建 Flask 应用实例
app = create_app()

if __name__ == '__main__':
    # 初始化数据库（创建表）
    init_db()

    # 启动任务队列（OCR 处理工作线程）
    task_queue.start()

    # 从环境变量读取端口，默认 5001
    port = int(os.environ.get('PORT', 5001))
    # 判断是否为生产环境
    debug = os.environ.get('FLASK_ENV') != 'production'
    # 启动 Flask 服务器
    app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)
