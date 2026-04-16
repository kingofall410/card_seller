import threading
import time
import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Dict, List
from importlib import import_module

from django.utils import timezone
from django.db import transaction

from services.models.task import Task, ListingTask, PricingTask, IDTask, UploadTask
from core.models.Status import StatusBase

@dataclass(order=True)
class MemoryTask:
    scheduled_for: datetime
    name: str = field(compare=False)
    callback: Callable = field(compare=False)
    params: Dict[str, Any] = field(compare=False, default_factory=dict)
    db_id: int = field(compare=False, default=None)
    successor_id: Any = field(compare=False, default=None)
    status: str = field(compare=False, default=StatusBase.PENDING)
    on_success_status: str = field(compare=False, default=StatusBase.SUCCESS)

    def run(self):
        try:
            print(f"[RUNNING] {self.db_id}. {self.name} (ID: {self.db_id})")
            retVal = self.callback(**self.params)
            
            # If it returns None, "", 0, or False, it's a failure.
            # Only an explicit True (or truthy value) allows the chain to continue.
            if not retVal:
                print(f"[LOGIC FAIL] {self.db_id}. {self.name} returned {retVal}. Stopping chain.")
                return False
            
            print(f"[SUCCESS] {self.db_id}. {self.name} completed.")
            return True
        except Exception:
            print(f"[CRASH] {self.db_id}. {self.name} raised an exception:")
            traceback.print_exc()
            return False

