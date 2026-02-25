import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Dict
from django.utils import timezone
from services.models.task import Task, ListingTask, PricingTask
from core.models.Status import StatusBase
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
        self._load_pending_tasks()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()

    def add(self, task: Task):
        self.tasks.append(task)
        self.tasks.sort()  # earliest datetime first

    def reset(self):
        self.tasks = []
        self._load_pending_tasks()

    def _load_pending_tasks(self):
        pending = Task.objects.filter(status=StatusBase.PENDING)
        for t in pending:
            print(t.id)
            callback = self._import_callback(t.callback_path)
            mem_task = MemoryTask(
                scheduled_for=t.scheduled_for,
                name=t.name,
                callback=callback,
                params=t.params(),
                db_id=t.id
            )
            print("---", mem_task.name)
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
            #print("loop:", ready)
            csr = None
            for task in ready:
                
                db_task = Task.objects.get(id=task.db_id)
                
                try:
                    if hasattr(db_task, "listingtask"):
                        on_success = StatusBase.LISTED
                        csr = db_task.listingtask.csr
                        print(f"Running Listing Task {csr}")
                    elif hasattr(db_task, "pricingtask"):
                        csr = db_task.pricingtask.csr
                        on_success = csr.overall_status
                        print(f"Running Pricing Task {csr}")
                    else:
                        csr = None                    
                        print(db_task)

                    db_task.status = "running"
                    db_task.save(update_fields=["status"])
                    task.run()
                    print("success")
                    csr.overall_status = on_success
                    db_task.status = StatusBase.SUCCESS
                    
                except Exception as e:
                    print("fail", e)
                    db_task.status = StatusBase.FAILED
                    db_task.error_str = str(e)
                    if csr:
                        csr.overall_status = StatusBase.FAILED
                finally:
                    db_task.save(update_fields=["status", "error_str"])
                    if csr:
                        csr.save(update_fields=["overall_status"])
            
            time.sleep(self.interval)

    #move these into the task object
    def schedule_listing_task(self, name, card, csr, when, callback, params):
        t = ListingTask.objects.create(name=name, scheduled_for=when, card=card, csr=csr, callback_path=f"{callback.__module__}.{callback.__name__}", \
                                params_json=json.dumps(params), status=StatusBase.PENDING)
        
        self.add(MemoryTask(scheduled_for=when, name=name, callback=callback, params=params, db_id=t.id))
        csr.overall_status = StatusBase.PENDING
        csr.save()

    def schedule_pricing_task(self, name, card, csr, callback, params):
        now = timezone.now()
        t = PricingTask.objects.create(name=name, scheduled_for=now, card=card, csr=csr, callback_path=f"{callback.__module__}.{callback.__name__}", \
                                params_json=json.dumps(params), status=StatusBase.PENDING)
        
        self.add(MemoryTask(scheduled_for=now, name=name, callback=callback, params=params, db_id=t.id))
        csr.overall_status = StatusBase.PENDING
        csr.save()