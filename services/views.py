from django.shortcuts import render
from services.models.task import Task, ListingTask, BulkListingTask, PricingTask, IDTask
from core.models.CardSearchResult import CardSearchResult
from core.models.Card import Card
from core.models.Status import StatusBase
from core.models.TagGroup import TagGroup
from services import lookup
import calendar, json
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from types import SimpleNamespace
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.apps import apps
from django.views.decorators.http import require_POST
from django.db.models import F, ExpressionWrapper, DateTimeField, DurationField
from django.db.models.functions import Now, Abs, Extract
from django.utils import timezone
from django.template.loader import render_to_string
import time
from datetime import date, timedelta
from django.db.models import Q
import os
from django.conf import settings
from django.http import HttpResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Import the wrapper function directly from your model pipeline script
from services.supervision_extract import run_pipeline_on_file

def task_monitor_data(request):
    now = timezone.now()
    
    # Get range from JS; default to 'now' if missing to avoid heavy queries
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    queryset = ListingTask.objects.all() # Or StatusBase.objects.all()

    if start_str and end_str:
        # Using __date lookup if your strings are YYYY-MM-DD
        # or range if they include times
        queryset = queryset.filter(
            scheduled_for__date__gte=start_str,
            scheduled_for__date__lte=end_str
        )

    # Sort by closest to "now" so the monitor sees imminent changes first
    tasks = queryset.annotate(
        time_diff_seconds=Abs(Extract(F('scheduled_for') - now, 'epoch'))
    ).order_by('time_diff_seconds')

    data = []
    for t in tasks:
        # Using getattr to handle fields that might vary across subclasses
        data.append({
            "id": t.id,
            "name": getattr(t, 'name', 'Unknown'),
            "status": getattr(t, 'status', ''),
            "scheduled": t.scheduled_for.strftime("%Y-%m-%d %H:%M:%S") if t.scheduled_for else "",
            "html": render_to_string("components/task.html", {"task": t, "detail_level": 0}),
            "error": getattr(t, 'error_str', ""),
            "type": t.__class__.__name__
        })

    return JsonResponse({"data": data})

def retry_task(request, task_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
        
    task = get_object_or_404(Task, id=task_id)
    when = request.POST.get('when', 'None')
    
    # Base configuration: if None, pass None to preserve task baseline time config
    scheduled_time = None 
    
    if when != 'None':
        # 1. Grab the existing task's clock time to merge with the new date
        # Fallback to current time if the relation fields are empty
        current_schedule = getattr(task, 'scheduled_for', None) or timezone.now()
        existing_time = current_schedule.time()
        
        # 2. Compute the new target date anchor
        today_date = timezone.now().date()
        print("here")
        if when == 'today':
            target_date = today_date
        elif when == 'tomorrow':
            target_date = today_date + timedelta(days=1)
        elif when.startswith('offset:'):
            try:
                days_count = int(when.split(':')[1])
                target_date = today_date + timedelta(days=days_count)
            except (ValueError, IndexError):
                return JsonResponse({"error": "Invalid day offset format"}, status=400)
        else:
            # Explicit ISO Date string choice: "YYYY-MM-DD"
            try:
                target_date = datetime.strptime(when, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"error": "Invalid explicit date format"}, status=400)
                
        # 3. Combine the computed date with the task's original clock time
        naive_dt = datetime.combine(target_date, existing_time)
        scheduled_time = timezone.make_aware(naive_dt, timezone.get_current_timezone())

    # 4. Hand over the evaluation directly to your core config engine
    try:
        core_config = apps.get_app_config("core")
        core_config.queue.reschedule_task(task, scheduled_time)
        return JsonResponse({"status": "success", "message": f"Task scheduled for {scheduled_time or 'Task Default'}"})
    except Exception as e:
        return JsonResponse({"error": f"Queue transaction failed: {str(e)}"}, status=500)

def delete_task(request, task_id):
    if request.method == "POST":
        task = get_object_or_404(Task, id=task_id)
        core_config = apps.get_app_config("core")
        core_config.queue.remove_task(task)
        task.delete()
        return JsonResponse({"success": True})

@csrf_exempt
def confirm_listing_status(request, task_id):
    if request.method == "POST":
        task = get_object_or_404(ListingTask, id=task_id)
    
        core_config = apps.get_app_config("core")
        core_config.queue.schedule_confirm_task(name=f"confirm listings", card=task.card, callback=lookup.bulk_order_update, params={"card_ids": [task.card.id], "listing_ids":[task.card.listed_card_info.listing_id]}, on_success_status=StatusBase.CONFIRMED)

        return JsonResponse({"success": True})

def task_queue(request):
    return render(request, 'services/task_queue.html')

def start_queue(request):
    if request.method == "POST":
        # Logic to start your background worker or update status
        core_config = apps.get_app_config("core")
        core_config.queue.start()
        messages.success(request, "Queue started successfully!")
    return redirect(request.META.get('HTTP_REFERER', 'task_queue'))

