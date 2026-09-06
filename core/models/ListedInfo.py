from django.db import models
from core.models.Status import StatusBase
from services import ebay
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import datetime

class ListedInfo(models.Model):
    
    #owner relation
    card = models.OneToOneField('core.Card', null=True, blank=True, on_delete=models.CASCADE, related_name="listed_card_info")
    product_group = models.ForeignKey('core.ProductGroup', null=True, blank=True, on_delete=models.CASCADE, related_name="listed_products_info")

    #membership relation 
    #reverse relation from CARD's LI to LI of Product Group card is assigned to
    assigned_product_group = models.ForeignKey('core.ProductGroup', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="as_group_member")

    is_pg = models.BooleanField(default=False)

    listed_sku = models.CharField(max_length=250, blank=True)

    listing_datetime = models.DateTimeField(null=True)
    list_price = models.FloatField(default=0.0)
    total_listing_value = models.FloatField(default=0.0)

    total_qty = models.IntegerField(default=0)
    list_qty = models.IntegerField(default=0)
    avail_qty = models.IntegerField(default=0)
    sold_qty = models .IntegerField(default=0)
    
    listed_price = models.FloatField(default=0.0)
    avail_price = models.FloatField(default=0.0)
    sold_price = models.FloatField(default=0.0)

    listing_id = models.CharField(max_length=250, blank=True)
    #listed_under_sku = models.ForeignKey('self', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="as_lead_sku")
    sku = models.CharField(max_length=250, blank=True)
    offer_id = models.CharField(max_length=250, blank=True, null=True)
    
    msrp = models.FloatField(default=0.0, null=True)
    variation_title_base = models.CharField(max_length=250, blank=True, null=True)
    
    shareable_link_front=models.CharField(max_length=250, null=True, blank=True)
    shareable_link_reverse=models.CharField(max_length=250, null=True, blank=True)

    listing_detail_text = models.TextField(blank=True)
    listing_notes = models.TextField(blank=True) 

    exportedOffer = models.JSONField(default=dict, blank=True)

    modification_date = models.DateTimeField(auto_now=True, null=True)
    
    @classmethod
    def create_from_card(cls, card):
        lci = cls.objects.create(card=card)
        return lci
    
    @classmethod
    def create_from_group(cls, group):
        print(group)
        lci = cls.objects.create(is_pg=True)        
        lci.product_group = group
        print(lci)
        lci.save()
        print(lci, lci.product_group)
        return lci
    
    
    def _secondary_calcs(self):
        print("LI_secondary ", self.id)
        if self.pk and self.listing_statuses.exists():
            self.sold_qty = self.listing_statuses.last().sold_qty
            self.avail_qty = self.listing_statuses.last().available_qty
        else:
            self.sold_qty = 0
            self.avail_qty = self.list_qty
            print(self.list_qty, self.list_price)
        if self.is_pg and self.product_group:
            self.total_qty = self.product_group.total_qty
            self.list_qty = self.product_group.listed_qty
            self.avail_qty = self.product_group.avail_qty
            self.sold_qty = self.product_group.sold_qty
            self.list_price = self.product_group.listed_price
            self.total_listing_value = self.product_group.total_price
            self.listed_price = self.product_group.listed_price
            self.avail_price = self.product_group.avail_price
            self.sold_price = self.product_group.sold_price
        else:   
            #list_price, list_qty set manually
            self.total_qty = self.list_qty
            self.listed_price = int(self.list_qty)*float(self.list_price) or 0.0
            self.avail_price = int(self.avail_qty)*float(self.list_price) or 0.0
            self.sold_price = int(self.sold_qty)*float(self.list_price) or 0.0
            self.total_listing_value = float(self.list_price)
            self.assigned_product_group = self.card.active_search_results.ebay_product_group if self.pk and self.card.active_search_results else None
            
            
    def save(self, *args, **kwargs):
        csr = None
        print("saving LI ", self.id)
        if self.card and self.card.active_search_results:
            csr = self.card.active_search_results
            self.listing_detail_text = csr.title_to_be if csr else ""
            self.card.update_mod_date()
        
        if csr:
            self.msrp = max((round(csr.ebay_msrp + 0.01, 1) - 0.01 if csr and csr.ebay_msrp and csr.ebay_msrp > 0 else -69.69), 0.99)
        if not self.listing_id:
            self.listing_id = ""
        if self.is_pg and hasattr(self, "product_group") and self.product_group:
            self.product_group.save()    
        self._secondary_calcs()
        if not self.sold_price or self.sold_price == '':
            self.sold_price = 0.0
        super().save(*args, **kwargs)
        
    @property
    def last_updated(self):
        if self.is_pg:
            return self.product_group.last_updated
        else:
            return self.listing_start_dt

    @property
    def next_renewal(self):
        """Calculates eBay's actual calendar-month GTC renewal date."""
        if not self.listing_start_dt:
            return None
        
        now = timezone.now()
        renewal = self.listing_start_dt
        
        # Step forward by 1 calendar month at a time until we pass 'now'
        while renewal <= now:
            renewal += relativedelta(months=1)
            
        return renewal

    @property
    def card_count(self):
        if self.is_pg:
            return self.product_group.card_count if self.product_group else 0
        return self.list_qty

    @property
    def listing_status(self):
        if self.is_pg:
            return self.product_group.listing_status if self.product_group else None
        else:
            return self.card.active_search_results.overall_status    
    
    @property
    def listing_str(self):
        if self.is_pg:
            return self.product_group.listing_str if self.product_group else None
        else:
            return self.card.active_search_results.sell_through_rate_total

    @property
    def get_listing_id(self):
        if self.is_pg:
            return self.product_group.listing_id
        else:
            return self.listing_id

    @property
    def listing_end_dt(self):
        if self.is_pg:
            return None
        else:
            return self.listing_statuses.last().sold_date if hasattr(self, "listing_statuses") and self.listing_statuses.exists() else None

    @property
    def listing_start_dt(self):
        
        if self.is_pg:
            return self.product_group.listing_datetime
        else:
            return self.listing_datetime

    @property
    def days_listed(self):
        start = self.listing_start_dt or timezone.now()
        end = self.listing_end_dt or timezone.now()
        return (end - start).days

    def clear(self):
        self.product_group = None
        self.listing_datetime = None
        self.list_qty = 1
        self.listing_id = ""
        self.offer_id = None
        self.save()

    def complete_listing(self, status, csr, task):
        if status is StatusBase.LISTED:
            self.listing_datetime = task.scheduled_for
            #self.product_group = csr.ebay_product_group
            #self.list_qty = task.qty already set
            self.listing_id = csr.ebay_listing_id
            #self.sku = csr.sku
            self.offer_id = csr.ebay_offer_id
    
    def update_from_csr(self, csr):

        #self.product_group = csr.ebay_product_group
        self.listing_detail_text = csr.title_to_be
        if csr.listing_tasks.exists():
            last_task = csr.listing_tasks.latest("scheduled_for")
            if last_task:
                self.listing_datetime = last_task.scheduled_for
        #self.list_price = csr.list_price
        self.list_qty = 1
        self.sku = csr.sku
        
        self.msrp = round(csr.ebay_msrp + 0.01, 1) - 0.01
        #self.variation_title_base = csr.variation_title_base
        
        self.shareable_link_front=csr.shareable_link_front
        self.shareable_link_reverse=csr.shareable_link_reverse
        self.save()

        return self

    def export_to_offer_template(self, template, single_listing):
        if self.list_price == 0:
            self.list_price = self.msrp
        data = template.copy()
        data["sku"] = self.sku
        data["listingDescription"] = self.listing_detail_text
        data["availableQuantity"] = self.list_qty
        data["pricingSummary"]["price"]["value"] = self.list_price 
        data["listingPolicies"]["fulfillmentPolicyId"] = ebay.SHIPPING_POLICY_STANDARD_ENVELOPE if self.list_price <= 20.0 else ebay.SHIPPING_POLICY_USPS_GROUND
        # Apply best offer policies only if item is standalone (not part of a variation group)
        if single_listing:
            listing_policies = data.setdefault("listingPolicies", {})
            best_offer = listing_policies.setdefault("bestOfferTerms", {})
            best_offer["bestOfferEnabled"] = True

        self.exported_offer = data
        self.save()
        return data

    def upload_listing_images(self, front, reverse):

        from services import export
        # Media Asset Upload & SKU Assembly Pipelines
        self.shareable_link_front = export.upload_to_cloudinary(front)
        self.shareable_link_reverse = export.upload_to_cloudinary(reverse)


    def build_sku(self):

        self.sku = self.card.active_search_results.build_sku()

    
    
    def accept_msrp(self):
        print("accept")
        self.list_price = self.msrp
        self.save()
        #self.card.save()

    @property
    def get_sold_price(self):
        last = self.listing_statuses.last()
        return last.sold_value if last else 0