class Queue:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.tasks: List[MemoryTask] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._load_pending_tasks()

    def start(self):
        print("[QUEUE] Starting thread...")
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        print("[QUEUE] Stopping thread...")
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()

    def add(self, mem_task: MemoryTask):
        print(f"[QUEUE] Adding task: {mem_task.name} (ID: {mem_task.db_id})")
        self.tasks.append(mem_task)
        self.tasks.sort() 

    def reset(self):
        print("[QUEUE] Resetting...")
        self.tasks = []
        self._load_pending_tasks()

    def _reset_running_tasks(self):
        count = Task.objects.filter(status__in=["running", StatusBase.RUNNING]).update(status=StatusBase.PENDING)
        if count > 0:
            print(f"[CLEANUP] Reset {count} stuck 'running' tasks to 'pending'.")

    def _load_pending_tasks(self):
        self._reset_running_tasks()
        pending = Task.objects.filter(status=StatusBase.PENDING).prefetch_related('successor')
        print(f"[LOADER] Found {pending.count()} pending tasks in DB.")

        for t in pending:
            try:
                callback = self._import_callback(t.callback_path)
                succ = t.successor.first() 
                
                mem_task = MemoryTask(
                    scheduled_for=t.scheduled_for,
                    name=t.name,
                    callback=callback,
                    params=t.params(),
                    db_id=t.id,
                    successor_id=succ.id if succ else None,
                    status=t.status,
                    on_success_status=t.on_success_status
                )
                self.tasks.append(mem_task)
            except Exception as e:
                print(f"[LOADER ERROR] Task {t.id}: {e}")
        
        self.tasks.sort()

    def _import_callback(self, path):
        module_name, func_name = path.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, func_name)

    def _loop(self):
        while not self._stop.is_set():
            now = timezone.now()
            
            # 1. Identify what can run RIGHT NOW
            ready = [t for t in self.tasks if t.scheduled_for <= now and t.status == StatusBase.PENDING]
            
            if ready:
                print(f"[LOOP] {len(ready)} tasks ready to execute.")

            for task in ready:

                if self._stop.is_set():
                    break
                # Re-verify status in case another thread or predecessor logic changed it
                if task.status != StatusBase.PENDING:
                    continue

                db_task = Task.objects.get(id=task.db_id)
                csr = None
                on_success_status = StatusBase.SUCCESS 

                try:
                    db_task.status = StatusBase.RUNNING
                    task.status = StatusBase.RUNNING # Update memory too
                    db_task.save(update_fields=["status"])

                    
                    if task.run():
                        print(f"[SUCCESS] {task.name} succeeded. Triggering successor: {task.successor_id}")
                        task.status = StatusBase.SUCCESS
                        db_task.status = StatusBase.SUCCESS
                        
                        if csr and csr.overall_status not in [StatusBase.LISTED, StatusBase.STAGED, StatusBase.HELD]:
                            console.log("onsuccess", db_task.on_success_status)
                            csr.overall_status = db_task.on_success_status

                        if task.successor_id:
                            # Update DB
                            Task.objects.filter(id=task.successor_id).update(status=StatusBase.PENDING)
                            # Update Memory: Crucial that we only touch the specific successor
                            for mt in self.tasks:
                                if mt.db_id == task.successor_id:
                                    mt.status = StatusBase.PENDING
                                    csr.overall_status = db_task.on_success_status
                    else:
                        print(f"[FAIL] {task.name} failed.")
                        if csr and csr.overall_status not in [StatusBase.LISTED, StatusBase.STAGED, StatusBase.HELD]:
                            csr.overall_status = StatusBase.FAILED
                        task.status = StatusBase.FAILED
                        db_task.status = StatusBase.FAILED

                except Exception as e:
                    print(f"[EXCEPTION] {task.name} failed.")
                    if csr and csr.overall_status not in [StatusBase.LISTED, StatusBase.STAGED, StatusBase.HELD]:
                        csr.overall_status = StatusBase.FAILED
                    task.status = StatusBase.FAILED
                    db_task.status = StatusBase.FAILED
                
                finally:
                    db_task.save(update_fields=["status", "error_str"])
                    if csr:
                        csr.save(update_fields=["overall_status"])
            
                    if self._stop.wait(timeout=self.interval):
                        break
            
            # 2. THE PRUNE
            self.tasks = [t for t in self.tasks if t.status not in [StatusBase.SUCCESS, StatusBase.FAILED]]

            # 3. THE SMART SLEEP
            # We use .wait() here INSTEAD of time.sleep(). 
            # If _stop.set() is called, this returns True INSTANTLY.
            if self._stop.wait(timeout=self.interval):
                print("[QUEUE] Stop signal received during interval. Exiting loop.")
                break

    def schedule_listing_task(self, name, card, csr, when, callback, params):
        t = ListingTask.objects.create(
            name=name, scheduled_for=when, card=card, csr=csr, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING
        )
        self.add(MemoryTask(scheduled_for=when, name=name, callback=callback, params=params, db_id=t.id))
        if csr:
            csr.overall_status = StatusBase.PENDING
            csr.parent_card.listed_card_info.listing_datetime = when
            csr.save(update_fields=['overall_status'])
            csr.parent_card.listed_card_info.save()
        return t

    def schedule_pricing_task(self, name, card, csr, callback, params, predecessor=None, on_success_status=StatusBase.PRICED):
        now = timezone.now()
        starting_status = StatusBase.STAGED if predecessor else StatusBase.PENDING
        
        db_task = PricingTask.objects.create(
            name=name, scheduled_for=now, card=card, csr=csr, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=starting_status, predecessor=predecessor
        )

        mem_task = MemoryTask(
            scheduled_for=now, name=name, callback=callback, params=params, 
            db_id=db_task.id, status=starting_status
        )
        
        # Link successor logic in memory BEFORE adding to list
        if predecessor:
            for mt in self.tasks:
                if mt.db_id == predecessor.id:
                    print(f"[LINK] Linking {predecessor.id} -> Successor {db_task.id}")
                    mt.successor_id = db_task.id
        
        self.add(mem_task)

        if csr:
            csr.overall_status = starting_status
            csr.save(update_fields=['overall_status'])
        
        return db_task

    def schedule_id_task(self, name, callback, params, card):
        now = timezone.now()
        t = IDTask.objects.create(
            name=name, scheduled_for=now, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING, card=card
        )
        self.add(MemoryTask(scheduled_for=now, name=name, callback=callback, params=params, db_id=t.id))
        return t

    def schedule_upload_task(self, name, callback, params):
        now = timezone.now()
        t = UploadTask.objects.create(
            name=name, scheduled_for=now, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING
        )
        self.add(MemoryTask(scheduled_for=now, name=name, callback=callback, params=params, db_id=t.id))
        return t