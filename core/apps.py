import os
from django.apps import AppConfig
#from services.queue import Queue

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Start the queue when Django starts
        from services.queue import Queue
        if os.environ.get("RUN_MAIN") == "true":
            self.queue = Queue(interval=10.0)
            self.queue.start()
