import os
from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return

        from services.queue_service import Queue
        self.queue = Queue()
        self.queue.start()
        
