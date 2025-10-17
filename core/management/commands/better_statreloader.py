import subprocess
import time
import os
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from django.core.management.base import BaseCommand
import sys

class SaveAllTriggerHandler(FileSystemEventHandler):
    def __init__(self, restart_callback, debounce_window=1.5, threshold=3):
        self.restart_callback = restart_callback
        self.debounce_window = debounce_window
        self.threshold = threshold
        self.recent_changes = deque() 
        self.last_restart = 0

    def on_modified(self, event):
        if not event.src_path.endswith(".py"):
            return

        now = time.time()
        self.recent_changes.append(now)

        # Remove old entries
        while self.recent_changes and now - self.recent_changes[0] > self.debounce_window:
            self.recent_changes.popleft()

        if len(self.recent_changes) >= self.threshold and now - self.last_restart > self.debounce_window:
            print(f"🧠 Detected Save All: {len(self.recent_changes)} files modified")
            self.last_restart = now
            self.restart_callback()

class Command(BaseCommand):
    help = "Watch for Save All events and restart Django server"

    def handle(self, *args, **options):
        path = os.getcwd() 
        self.process = None

                
        def restart_server():
            if self.process:
                self.process.terminate()
                self.process.wait()
            print("🚀 Starting Django server...")
            self.process = subprocess.Popen([sys.executable, "manage.py", "runserver", "--noreload"])

        event_handler = SaveAllTriggerHandler(restart_callback=restart_server)
        observer = Observer()
        observer.schedule(event_handler, path=path, recursive=True)
        observer.start()

        restart_server()  # Initial launch

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            if self.process:
                self.process.terminate()
        observer.join()