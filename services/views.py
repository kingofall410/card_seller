from django.shortcuts import render
from services.models.task import Task, ListingTask, PricingTask, IDTask
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
from django.db.models import F, ExpressionWrapper, DateTimeField, DurationField
from django.db.models.functions import Now, Abs, Extract
from django.utils import timezone
from django.template.loader import render_to_string

def task_monitor_data(request):
    now = timezone.now()
    
    # Get range from JS; default to 'now' if missing to avoid heavy queries
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    queryset = Task.objects.all() # Or StatusBase.objects.all()

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
    ).order_by('time_diff_seconds')[:200]

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
    month_param = request.GET.get("month")
    today = date.today()

    if month_param:
        try:
            year, month = map(int, month_param.split("-"))
            current = date(year, month, 1)
        except ValueError:
            current = date(today.year, today.month, 1)
    else:
        current = date(today.year, today.month, 1)

    # 1. Calendar Setup (Sunday Start)
    cal = calendar.Calendar(firstweekday=6)
    # itermonthdates gives us the full grid (including padding days from prev/next month)
    month_days = list(cal.itermonthdates(current.year, current.month))

    # 2. Optimized Task Fetching
    # Filter by the range of dates visible on the calendar to avoid loading the whole DB
    start_range = month_days[0]
    end_range = month_days[-1]
    
    listingtasks = ListingTask.objects.filter(scheduled_for__date__range=(start_range, end_range)).select_related('card', 'csr').order_by('scheduled_for')
    pricingtasks = []#PricingTask.objects.filter(scheduled_for__date__range=(start_range, end_range)).select_related('card', 'csr').order_by('scheduled_for')

    day_map = {}
    for task in (list(listingtasks)+list(pricingtasks)):
        d = task.scheduled_for.date()
        day_map.setdefault(d, []).append(task)

    # 3. Determine Current Week (for the "Week View" toggle)
    # Since your calendar is Sunday start, find the most recent Sunday
    days_since_sun = (today.weekday() + 1) % 7 
    week_start = today - timedelta(days=days_since_sun)
    week_end = week_start + timedelta(days=6)

    # 4. Build Unified Day Objects
    day_objects = []
    for d in month_days:
        day_objects.append(SimpleNamespace(
            date=d,
            tasks=day_map.get(d, []),
            is_today=(d == today),
            in_current_month=(d.month == current.month),
            in_current_week=(week_start <= d <= week_end)
        ))

    context = {
        "day_objects": day_objects,
        "current_month": current,
        "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "today": today,
        # Navigation
        "prev_month": (current.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
        "next_month": (current.replace(day=28) + timedelta(days=5)).replace(day=1).strftime("%Y-%m"),
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
