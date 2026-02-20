from django.urls import path
from . import views

urlpatterns = [
    path("tasks/", views.tasks_list, name="tasks_list"),    
    path("calendar/", views.task_calendar, name="calendar"),
    path('delete_task/<int:task_id>', views.delete_task, name="delete_task"),
    path('clear_tasks/<slug:status_value>/', views.clear_tasks, name='clear_tasks'),
    path("task_reset/<int:task_id>/", views.task_reset, name="task_reset")
]
