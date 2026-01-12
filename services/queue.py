import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List


@dataclass(order=True)
class Task:
    time: float
    name: str = field(compare=False)
    callback: Callable = field(compare=False)
    params: Dict[str, Any] = field(compare=False, default_factory=dict)

    def run(self):
        print("run")
        self.callback(**self.params)


class Queue:
    def __init__(self, interval: float = 1.0):
        """
        interval: how often (in seconds) the queue wakes up to check for work
        """
        self.interval = interval
        self.tasks: List[Task] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        print("start")
        self._thread.start()

    def stop(self):
        print("stop")
        self._stop.set()
        self._thread.join()

    def add(self, task: Task):
        print("add")
        self.tasks.append(task)
        self.tasks.sort()  # keep earliest task first

    def _loop(self):
        while not self._stop.is_set():
            print("loop")
            now = time.time()

            ready = [t for t in self.tasks if t.time <= now]
            self.tasks = [t for t in self.tasks if t.time > now]

            for task in ready:
                try:
                    task.run()
                except Exception as e:
                    print(f"Task '{task.name}' failed: {e}")

            time.sleep(self.interval)