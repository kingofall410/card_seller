import os
from django.apps import AppConfig
#from services.queue import Queue

class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return

        from services.queue import Queue
        self.queue = Queue()
        self.queue.start()
