from django.contrib import admin
from .models.models import Brand, Subset, Settings, PlayerYearTeamCity, Team, City, KnownName, Parallel, CardAttribute, Condition, CardName, Season
from .models.task import Task, ListingTask, PricingTask, IDTask, ConfirmTask

class BrandAdmin(admin.ModelAdmin):
    list_display = ['raw_value', 'field_key'] 

admin.site.register(Brand, BrandAdmin)

class SubsetAdmin(admin.ModelAdmin):
    list_display = ['raw_value', 'field_key'] 

admin.site.register(Subset, SubsetAdmin)
admin.site.register(Settings)
admin.site.register(Team)
admin.site.register(City) 

class PYTAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'year', 'team', 'city']

admin.site.register(PlayerYearTeamCity, PYTAdmin) 

class KnownNameAdmin(admin.ModelAdmin):
    search_fields = ['raw_value', 'field_key']  # Add any other fields you want searchable
    list_display = ['raw_value', 'field_key']  # Optional: improves visibility

admin.site.register(KnownName, KnownNameAdmin)
admin.site.register(CardAttribute)
admin.site.register(Condition)

@admin.register(Parallel)
class ParallelAdmin(admin.ModelAdmin):
    list_display = ['raw_value', 'field_key', 'year', 'brand', 'subset', 'filter_terms']  # Optional: improves visibility

admin.site.register(CardName)
admin.site.register(Season)

class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'actual_type']
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


class ConfirmTaskAdmin(admin.ModelAdmin):
    list_display = ['id']

class IDTaskAdmin(admin.ModelAdmin):
    list_display = ['card']


class PricingTaskAdmin(admin.ModelAdmin):
    list_display = ['card', 'csr']

admin.site.register(Task, TaskAdmin)

admin.site.register(ConfirmTask, ConfirmTaskAdmin)
admin.site.register(ListingTask, ListingTaskAdmin)
admin.site.register(IDTask, IDTaskAdmin)
admin.site.register(PricingTask, PricingTaskAdmin)
