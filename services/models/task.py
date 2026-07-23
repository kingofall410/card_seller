# services/models.py
from django.db import models
from django.utils import timezone
import json
from core.models.Cropping import CroppedImage

from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase

class Task(models.Model):
    title = models.CharField(max_length=200)
    scheduled_for = models.DateTimeField(null=True)
    executed_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True) 
    callback_path = models.CharField(max_length=300)
    params_json = models.TextField(default="{}")
    priority = models.IntegerField(default=0)

    predecessor = models.ForeignKey('self', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="successors")
    
    status = models.CharField(max_length=20, default=StatusBase.PENDING, choices=StatusBase.choices)
    on_success_status = models.CharField(max_length=20, default=StatusBase.SUCCESS, choices=StatusBase.choices)
    error_str = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


    @property
    def group_key(self):
        if hasattr(self, 'listingtask') and self.listingtask:
            return self.listingtask.group_key
        elif self.successors:
            return self.successors.first().group_key

        return ""

    @property
    def get_csr_id(self):
        if hasattr(self, 'listingtask') and self.listingtask:
            return self.listingtask.csr.id
        elif self.successors:
            return [t.listingtask.csr.id for t in self.successors.all()]


    def reset(self, new_datetime):
        self.scheduled_for = new_datetime
        self.status = StatusBase.PENDING
        self.save()

    @property
    def img(self):
        return None

    def params(self):
        return json.loads(self.params_json)

    def update_params(self, field_name, field_value):
        params = self.params()
        params[field_name] = field_value
        self.params_json = json.dumps(params)
        self.save()

    @property
    def status_meta(self):
        return StatusBase.get_meta(self.status)

    @property
    def status_icon(self):
        return self.status_meta["icon"]

    @property
    def status_color(self):
        return self.status_meta["color"]

    def __str__(self):
        return f"{self.title} @ {self.scheduled_for}"

class BulkListingTask(Task):
    value = models.FloatField(default=0.0)

    @property
    def succ_status(self):
        retval = self.status
        if self.successors.filter(status=StatusBase.FAILED).exists():
            return StatusBase.FAILED
        else:
            return retval


    @property
    def group_key(self):
        return self.successors.first().group_key

class ListingTask(Task):
    
    card = models.ForeignKey('core.Card', on_delete=models.CASCADE, related_name='listing_tasks', null=True)
    csr = models.ForeignKey(CardSearchResult, on_delete=models.DO_NOTHING, related_name='listing_tasks', null=True)    

    @property
    def group_key(self):
        return self.params().get('group_key')


class PricingTask(Task):
    
    card = models.ForeignKey('core.Card', on_delete=models.CASCADE, related_name='pricing_tasks', null=True)
    csr = models.ForeignKey(CardSearchResult, on_delete=models.DO_NOTHING, related_name='pricing_tasks', null=True)


class UploadTask(Task):
    pass


class IDTask(Task):

    card = models.ForeignKey('core.Card', on_delete=models.CASCADE, related_name='id_tasks', null=True)

    
class ConfirmTask(Task):

    card = models.ForeignKey('core.Card', on_delete=models.CASCADE, related_name='confirm_tasks', null=True)
