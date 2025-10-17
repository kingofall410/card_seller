import os
import shutil
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
from core.views import image_views  # adjust if perform_upload is elsewhere

def get_paths(base_path):
    watched = base_path
    dest = os.path.join(settings.MEDIA_ROOT, 'uploads')
    processed = os.path.join(watched, 'processed')
    return watched, dest, processed

def get_all_file_paths(watched_dir):
    return [
        os.path.join(watched_dir, f)
        for f in os.listdir(watched_dir)
        if os.path.isfile(os.path.join(watched_dir, f))
    ]

def transfer_files_to_media(file_paths, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    transferred = []
    for src_path in file_paths:
        filename = os.path.basename(src_path)
        dest_path = os.path.join(dest_dir, filename)
        try:
            shutil.copy2(src_path, dest_path)
            transferred.append(dest_path)
        except Exception as e:
            print(f"Error copying {filename}: {e}")
    return transferred

def get_django_file_objects(file_paths):
    file_objects = []
    for path in file_paths:
        try:
            f = open(path, 'rb')
            django_file = File(f)
            django_file.name = os.path.basename(path)
            file_objects.append(django_file)
        except Exception as e:
            print(f"Error opening {path}: {e}")
    return file_objects

def close_file_objects(file_objects):
    for f in file_objects:
        try:
            f.close()
        except Exception:
            pass

def move_to_processed(original_paths, processed_dir):
    os.makedirs(processed_dir, exist_ok=True)
    for src_path in original_paths:
        filename = os.path.basename(src_path)
        dest_path = os.path.join(processed_dir, filename)
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(filename)
            timestamp = time.strftime("%H%M%S")
            dest_path = os.path.join(processed_dir, f"{base}_{timestamp}{ext}")
        try:
            shutil.move(src_path, dest_path)
            print(f"📦 Moved to processed: {filename}")
        except Exception as e:
            print(f"⚠️ Error moving {filename}: {e}")

class EvenFileCountHandler(FileSystemEventHandler):
    def __init__(self, watched_dir, dest_dir, processed_dir):
        self.watched_dir = watched_dir
        self.dest_dir = dest_dir
        self.processed_dir = processed_dir

    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(0.5)
        file_paths = get_all_file_paths(self.watched_dir)
        file_count = len(file_paths)

        if file_count % 2 == 0:
            print(f"Even file count ({file_count}) detected. Waiting before upload…")
            time.sleep(1.0)
            transferred_paths = transfer_files_to_media(file_paths, self.dest_dir)
            file_objects = get_django_file_objects(transferred_paths)
            try:
                image_views.perform_upload(file_objects)
                print(f"✅ Uploaded {len(file_objects)} files: {[os.path.basename(f.name) for f in file_objects]}")
            except Exception as e:
                print(f"❌ Error uploading files: {e}")
            finally:
                close_file_objects(file_objects)
                move_to_processed(file_paths, self.processed_dir)

class Command(BaseCommand):
    help = 'Monitor folder, transfer to MEDIA_ROOT, and upload when file count is even'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, help='Custom folder to monitor')

    def handle(self, *args, **options):
        base_path = options['path'] or os.path.join(settings.WATCHED_ROOT, 'SaveFile')
        watched_dir, dest_dir, processed_dir = get_paths(base_path)

        os.makedirs(watched_dir, exist_ok=True)
        os.makedirs(dest_dir, exist_ok=True)
        os.makedirs(processed_dir, exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"📡 Watching folder: {watched_dir}"))

        initial_paths = get_all_file_paths(watched_dir)
        if len(initial_paths) % 2 == 0 and initial_paths:
            print(f"🚀 Startup: Even file count ({len(initial_paths)}). Transferring and uploading.")
            transferred_paths = transfer_files_to_media(initial_paths, dest_dir)
            file_objects = get_django_file_objects(transferred_paths)
            try:
                image_views.perform_upload(file_objects)
                print(f"✅ Uploaded {len(file_objects)} files.")
            except Exception as e:
                print(f"❌ Error during startup upload: {e}")
            finally:
                close_file_objects(file_objects)
                move_to_processed(initial_paths, processed_dir)

        event_handler = EvenFileCountHandler(watched_dir, dest_dir, processed_dir)
        observer = Observer()
        observer.schedule(event_handler, watched_dir, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            self.stdout.write(self.style.WARNING("🛑 Stopped watching."))
        observer.join()