def stop_queue(request):
    if request.method == "POST":
        # Logic to pause/stop processing
        core_config = apps.get_app_config("core")
        core_config.queue.stop()
        messages.warning(request, "Queue has been stopped.")
    return redirect(request.META.get('HTTP_REFERER', 'task_queue'))

def reset_queue(request):
    if request.method == "POST":
        # Example: Move all 'failed' or 'processing' tasks back to 'pending'
        core_config = apps.get_app_config("core")
        core_config.queue.start()
        messages.info(request, "Queue has been reset to pending status.")
    return redirect(request.META.get('HTTP_REFERER', 'task_queue'))

@require_POST
def clear_recent_tasks(request):
    """
    POST handler called from navbar to purge pending tasks created 
    within x minutes out of memory arrays and database backends.
    """
    try:
        minutes = int(request.POST.get('minutes', 15))
    except (ValueError, TypeError):
        minutes = 15

    try:
        core_config = apps.get_app_config("core")
        deleted_count = core_config.queue.clear_recent_pending_tasks(minutes=minutes)
        
        if deleted_count > 0:
            messages.success(request, f"Permanently cleared {deleted_count} recent pending tasks.")
        else:
            messages.info(request, f"No pending tasks found within the past {minutes} minutes.")
    except Exception as e:
        messages.error(request, f"Failed to execute batch task purge: {str(e)}")

    return redirect(request.META.get('HTTP_REFERER', 'task_queue'))

def task_calendar(request):
    start_time = time.perf_counter()
    today = date.today()
    week_param = request.GET.get("week")

    # 1. Determine the Start of the Week (Sunday)
    if week_param:
        try:
            week_start = date.fromisoformat(week_param)
            days_since_sun = (week_start.weekday() + 1) % 7
            week_start = week_start - timedelta(days=days_since_sun)
        except ValueError:
            days_since_sun = (today.weekday() + 1) % 7
            week_start = today - timedelta(days=days_since_sun)
    else:
        days_since_sun = (today.weekday() + 1) % 7
        week_start = today - timedelta(days=days_since_sun)

    week_days = [week_start + timedelta(days=i) for i in range(7)]
    start_range = week_days[0]
    end_range = week_days[-1]

    #logger.debug(f"[Debug Logs] Initializing calendar load for range: {start_range} to {end_range}")

    # 2. Optimized Combined Task Fetching
    # Get the bulk IDs for the exclusion check
    bulk_task_ids = BulkListingTask.objects.filter(
        scheduled_for__date__range=(start_range, end_range)
    ).values_list('id', flat=True)

    # Query the base table using our precise logical condition
    combined_tasks = Task.objects.filter(
        scheduled_for__date__range=(start_range, end_range)
    ).filter(
        Q(bulklistingtask__isnull=False) | 
        (
            Q(listingtask__isnull=False) & 
            (Q(predecessor__isnull=True) | ~Q(predecessor_id__in=bulk_task_ids))
        )
    ).select_related(
        'predecessor', 
        'listingtask__card__listed_card_info',  
        'listingtask__csr'
    ).prefetch_related(
        # Fix: Traverse from the Bulk task down through its children listings to grab the prices
        'bulklistingtask__successors__listingtask__card__listed_card_info',
        'bulklistingtask__successors__listingtask__csr',
    ).order_by('id')

    # 3. Map both item types into day slots
    day_map = {}
    for task in combined_tasks:
        d = task.scheduled_for.date()
        day_map.setdefault(d, []).append(task)

    # 4. Build Day Objects with highly optimized lookups
    day_objects = []
    for d in week_days:
        tasks = sorted(day_map.get(d, []), key=lambda t: t.scheduled_for)
        
        # Helper function to extract price cleanly across polymorphic types
        def get_task_price(t):
            try:
                # Dig down to find whichever related object path is hydrated
                if hasattr(t, 'listingtask') and t.listingtask and t.listingtask.card:
                    return t.listingtask.card.listed_card_info.list_price or 0
                elif hasattr(t, 'bulklistingtask') and t.bulklistingtask:
                    return t.bulklistingtask.value or 0
            except AttributeError:
                pass
            return 0

        # Build summaries cleanly without triggering subsequent query thrashing
        summary = {
            "total_tasks": len(tasks),
            "success": sum(1 for t in tasks if t.status == StatusBase.SUCCESS),
            "success_val": sum(get_task_price(t) for t in tasks if t.status == StatusBase.SUCCESS),
            "failed": sum(1 for t in tasks if t.status == StatusBase.FAILED),
            "failed_val": sum(get_task_price(t) for t in tasks if t.status == StatusBase.FAILED),
            "pending": sum(1 for t in tasks if t.status == StatusBase.PENDING),
            "pending_val": sum(get_task_price(t) for t in tasks if t.status == StatusBase.PENDING)
        }

        day_objects.append(SimpleNamespace(
            date=d,
            tasks=tasks,
            summary=summary,
            is_today=(d == today)
        ))

    # 5. Calculate Navigation Offsets
    prev_week_start = week_start - timedelta(days=7)
    next_week_start = week_start + timedelta(days=7)

    context = {
        "day_objects": day_objects,
        "week_start": week_start,
        "today": today,
        "prev_week": prev_week_start.strftime("%Y-%m-%d"),
        "next_week": next_week_start.strftime("%Y-%m-%d"),
    }

    duration = time.perf_counter() - start_time
    #logger.debug(f"[Debug Logs] Calendar compilation complete. Execution time: {duration:.4f} seconds.")

    return render(request, "services/task_calendar.html", context)

