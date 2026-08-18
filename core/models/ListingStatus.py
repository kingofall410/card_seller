from django.db import models
from core.models.Status import StatusBase
from core.models.ListingSpread import ListingSpread

class ListingStatus(models.Model):
    listing_info = models.ForeignKey('core.ListedInfo', on_delete=models.CASCADE, related_name='listing_statuses')

    listing_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.LISTED)
    is_published = models.BooleanField(default=True)
    sold_qty = models.IntegerField(default=0)
    sold_value = models.FloatField(default=0)
    sold_date = models.DateTimeField(null=True)
    available_qty = models.IntegerField(default=0)
    create_date = models.DateTimeField(auto_now_add=True)
    create_sku = models.CharField(max_length=100, blank=True)
    
    @classmethod
    #created upon request being made, not before
    def create(cls, listed_info, avail_qty, status, sold_qty, published, create_sku=None, sold_price=0):
        print("create", create_sku)
        if create_sku:
            listed_info.listed_sku = create_sku
            listed_info.save()
        return cls.objects.create(listing_info=listed_info, available_qty=avail_qty, listing_status=status, sold_qty=sold_qty, is_published=published, create_sku=create_sku or listed_info.sku, sold_value=sold_price or listed_info.list_price)


    def save(self, *args, **kwargs):
        # 1. Check if create_sku is empty and listing_info exists
        if not self.create_sku and self.listing_info and hasattr(self.listing_info, 'sku'):
            self.create_sku = self.listing_info.sku
            
        # 2. Call the actual save method
        super().save(*args, **kwargs)