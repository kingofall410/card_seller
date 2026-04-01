from django.shortcuts import render
from services.models.task import Task, ListingTask
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase
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
from django.db.models import F, ExpressionWrapper, DateTimeField
from django.db.models.functions import Now, Abs
from django.utils import timezone

def task_monitor_data(request):
    # 1. Get the current time
    now = timezone.now()

    # 2. Query tasks ordered by proximity to "now"
    # We annotate each row with the time difference from now, then sort by that delta
    tasks = Task.objects.annotate(
        time_diff=(F('scheduled_for') - now)
    ).order_by('time_diff')[:200]

    data = []
    for t in tasks:
        data.append({
            "id": t.id,
            "name": t.name,
            "status": t.status,
            # If scheduled_for is null, handle gracefully
            "scheduled": t.scheduled_for.strftime("%Y-%m-%d %H:%M:%S") if t.scheduled_for else "",
            "error": t.error_str or "",
            "type": t.__class__.__name__
        })

    return JsonResponse({"data": data})

# views.py
def retry_task(request, task_id):
    if request.method == "POST":
        task = get_object_or_404(Task, id=task_id)
        task.status = "pending"
        task.error_str = ""
        task.save()
        
        # Also tell the Singleton Queue to re-add it if it's not there
        from core.apps import CoreConfig
        # Check if it's already in memory; if not, reload
        # Or simply call Queue().reset() to sync memory with DB
        
        return JsonResponse({"success": True})

def delete_task_json(request, task_id):
    if request.method == "POST":
        task = get_object_or_404(Task, id=task_id)
        task.delete()
        # Ensure memory is also cleared
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


def task_calendar(request):
    # Determine month
    month_param = request.GET.get("month")
    today = date.today()  # <-- ensure today always exists

    if month_param:
        year, month = map(int, month_param.split("-"))
        current = date(year, month, 1)
    else:
        current = date(today.year, today.month, 1)

    # Calendar helpers
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    month_days = list(cal.itermonthdates(current.year, current.month))

    # Group tasks by date
    tasks = ListingTask.objects.order_by('scheduled_for')
    day_map = {}

    days = [d for d in month_days if d.month == current.month]

    for task in tasks:
        day = task.scheduled_for.date()
        day_map.setdefault(day, []).append(task)

    # Build day_objects
    day_objects = [
        SimpleNamespace(date=d, tasks=day_map.get(d, []))
        for d in days
    ]

    # First day index for blanks
    first_day_index = (current.weekday() + 1) % 7

    # WEEK VIEW: compute week containing today
    week_start = today - timedelta(days=today.weekday())  # Monday start
    week_end = week_start + timedelta(days=6)

    week_objects = [
        day for day in day_objects
        if week_start <= day.date <= week_end
    ]

    context = {
        "day_objects": day_objects,
        "week_objects": week_objects,   # <-- ADDED
        "current_month": current,
        "days": [d for d in month_days if d.month == current.month],
        "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "blanks": range(first_day_index),
        "tasks_by_day": {
            "day_map": day_map
        },

        # Navigation
        "prev_month": (current.replace(day=1) - timedelta(days=1)).replace(day=1),
        "next_month": (current.replace(day=28) + timedelta(days=4)).replace(day=1),

        "today": today,
    }

    return render(request, "services/task_calendar.html", context)


def tasks_list(request):

    tasks = Task.objects.order_by('-scheduled_for')

    return render(request, "services/task_list.html", {"tasks": tasks})

    
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
