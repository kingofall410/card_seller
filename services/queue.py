import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Dict
from django.utils import timezone
from services.models.task import Task
from importlib import import_module
import json

@dataclass(order=True)
class MemoryTask:
    scheduled_for: datetime
    name: str = field(compare=False)
    callback: Callable = field(compare=False)
    params: Dict[str, Any] = field(compare=False, default_factory=dict)
    db_id: int = field(compare=False, default=None)

    def run(self):
        self.callback(**self.params)

class Queue:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.tasks = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()

    def add(self, task: Task):
        self.tasks.append(task)
        self.tasks.sort()  # earliest datetime first

    def _load_pending_tasks(self):
        pending = Task.objects.filter(status="pending")
        for t in pending:
            callback = self._import_callback(t.callback_path)
            mem_task = MemoryTask(
                scheduled_for=t.scheduled_for,
                name=t.name,
                callback=callback,
                params=t.params(),
                db_id=t.id
            )
            self.tasks.append(mem_task)
        self.tasks.sort()

    def _import_callback(self, path):
        module_name, func_name = path.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, func_name)

    def _loop(self):
        while not self._stop.is_set():
            now = timezone.now()

            ready = [t for t in self.tasks if t.scheduled_for <= now]
            self.tasks = [t for t in self.tasks if t.scheduled_for > now]

            for task in ready:
                db_task = Task.objects.get(id=task.db_id)
                db_task.status = "running"
                db_task.save(update_fields=["status"])

                try:
                    task.run()
                    db_task.status = "done"
                except Exception:
                    db_task.status = "failed"
                db_task.save(update_fields=["status"])

            time.sleep(self.interval)

    def schedule_task(self, name, when, callback, params):
        t = Task.objects.create(name=name, scheduled_for=when, callback_path=f"{callback.__module__}.{callback.__name__}", \
                                params_json=json.dumps(params), status="pending")

        self.add(MemoryTask(scheduled_for=when, name=name, callback=callback, params=params, db_id=t.id))
