"""
任务队列 - 管理 OCR 处理任务的并发执行
"""
import queue
import threading
import time
import logging
import itertools
from config import Config

logger = logging.getLogger(__name__)

class TaskQueue:
    """任务队列类 - 使用优先级队列和工作线程池处理 OCR 任务"""

    def __init__(self):
        self.ocr_queue = queue.PriorityQueue()  # 优先级队列（数字越小优先级越高）
        self.counter = itertools.count()  # 唯一序列计数器，用于打破优先级相同时的排序

        self.running_tasks = {}  # 运行中的任务: task_id -> {status, thread, cancel_event}
        self.task_results = {}  # 任务结果: task_id -> result/error

        self.ocr_workers = []  # OCR 工作线程列表

        self.is_running = False  # 队列运行状态

    def start(self):
        """启动任务队列，创建工作线程池"""
        self.is_running = True

        # 启动 OCR 工作线程
        for i in range(Config.OCR_MAX_WORKERS):
            t = threading.Thread(target=self._ocr_worker_loop, name=f"OCR-Worker-{i}", daemon=True)
            t.start()
            self.ocr_workers.append(t)

        logger.info(f"TaskQueue started with {Config.OCR_MAX_WORKERS} OCR workers.")

    def add_ocr_task(self, task_func, args=(), priority=1, task_id=None):
        """
        添加 OCR 任务到队列

        Args:
            task_func: 任务函数
            args: 任务参数
            priority: 优先级（数字越小优先级越高）
            task_id: 任务 ID（可选，不提供则自动生成）

        Returns:
            task_id: 任务 ID
        """
        if not task_id:
            task_id = f"task_{int(time.time()*1000)}"

        # 注册任务
        self.running_tasks[task_id] = {
            'status': 'queued',
            'type': 'ocr',
            'cancel_event': threading.Event()  # 用于取消任务的事件
        }

        logger.info(f"Adding OCR task {task_id} to queue. Priority: {priority}")
        # 使用计数器作为第二排序键，避免比较不可比较的对象
        count = next(self.counter)
        self.ocr_queue.put((priority, count, task_id, task_func, args))
        return task_id

    def cancel_task(self, task_id):
        """取消指定任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id]['cancel_event'].set()
            self.running_tasks[task_id]['status'] = 'cancelled'
            logger.info(f"Task {task_id} marked for cancellation.")
            return True
        return False

    def _ocr_worker_loop(self):
        """OCR 工作线程主循环 - 从队列中取任务并执行"""
        logger.info(f"OCR Worker started in thread {threading.current_thread().name}")
        while self.is_running:
            try:
                # 从优先级队列获取任务（阻塞 1 秒超时）
                priority, count, task_id, func, args = self.ocr_queue.get(timeout=1)
                logger.info(f"OCR Worker picked up task {task_id}")
                self._execute_task(task_id, func, args)
                logger.info(f"OCR Worker finished task {task_id}")
                self.ocr_queue.task_done()
            except queue.Empty:
                continue  # 队列为空，继续等待
            except Exception as e:
                logger.error(f"OCR Worker Error: {e}", exc_info=True)

    def _execute_task(self, task_id, func, args):
        """执行单个任务"""
        if task_id not in self.running_tasks:
            return

        task_info = self.running_tasks[task_id]
        if task_info['status'] == 'cancelled':
            return

        task_info['status'] = 'running'
        cancel_event = task_info['cancel_event']

        try:
            # 执行任务函数（第一个参数是 cancel_event）
            result = func(cancel_event, *args)

            if not cancel_event.is_set():
                self.task_results[task_id] = result
                task_info['status'] = 'completed'
            else:
                task_info['status'] = 'cancelled'

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task_info['status'] = 'failed'
            self.task_results[task_id] = {'error': str(e)}

# 全局任务队列实例
task_queue = TaskQueue()
