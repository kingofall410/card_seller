# services/models.py
from django.db import models
from django.utils import timezone
import json

from core.models.Cropping import CroppedImage
from core.models.Card import Card
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase

class Task(models.Model):
    name = models.CharField(max_length=200)
    scheduled_for = models.DateTimeField()
    callback_path = models.CharField(max_length=300)
    params_json = models.TextField(default="{}")

    predecessor = models.ForeignKey('self', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="next")
    
    status = models.CharField(
        max_length=20,
        default=StatusBase.PENDING,
        choices=StatusBase.choices
    )
    error_str = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def reset(self, new_datetime):
        self.scheduled_for = new_datetime
        self.status = StatusBase.PENDING
        self.save()

    @property
    def img(self):
        return None

    def params(self):
        return json.loads(self.params_json)

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
        return f"{self.name} @ {self.scheduled_for}"


class ListingTask(Task):
    
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='listing_tasks', null=True)
    csr = models.ForeignKey(CardSearchResult, on_delete=models.DO_NOTHING, related_name='listing_tasks', null=True)
    
    def img(self):
        if self.card:
            return self.card.cropped_image.url()

    @property
    def group_key(self):
        return self.params().get('group_key')

class PricingTask(Task):
    
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='pricing_tasks', null=True)
    csr = models.ForeignKey(CardSearchResult, on_delete=models.DO_NOTHING, related_name='_pricing_tasks', null=True)


class UploadTask(Task):
    pass


class IDTask(Task):
    pass
