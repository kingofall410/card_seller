import threading
import time
import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta  # Added timedelta for lookbacks
from typing import Callable, Any, Dict, List
from importlib import import_module

from django.utils import timezone
from django.db import transaction
from services.models.task import Task, ListingTask, BulkListingTask, ConfirmTask, PricingTask, IDTask, UploadTask
from core.models.Status import StatusBase

@dataclass(order=True)
class MemoryTask:
    scheduled_for: datetime
    title: str = field(compare=False)
    callback: Callable = field(compare=False)
    params: Dict[str, Any] = field(compare=False, default_factory=dict)
    db_id: int = field(compare=False, default=None)
    successor_ids: [Any] = field(compare=False, default=None)
    status: str = field(compare=False, default=StatusBase.PENDING)
    on_success_status: str = field(compare=False, default=StatusBase.SUCCESS)
    priority: int = field(compare=False, default=0)

    def run(self):
        try:
            print(f"[RUNNING] {self.db_id}. {self.title} (ID: {self.db_id})")
            retVal = self.callback(**self.params)
            
            # 1. If it's a hard boolean False, or completely empty/None, stop the chain.
            if not retVal:
                print(f"[LOGIC FAIL] {self.db_id}. {self.title} returned {retVal}. Stopping chain.")
                return False

            # 2. If it's a dict, safely check the failures. Boolean True or other valid objects skip this entirely.
            elif isinstance(retVal, dict) and retVal.get("failed_count", 0) > 0:
                print(f"[LOGIC FAIL] {self.db_id}. {self.title} reported {retVal['failed_count']} failures. Stopping chain.")

                return False

            print(f"[SUCCESS] {self.db_id}. {self.title} completed.")
            return True
        except Exception:
            print(f"[CRASH] {self.db_id}. {self.title} raised an exception:")
            traceback.print_exc()
            return False

