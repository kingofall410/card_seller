from django.db import models
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase
from services import ebay
from django.utils import timezone

class ListedInfo(models.Model):
    card = models.OneToOneField('core.Card', null=True, blank=True, on_delete=models.CASCADE, related_name="listed_card_info")
    sub_cards = models.ManyToManyField('core.Card', null=True, blank=True, related_name="listed_subcard_info")
    product_group = models.ForeignKey('core.ProductGroup', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="listed_products_info")

    listed_sku = models.CharField(max_length=250, blank=True)

    listing_datetime = models.DateTimeField(null=True)
    list_price = models.FloatField(default=0.0)
    total_listing_value = models.FloatField(default=0.0)

    list_qty = models.IntegerField(default=0)
    avail_qty = models.IntegerField(default=0)
    sold_qty = models.IntegerField(default=0)
    
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
    
    @classmethod
    def create_from_card(cls, card):
        lci = ListedInfo.objects.create(card=card)
        return lci
    
    @property
    def listing_status(self):
        return self.listing_statuses.last().listing_status
    
    @property
    def listing_end_dt(self):
        if self.listing_statuses.last():
            return self.listing_statuses.last().sold_date
        else:
            return timezone.now()

    @property
    def days_listed(self):
        start = self.listing_datetime or timezone.now()
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
            self.product_group = csr.ebay_product_group
            #self.list_qty = task.qty already set
            self.listing_id = csr.ebay_listing_id
            #self.sku = csr.sku
            self.offer_id = csr.ebay_offer_id
    
    def update_from_csr(self, csr):

        self.product_group = csr.ebay_product_group
        self.listing_detail_text = csr.title_to_be
        if csr.listing_tasks.exists():
            last_task = csr.listing_tasks.latest("scheduled_for")
            if last_task:
                self.listing_datetime = last_task.scheduled_for
        #self.list_price = csr.list_price
        self.list_qty = 1
        #self.listing_id = csr.ebay_listing_id
        #lci.listed_under_sku = csr.ebay_listed_under_sku
        self.sku = csr.sku
        #self.offer_id = csr.ebay_offer_id
        
        self.msrp = round(csr.ebay_msrp + 0.01, 1) - 0.01
        #self.variation_title_base = csr.variation_title_base
        
        self.shareable_link_front=csr.shareable_link_front
        self.shareable_link_reverse=csr.shareable_link_reverse
        self.save()

        return self

    @classmethod
    def create_from_csr(cls, csr: CardSearchResult):
        
        lci = ListedInfo.create_from_card(csr.parent_card)
        
        #lci.product_group = csr.ebay_product_group
        lci.listing_detail_text = csr.title_to_be
        if csr.listing_tasks.exists():
            last_task = csr.listing_tasks.latest("scheduled_for")
            if last_task and last_task.status is StatusBase.SUCCESS:
                lci.product_group = csr.ebay_product_group
                lci.listing_datetime = last_task.scheduled_for

        #lci.list_price = csr.list_price if not lci.list_price else 0
        lci.list_qty = 1
        lci.listing_id = csr.ebay_listing_id
        #lci.listed_under_sku = csr.ebay_listed_under_sku
        lci.sku = csr.sku
        lci.offer_id = csr.ebay_offer_id
        
        lci.msrp = round(csr.ebay_msrp + 0.01, 1) - 0.01
        #lci.variation_title_base = csr.variation_title_base
        
        lci.shareable_link_front=csr.shareable_link_front
        lci.shareable_link_reverse=csr.shareable_link_reverse
        lci.save()
        
        return lci

    def export_to_offer_template(self, template, single_listing):
        
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

    def save(self, *args, **kwargs):
        csr = None
        if self.card and self.card.active_search_results:
            csr = self.card.active_search_results
            
            print("saving LI ", self.id, csr.ebay_msrp)
            self.listing_detail_text = csr.title_to_be if csr else ""
            self.card.update_mod_date()

        if csr and self.msrp == 0.0 or self.msrp == -69.69:
            self.msrp = max((round(csr.ebay_msrp + 0.01, 1) - 0.01 if csr and csr.ebay_msrp and csr.ebay_msrp > 0 else -69.69), 0.99)
        if not self.listing_id:
            self.listing_id = ""

        if self.listing_statuses.exists():
            self.sold_qty = self.listing_statuses.last().sold_qty
            self.avail_qty = self.listing_statuses.last().available_qty
        else:
            self.sold_qty = 0
            self.avail_qty = self.list_qty

        self.listed_price = self.list_qty*self.list_price
        self.avail_price = self.avail_qty*self.list_price
        self.sold_price = self.sold_qty*self.list_price

        super().save(*args, **kwargs)
    
    def accept_msrp(self):
        print("accept")
        self.list_price = self.msrp
        self.save()
        #self.card.save()

    @property
    def get_sold_price(self):
        last = self.listing_statuses.last()
        return last.sold_value if last else None