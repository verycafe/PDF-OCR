"""
SSE 流式 API - 提供实时事件推送接口
前端通过 EventSource 连接此接口接收文档处理状态更新
"""
from flask import Blueprint, Response, stream_with_context
from app.services.event_bus import event_bus

stream_bp = Blueprint('stream', __name__)

@stream_bp.route('/events')
def stream_events():
    """
    SSE (Server-Sent Events) 事件流接口
    前端通过 EventSource 连接此接口，持续接收服务器推送的事件

    Returns:
        Response: SSE 格式的流式响应
    """
    def generate():
        """
        生成器函数 - 持续从事件总线读取消息并推送给客户端
        """
        # 订阅事件总线，获取专属消息队列
        q = event_bus.subscribe()
        try:
            while True:
                # 阻塞等待消息（直到有新消息或连接断开）
                msg = q.get()
                yield msg  # 推送消息到客户端
        except GeneratorExit:
            # 客户端断开连接时触发
            event_bus.unsubscribe(q)
        except Exception:
            # 发生异常时清理订阅
            event_bus.unsubscribe(q)

    # 返回 SSE 格式的流式响应
    return Response(stream_with_context(generate()), mimetype='text/event-stream')
