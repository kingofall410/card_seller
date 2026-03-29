from django.urls import path
from . import views

urlpatterns = [
    path("tasks/", views.tasks_list, name="tasks_list"),    
    path("task_queue/", views.task_queue, name="task_queue"),    
    path("task_monitor_data/", views.task_monitor_data, name="task_monitor_data"),
    path("calendar/", views.task_calendar, name="calendar"),
    path('delete_task/<int:task_id>', views.delete_task, name="delete_task"),
    path('clear_tasks/<slug:status_value>/', views.clear_tasks, name='clear_tasks'),
    path("task_reset/<int:task_id>/", views.task_reset, name="task_reset"),
    path('start_queue/', views.start_queue, name='start_queue'),
    path('stop_queue/', views.stop_queue, name='stop_queue'),
    path('reset_queue/', views.reset_queue, name='reset_queue'),
]
