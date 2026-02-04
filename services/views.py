from django.shortcuts import render
from services.models.task import Task, ListingTask
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase
import calendar
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from types import SimpleNamespace


def task_calendar(request):
    # Determine month
    month_param = request.GET.get("month")
    if month_param:
        year, month = map(int, month_param.split("-"))
        current = date(year, month, 1)
    else:
        today = date.today()
        current = date(today.year, today.month, 1)

    # Calendar helpers
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    month_days = list(cal.itermonthdates(current.year, current.month))

    # Group tasks by date
    tasks = ListingTask.objects.order_by('scheduled_for')
    day_map = {}

    days = [d for d in month_days if d.month == current.month]

    day_map = {}

    for task in tasks:
        day = task.scheduled_for.date()
        day_map.setdefault(day, []).append(task)

    # 2. Now build day_objects using the populated map
    day_objects = [
        SimpleNamespace(date=d, tasks=day_map.get(d, []))
        for d in days
    ]

    first_day_index = (current.weekday() + 1) % 7


    context = {
        "day_objects": day_objects,
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
        "today": date.today()
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
