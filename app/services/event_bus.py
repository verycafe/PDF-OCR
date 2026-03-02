"""
事件总线 - 基于 SSE (Server-Sent Events) 的实时状态推送
用于向前端推送文档处理进度、状态变化等实时消息
"""
import queue
import threading
import time

class EventBus:
    """
    事件总线类 - 管理多个客户端的消息订阅和广播
    使用线程安全的队列实现发布-订阅模式
    """
    def __init__(self):
        self.listeners = []  # 订阅者队列列表
        self.lock = threading.Lock()  # 线程锁，保护 listeners 列表的并发访问

    def subscribe(self):
        """
        订阅事件流
        为新客户端创建一个消息队列

        Returns:
            queue.Queue: 客户端专属的消息队列
        """
        q = queue.Queue(maxsize=100)  # 限制队列大小防止内存泄漏
        with self.lock:
            self.listeners.append(q)
        return q

    def unsubscribe(self, q):
        """
        取消订阅
        移除客户端的消息队列

        Args:
            q: 要移除的队列对象
        """
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def emit(self, event_type, data):
        """
        广播事件到所有订阅者
        将消息推送到所有客户端的队列中

        Args:
            event_type: 事件类型（如 'status', 'progress'）
            data: 事件数据（通常是 JSON 字符串）
        """
        # 构造 SSE 格式的消息
        message = f"event: {event_type}\ndata: {data}\n\n"
        with self.lock:
            # 遍历副本以避免迭代时列表被修改
            for q in list(self.listeners):
                try:
                    q.put_nowait(message)  # 非阻塞放入队列
                except queue.Full:
                    # 队列满时丢弃消息，保护服务器内存
                    # 可选：移除慢速消费者
                    pass

# 全局事件总线实例
event_bus = EventBus()
