# services/models.py
from django.db import models
from django.utils import timezone
import json

class Task(models.Model):
    name = models.CharField(max_length=200)
    scheduled_for = models.DateTimeField()
    callback_path = models.CharField(max_length=300)
    params_json = models.TextField(default="{}")
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def params(self):
        return json.loads(self.params_json)
    
    def __str__(self):
        return f"{self.name} @ {self.scheduled_for}"