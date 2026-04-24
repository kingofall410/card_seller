from django.contrib import admin
from .models.models import Brand, Subset, Settings, Team, City, KnownName, Parallel, CardAttribute, Condition, CardName, Season
from .models.task import Task, ListingTask, PricingTask, IDTask

class BrandAdmin(admin.ModelAdmin):
    list_display = ['raw_value', 'field_key'] 

admin.site.register(Brand, BrandAdmin)

class SubsetAdmin(admin.ModelAdmin):
    list_display = ['raw_value', 'field_key'] 

admin.site.register(Subset, SubsetAdmin)
admin.site.register(Settings)
admin.site.register(Team)
admin.site.register(City)

class KnownNameAdmin(admin.ModelAdmin):
    search_fields = ['raw_value', 'field_key']  # Add any other fields you want searchable
    list_display = ['raw_value', 'field_key']  # Optional: improves visibility

admin.site.register(KnownName, KnownNameAdmin)
admin.site.register(CardAttribute)
admin.site.register(Condition)
admin.site.register(Parallel)
admin.site.register(CardName)
admin.site.register(Season)

class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'status', 'actual_type']
    def actual_type(self, obj):
        for subclass in Task.__subclasses__():
            try:
                getattr(obj, subclass.__name__.lower())
                return subclass.__name__
            except subclass.DoesNotExist:
                pass
        return "Task"

class ListingTaskAdmin(admin.ModelAdmin):
    list_display = ['id']


class IDTaskAdmin(admin.ModelAdmin):
    list_display = ['card']


class PricingTaskAdmin(admin.ModelAdmin):
    list_display = ['card', 'csr']

admin.site.register(Task, TaskAdmin)

admin.site.register(ListingTask, ListingTaskAdmin)
admin.site.register(IDTask, IDTaskAdmin)
admin.site.register(PricingTask, PricingTaskAdmin)
