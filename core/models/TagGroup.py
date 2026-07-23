from django.db import models
from django.db.models import Q
from collections import defaultdict
from core.models.Utilities import FieldStructure
from core.models.Status import StatusBase
from datetime import timedelta
from django.utils import timezone

class TagGroup(models.Model):
    group_key = models.CharField(max_length=50)#limit tied to inventoryItemGroupKey max length
    group_title = models.CharField(max_length=50, blank=True, null=True)
    #group_image_link = models.CharField(max_length=250, null=True, blank=True)
    #replaced_by = models.ForeignKey('self', blank=False, null=True, on_delete=models.SET_NULL, related_name='replaces')

    @property
    def value(self):
        return sum(p.parent_card.value for p in self.products)

    @property
    def size(self):
        return self.tagged_cards.count()
    
    @classmethod
    def create(cls, name):
        group,created = TagGroup.objects.get_or_create(group_title=name)
        if created:
            group.group_key=str(group.id)
            group.save()
        return group

    def add(self, card):
        card.tag_groups.add(self)

    
    