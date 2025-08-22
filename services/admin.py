from django.contrib import admin
from .models import Brand, Subset, Settings, Team, City, KnownName, Parallel, CardAttribute, Condition, CardName

admin.site.register(Brand)
admin.site.register(Subset)
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