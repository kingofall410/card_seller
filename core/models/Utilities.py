from django.db import models

class FieldStructure(models.Model):
    name = models.CharField(max_length=100)
    template = models.CharField(max_length=250)
    max_len = models.IntegerField(default=0)
    min_len = models.IntegerField(default=0)

    def apply_to(self, obj):
        """
        Apply this FieldStructure to another object.
        obj should have attributes matching the placeholders.
        """
        context = {}
        for field in obj._meta.get_fields():
            if hasattr(obj, field.name):
                context[field.name] = getattr(obj, field.name)
        try:
            return self.template.format(**context)
        except KeyError as e:
            return f"Missing field: {e}"