class Queue:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.tasks: List[MemoryTask] = []
        self._stop = threading.Event()
        self._thread = None  
        self._load_pending_tasks()

    def _make_thread(self):
        """Helper to safely instantiate a fresh target thread instance."""
        return threading.Thread(target=self._loop, daemon=True)

    def start(self):
        print("[QUEUE] Starting thread...")
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = self._make_thread()
            self._thread.start()

    def stop(self):
        print("[QUEUE] Stopping thread...")
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def add(self, mem_task: MemoryTask):
        print(f"[QUEUE] Adding task: {mem_task.title} (ID: {mem_task.db_id})")
        self.tasks.append(mem_task)
        self.tasks.sort() 

    def remove(self, task_id):
        mem_task = next((x for x in self.tasks if x.db_id == task_id), None)
        if mem_task:
            print(f"[QUEUE] removing task: {mem_task.title} (ID: {mem_task.db_id})")
            self.tasks.remove(mem_task)
        else:
            print(f"[QUEUE] couldn't find task to remove: {task_id}")
            
    def clear_recent_pending_tasks(self, minutes: int = 15):
        """
        Finds and deletes pending tasks created within the last X minutes
        from both memory and the database tracking layers.
        """
        time_threshold = timezone.now() - timedelta(minutes=minutes)
        
        # Target only tasks that are PENDING and recently created
        recent_pending_query = Task.objects.filter(
            status=StatusBase.PENDING,
            created_at__gte=time_threshold
        )
        
        target_ids = list(recent_pending_query.values_list('id', flat=True))
        
        if not target_ids:
            print(f"[CLEANUP] No pending tasks found created within the last {minutes} minutes.")
            return 0
            
        print(f"[CLEANUP] Clearing {len(target_ids)} recent pending tasks from memory and database...")
        
        # 1. Purge from local thread queue memory layout
        self.tasks = [t for t in self.tasks if t.db_id not in target_ids]
        
        # 2. Hard delete database records cascades down to individual task variants
        count, _ = recent_pending_query.delete()
        print(f"[CLEANUP] Successfully purged {count} task records.")
        return count

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
        pending = Task.objects.filter(status=StatusBase.PENDING).prefetch_related('successors')
        print(f"[LOADER] Found {pending.count()} pending tasks in DB.")

        for t in pending:
            try:
                callback = self._import_callback(t.callback_path)
                succ = t.successors.first() 
                mem_task = MemoryTask(
                    scheduled_for=t.scheduled_for,
                    title=t.title,
                    callback=callback,
                    params=t.params(),
                    db_id=t.id,
                    successor_ids=[s.id for s in t.successors.all()],
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
            
            ready = sorted((t for t in self.tasks if t.scheduled_for <= now and t.status == StatusBase.PENDING), key=lambda x:-x.priority)
            
            if ready:
                print(f"[LOOP] {len(ready)} tasks ready to execute.")

            for task in ready:

                if self._stop.is_set() and not task.priority:
                    break
                if task.status != StatusBase.PENDING:
                    continue

                db_task = Task.objects.prefetch_related("successors").get(id=task.db_id)
                csr = db_task.listingtask.csr if hasattr(db_task, "listingtask") else None
                on_success_status = StatusBase.SUCCESS 

                try:
                    db_task.status = StatusBase.RUNNING
                    task.status = StatusBase.RUNNING 
                    db_task.save(update_fields=["status"])

                    db_task.executed_at = timezone.now()

                    if task.run():
                        
                        print(f"[SUCCESS] {task.title} succeeded. Triggering successors: {task.successor_ids}")
                        task.status = StatusBase.SUCCESS
                        db_task.status = StatusBase.SUCCESS
                        
                        if csr and (csr.overall_status not in [StatusBase.LISTED, StatusBase.HELD] or db_task.on_success_status == StatusBase.CONFIRMED):
                            print("onsuccess", db_task.on_success_status)
                            csr.overall_status = db_task.on_success_status

                        if hasattr(db_task, "bulklistingtask"):
                            print(f"[SUCCESS] {task.title} succeeded. Killing successors: {task.successor_ids}")
                            
                            successors_list = list(Task.objects.filter(id__in=task.successor_ids))
                            print("SL:", successors_list)
                            db_task.successors.update(status=StatusBase.SUCCESS)
                            
                            # 3. Process the objects in-memory
                            for succ in successors_list:
                                print("suc")
                                for mt in self.tasks:      
                                    print("mtdbod", mt.db_id, succ.id)                          
                                    if mt.db_id == succ.id:
                                        mt.status = StatusBase.SUCCESS
                                        succ.status = StatusBase.SUCCESS # Already updated in DB, but updates Python object
                                        
                                        # If prefetched via 'successors__listingtask__csr', these lines won't hit the DB!
                                        succ_csr = succ.listingtask.csr
                                        succ_csr.overall_status = db_task.on_success_status
                                        print(succ_csr)
                                        # succ.save() is redundant here because you ran .update() above! 
                                        # You only need to save the CSR object:
                                        succ_csr.save()

                        elif task.successor_ids:

                            db_task.successors.update(status=StatusBase.PENDING)
                            for mt in self.tasks:
                                if mt.db_id in task.successor_ids:
                                    mt.status = StatusBase.PENDING                                        
                        
                    else:
                        print(f"[FAIL] {task.title} failed.")
                        if csr and csr.overall_status not in [StatusBase.HELD]:
                            csr.overall_status = StatusBase.FAILED
                        task.status = StatusBase.FAILED
                        task.error_str = "logical fail"
                        db_task.status = StatusBase.FAILED

                except Exception as e:
                    print(f"[EXCEPTION] {task.title} failed.")
                    if csr and csr.overall_status not in [StatusBase.LISTED, StatusBase.STAGED, StatusBase.HELD]:
                        csr.overall_status = StatusBase.FAILED
                    task.status = StatusBase.FAILED
                    db_task.status = StatusBase.FAILED
                    task.error_str = e
                
                finally:
                    
                    db_task.completed_at = timezone.now()
                    db_task.save(update_fields=["status", "error_str", "completed_at", "executed_at"])
                    if csr:
                        csr.save(update_fields=["overall_status"])
            
                    if self._stop.wait(timeout=self.interval):
                        break
            
            self.tasks = [t for t in self.tasks if t.status not in [StatusBase.SUCCESS, StatusBase.FAILED]]

            if self._stop.wait(timeout=self.interval):
                print("[QUEUE] Stop signal received during interval. Exiting loop.")
                break

    def remove_task(self, t):
        self.remove(t.id)

    def reschedule_task(self, t, when=None):
        t.scheduled_for = when or t.scheduled_for
        t.status = StatusBase.PENDING
        t.save(update_fields=['scheduled_for', 'status'])

        import importlib
        module_path, class_or_func_name = t.callback_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        callback_func = getattr(module, class_or_func_name)

        params = json.loads(t.params_json) if t.params_json else {}

        self.add(MemoryTask(
            scheduled_for=t.scheduled_for, 
            name=t.title, 
            callback=callback_func, 
            params=params, 
            db_id=t.id
        ))

        csr = t.listingtask.csr
        if csr:
            csr.overall_status = StatusBase.PENDING
            csr.save(update_fields=['overall_status'])
            
            if hasattr(csr, 'parent_card') and hasattr(csr.parent_card, 'listed_card_info') and csr.parent_card.listed_card_info:
                listed_info = csr.parent_card.listed_card_info
                listed_info.listing_datetime = when
                listed_info.save(update_fields=['listing_datetime'])

        return t
    
    def schedule_confirm_task(self, name, card, callback, params, on_success_status=StatusBase.CONFIRMED, priority=0, when=timezone.now()):
        t = ConfirmTask.objects.create(
            title=name, scheduled_for=when, card=card, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING, on_success_status=on_success_status, priority=priority
        )
        self.add(MemoryTask(scheduled_for=when, title=name, callback=callback, params=params, db_id=t.id, priority=priority))
        return t
    
    def _link_pred(self, predecessor, successor):
        for mt in self.tasks:
            if mt.db_id == predecessor.id:
                print(f"[LINK] Linking DB {predecessor.id} -> Successor DB {successor.id}")
                if mt.successor_ids:
                    mt.successor_ids.append(successor.id)
                else:
                    mt.successor_ids = [successor.id]
        
                predecessor.successors.add(successor)
    
    def enqueue_bulk_listing_task(self, mblt, blt):
        mblt.status = StatusBase.PENDING
        blt.value = sum(t.listingtask.card.listed_card_info.list_price for t in blt.successors.all())
        blt.save()

    def prepare_bulk_listing_task(self, name, callback, params, on_success_status=StatusBase.LISTED, priority=0, when=timezone.now(), predecessor=None):
        starting_status = StatusBase.STAGED if predecessor else StatusBase.PENDING
        t = BulkListingTask.objects.create(
            title=name, scheduled_for=when, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=starting_status, on_success_status=on_success_status, priority=priority
        )
        mem_task = MemoryTask(scheduled_for=when, title=name, callback=callback, status=starting_status, params=params, db_id=t.id, priority=priority)
        
        self.add(mem_task)
        if predecessor:
            self._link_pred(predecessor, t)

        return t, mem_task

    def schedule_listing_task(self, name, card, csr, when, callback, params, on_success_status=StatusBase.LISTED, priority=0, predecessor=None):
        starting_status = StatusBase.STAGED if predecessor else StatusBase.PENDING
        t = ListingTask.objects.create(
            title=name, scheduled_for=when, card=card, csr=csr, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=starting_status, on_success_status=on_success_status, priority=priority
        )
        mem_task = MemoryTask(scheduled_for=when, title=name, callback=callback, status=starting_status, params=params, db_id=t.id, priority=priority)

        self.add(mem_task)
        if predecessor:
            self._link_pred(predecessor, t)

        if csr:
            csr.overall_status = StatusBase.PENDING
            csr.parent_card.listed_card_info.listing_datetime = when
            csr.save(update_fields=['overall_status'])
            csr.parent_card.listed_card_info.save()
        return t

    def schedule_pricing_task(self, name, card, csr, callback, params, predecessor=None, on_success_status=StatusBase.PRICED, priority=0):
        now = timezone.now()
        starting_status = StatusBase.STAGED if predecessor else StatusBase.PENDING
        
        db_task = PricingTask.objects.create(
            title=name, scheduled_for=now, card=card, csr=csr, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=starting_status, predecessor=predecessor, priority=priority
        )

        mem_task = MemoryTask(
            scheduled_for=now, title=name, callback=callback, params=params, 
            db_id=db_task.id, status=starting_status, priority=priority
        )
        
        self.add(mem_task)
        if predecessor:
            self._link_pred(predecessor, db_task)
        

        if csr:
            csr.overall_status = starting_status
            csr.save(update_fields=['overall_status'])
        
        return db_task

    def schedule_id_task(self, name, callback, params, card, priority=0):
        now = timezone.now()
        t = IDTask.objects.create(
            title=name, scheduled_for=now, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING, card=card, priority=priority
        )
        self.add(MemoryTask(scheduled_for=now, title=name, callback=callback, params=params, db_id=t.id, priority=priority))
        return t

    def schedule_upload_task(self, name, callback, params, priority=0):
        now = timezone.now()
        t = UploadTask.objects.create(
            title=name, scheduled_for=now, 
            callback_path=f"{callback.__module__}.{callback.__name__}",
            params_json=json.dumps(params), status=StatusBase.PENDING, priority=priority
        )
        self.add(MemoryTask(scheduled_for=now, title=name, callback=callback, params=params, db_id=t.id, priority=priority))
        return t