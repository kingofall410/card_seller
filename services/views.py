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
        current_schedule = getattr(task.listingtask, 'scheduled_for', None) or timezone.now()
        existing_time = current_schedule.time()
        
        # 2. Compute the new target date anchor
        today_date = timezone.now().date()
        
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
    today = date.today()
    week_param = request.GET.get("week")

    # 1. Determine the Start of the Week (Sunday)
    if week_param:
        try:
            # Parse the requested week start date (e.g., "2026-05-11")
            week_start = date.fromisoformat(week_param)
            # Ensure it falls on a Sunday to keep our layout clean
            days_since_sun = (week_start.weekday() + 1) % 7
            week_start = week_start - timedelta(days=days_since_sun)
        except ValueError:
            # Fallback if the date format is corrupted
            days_since_sun = (today.weekday() + 1) % 7
            week_start = today - timedelta(days=days_since_sun)
    else:
        # Default to the current week containing "today"
        days_since_sun = (today.weekday() + 1) % 7
        week_start = today - timedelta(days=days_since_sun)

    # A week is exactly 7 days from Sunday to Saturday
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    start_range = week_days[0]
    end_range = week_days[-1]

    # 2. Optimized Task Fetching for this specific week range
    listingtasks = ListingTask.objects.filter(
        scheduled_for__date__range=(start_range, end_range)
    ).select_related('card', 'csr').order_by('id')

    day_map = {}
    for task in listingtasks:
        d = task.scheduled_for.date()
        day_map.setdefault(d, []).append(task)

    # 3. Build Day Objects for the 7 Days
    day_objects = []
    for d in week_days:
        tasks = sorted(day_map.get(d, []), key=lambda t: t.id)
        
        # Build simple summaries
        summary = {
            "total_tasks": len(tasks),
            "success": sum(1 for task in tasks if task.status == StatusBase.SUCCESS),
            "success_val": sum(task.listingtask.card.listed_card_info.list_price for task in tasks if task.status == StatusBase.SUCCESS),
            "failed": sum(1 for task in tasks if task.status == StatusBase.FAILED),
            "failed_val": sum(task.listingtask.card.listed_card_info.list_price for task in tasks if task.status == StatusBase.FAILED),
            "pending": sum(1 for task in tasks if task.status == StatusBase.PENDING),
            "pending_val": sum(task.listingtask.card.listed_card_info.list_price for task in tasks if task.status == StatusBase.PENDING)
        }

        day_objects.append(SimpleNamespace(
            date=d,
            tasks=tasks,
            summary=summary,
            is_today=(d == today)
        ))

    # 4. Calculate Navigation Offsets
    prev_week_start = week_start - timedelta(days=7)
    next_week_start = week_start + timedelta(days=7)

    context = {
        "day_objects": day_objects,
        "week_start": week_start,
        "today": today,
        # Navigation parameters
        "prev_week": prev_week_start.strftime("%Y-%m-%d"),
        "next_week": next_week_start.strftime("%Y-%m-%d"),
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

