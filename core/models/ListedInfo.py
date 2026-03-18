from django.db import models
from core.models.CardSearchResult import CardSearchResult
from core.models.Group import ProductGroup
from core.models.Status import StatusBase

class ListedInfo(models.Model):
    card = models.OneToOneField('Card', null=True, blank=True, on_delete=models.CASCADE, related_name="listed_card_info")
    sub_cards = models.ManyToManyField('Card', null=True, blank=True, related_name="listed_subcard_info")
    product_group = models.ForeignKey(ProductGroup, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="listed_products_info")

    listing_datetime = models.DateTimeField(null=True)
    list_price = models.FloatField(default=0.0)
    list_qty = models.IntegerField(default=0)

    listing_id = models.CharField(max_length=50, blank=True)
    #listed_under_sku = models.ForeignKey('self', null=True, blank=True, on_delete=models.DO_NOTHING, related_name="as_lead_sku")
    sku = models.CharField(max_length=50, blank=True)
    offer_id = models.CharField(max_length=50, blank=True, null=True)
    
    msrp = models.FloatField(default=0.0, null=True)
    variation_title_base = models.CharField(max_length=50, blank=True, null=True)
    
    shareable_link_front=models.CharField(max_length=250, null=True, blank=True)
    shareable_link_reverse=models.CharField(max_length=250, null=True, blank=True)

    listing_detail_text = models.TextField(blank=True)
    listing_notes = models.TextField(blank=True) 
    
    @classmethod
    def create_from_card(cls, card):
        lci = ListedInfo.objects.create(card=card)
        return lci

        
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
        self.list_price = csr.list_price
        self.list_qty = 1
        self.listing_id = csr.ebay_listing_id
        #lci.listed_under_sku = csr.ebay_listed_under_sku
        self.sku = csr.sku
        self.offer_id = csr.ebay_offer_id
        
        self.msrp = csr.ebay_msrp        
        self.variation_title_base = csr.variation_title_base
        
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

        lci.list_price = csr.list_price
        lci.list_qty = 1
        lci.listing_id = csr.ebay_listing_id
        #lci.listed_under_sku = csr.ebay_listed_under_sku
        lci.sku = csr.sku
        lci.offer_id = csr.ebay_offer_id
        
        lci.msrp = csr.ebay_msrp        
        lci.variation_title_base = csr.variation_title_base
        
        lci.shareable_link_front=csr.shareable_link_front
        lci.shareable_link_reverse=csr.shareable_link_reverse
        lci.save()

        return lci

    def save(self, *args, **kwargs):
        csr = self.card.active_search_results()
        self.listing_detail_text = csr.title_to_be if csr else ""
        super().save(*args, **kwargs)