def tasks_list(request):

    tasks = Task.objects.order_by('-scheduled_for')

    return render(request, "services/task_list.html", {"tasks": tasks})

# --- DEBUG LOG ---
# Route Target: /process_scans/<collection_id>
# Action: Capture dropzone upload, write temp asset, run GroundedSAM inference loop, clean up

@csrf_exempt
def process_scans(request):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    # 1. Pull the array of images matching the form.append("images", f) key from JS
    uploaded_files = request.FILES.getlist("images")
    if not uploaded_files:
        return HttpResponse("<p style='color:red;'>Error: No images detected in request.</p>")

    # 2. Establish output directories matching media storage path rules
    output_dir = os.path.join(settings.MEDIA_ROOT, f"extracted_cards/")
    os.makedirs(output_dir, exist_ok=True)

    total_cropped = 0
    file_count = len(uploaded_files)

    print(f"[DEBUG] View starting inference pass on {file_count} upload file targets.")

    for f in uploaded_files:
        # Save payload to a temporary file layout so cv2/PIL can read it via string paths
        temp_name = default_storage.save(f"temp_scans/{f.name}", ContentFile(f.read()))
        absolute_temp_path = os.path.join(settings.MEDIA_ROOT, temp_name)

        try:
            # 3. Fire your optimized wrapper execution loop
            count = run_pipeline_on_file(image_path=absolute_temp_path, output_dir=output_dir)
            total_cropped += count
        except Exception as e:
            print(f"[ERROR] Pipeline execution exception on {f.name}: {str(e)}")
        finally:
            # 4. Immediate storage cleanup to keep the disk light
            if os.path.exists(absolute_temp_path):
                os.remove(absolute_temp_path)

    # Return a simple clean string that drops straight into your front-end results box
    success_message = f"<h4>Processing Complete!</h4>Processed {file_count} scan file(s) and isolated <b>{total_cropped}</b> individual card crop assets."
    return HttpResponse(success_message)


@csrf_exempt
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('tasks_list')

@csrf_exempt
def clear_tasks(request, status_value):
    try:
        status = StatusBase(status_value)
    except ValueError:
        raise Exception(f"Invalid status: {status_value}")

    Task.objects.filter(status=status).delete()
    return redirect('tasks_list')

@csrf_exempt
def task_reset(request, task_id):
    data = json.loads(request.body)
    new_dt = data.get("new_datetime")
    print(new_dt)

    # delete + recreate logic here
    task = Task.objects.get(id=task_id)
    task.reset(new_dt)

    return JsonResponse({"status": "ok"})

from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone
from services.models.task import Task
from core.models.Status import StatusBase

def queue_dashboard(request):

    core_config = apps.get_app_config("core")
    # In-memory tasks currently scheduled in thread queue
    memory_tasks = core_config.queue.tasks

    # Database summary counts
    counts = {
        'pending': Task.objects.filter(status=StatusBase.PENDING).count(),
        'running': Task.objects.filter(status=StatusBase.RUNNING).count(),
        'success': Task.objects.filter(status=StatusBase.SUCCESS).count(),
        'failed': Task.objects.filter(status=StatusBase.FAILED).count(),
        'staged': Task.objects.filter(status=StatusBase.STAGED).count(),
    }

    # Recent completed or failed database tasks for audit table
    recent_db_tasks = Task.objects.select_related(
        'listingtask', 'pricingtask', 'idtask', 'uploadtask', 'confirmtask'
    ).prefetch_related('successors').order_by('-executed_at')[:25]

    context = {
        'memory_tasks': memory_tasks,
        'counts': counts,
        'recent_db_tasks': recent_db_tasks,
        'now': timezone.now(),
    }
    return render(request, 'services/task_queue.html', context)


@require_POST
def clear_recent_tasks_view(request):
    minutes = int(request.POST.get('minutes', 15))
    queue_instance.clear_recent_pending_tasks(minutes=minutes)
    return redirect('queue_dashboard')


@require_POST
def reset_queue_view(request):
    queue_instance.reset()
    return redirect('queue_dashboard')