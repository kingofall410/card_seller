from django.db import models
from django.db.models import Q
from collections import defaultdict
from core.models.Utilities import FieldStructure
from core.models.Status import StatusBase
from core.models.ListedInfo import ListedInfo
from datetime import timedelta
from django.utils import timezone

class TitleFormat(models.TextChoices):
    
    PLAYER_GROUP = "player group", "Player Group"
    SET_GROUP = "set group", "Set Group"
    TEAM_GROUP = "team group", "Team Group"
    MISC_GROUP = "misc group", "Misc Group"

class ProductGroup(models.Model):
    creation_dt = models.DateTimeField(auto_now_add=True)
    modified_dt = models.DateTimeField(auto_now=True)

    group_key = models.CharField(max_length=50)#limit tied to inventoryItemGroupKey max length
    group_title = models.CharField(max_length=50, blank=True, null=True)
    group_image_link = models.CharField(max_length=250, null=True, blank=True)
    replaced_by = models.ForeignKey('self', blank=False, null=True, on_delete=models.SET_NULL, related_name='replaces')

    card_count = models.IntegerField(default=0)

    listing_id = models.CharField(max_length=100, blank=True, null=True)
    total_qty = models.IntegerField(default=0)
    listed_qty = models.IntegerField(default=0)
    staged_qty = models.IntegerField(default=0)
    avail_qty = models.IntegerField(default=0)
    sold_qty = models.IntegerField(default=0)
   
    total_price = models.FloatField(default=0.0)
    listed_price = models.FloatField(default=0.0)
    staged_price = models.FloatField(default=0.0)
    avail_price = models.FloatField(default=0.0)
    sold_price = models.FloatField(default=0.0)

    listing_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.IMPORTED)
    listing_datetime = models.DateTimeField(null=True)
    last_updated = models.DateTimeField(null=True)
    skus = models.TextField(blank=True, null=True)
    listing_str = models.FloatField(default=0.0)

    title_format = models.CharField(max_length=20, choices=TitleFormat.choices, default=TitleFormat.MISC_GROUP)
    player_group_title = ["year","brand","subset","card_name","parallel","card_number","city","team"]
    set_group_title = ["card_number", "full_name", "card_name","parallel","city","team","condition"]
    team_group_title = ["full_name","year","brand","subset","card_name","parallel","card_number","city","team"]
    misc_group_title = ["full_name","year","brand","subset","card_name","parallel","card_number","city","team"]

    @property
    def _calc_listing_str(self):
        if self.card_count > 0:    
            return sum(csr.sell_through_rate_total for csr in self.products.all() if hasattr(csr.parent_card, 'listed_card_info'))/self.card_count
        else:
            return 0

    def set_title_for_group(self, csr, limit=65):
        values = []
        #This isn't our first try, don't fuck with the variation title; this assumes the same group as last time
        if csr.variation_title_base and (len(csr.variation_title_base) <= limit) and csr.overall_status in [StatusBase.CONFIRMED, StatusBase.LISTED]:
            print("EXISTING csr.variation_title_base", csr.variation_title_base)
            return csr.variation_title_base
            
        title_format_details = self.misc_group_title
        if self.title_format == TitleFormat.SET_GROUP:
            title_format_details = self.set_group_title
        elif self.title_format == TitleFormat.PLAYER_GROUP:
            title_format_details = self.player_group_title
        elif self.title_format == TitleFormat.TEAM_GROUP:
            title_format_details = self.team_group_title
        #print(title_format_details)
        for term in title_format_details:
            if hasattr(csr, term):
                value = getattr(csr, "display_"+term)
                if value:
                    values.append(value)
                    
        values.append("("+str(csr.id)+")")
        print("values", values)
        fart = " ".join([x.strip() for x in values])[:limit]
        csr.variation_title_base = fart
        csr.save()
        print("NEW csr.variation_title_base", fart, csr.variation_title_base)
        return csr.variation_title_base

    def _calculate_summary_attribs(self):
        print("PG_secondary _csa", self.id)
        product_list = list(self.products.all()) if self.pk else []
        
        self.card_count = len(product_list)

        self.total_qty = sum(csr.parent_card.listed_card_info.list_qty for csr in product_list if hasattr(csr.parent_card, 'listed_card_info'))
        self.listed_qty = sum(csr.parent_card.listed_card_info.list_qty for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.LISTED,StatusBase.CONFIRMED])
        self.staged_qty = sum(csr.parent_card.listed_card_info.list_qty for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.STAGED])
        self.avail_qty = sum(csr.parent_card.listed_card_info.avail_qty for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.LISTED,StatusBase.CONFIRMED])
        self.sold_qty = sum(csr.parent_card.listed_card_info.sold_qty for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.SOLD])

        self.total_price = sum(csr.parent_card.listed_card_info.total_listing_value for csr in product_list if hasattr(csr.parent_card, 'listed_card_info'))
        self.listed_price = sum(csr.parent_card.listed_card_info.list_price for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.LISTED,StatusBase.CONFIRMED])
        self.staged_price = sum(csr.parent_card.listed_card_info.list_price for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.STAGED])
        self.avail_price = sum(csr.parent_card.listed_card_info.avail_price for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.LISTED,StatusBase.CONFIRMED])
        self.sold_price = sum(csr.parent_card.listed_card_info.sold_price for csr in product_list if hasattr(csr.parent_card, 'listed_card_info') if csr.overall_status in [StatusBase.SOLD])

        #self.listing_status = 
        self.listing_datetime = None
        if self.pk:
        
            if self.products.exists():
                #print("FU", self.id, self.products, self.products.order_by("parent_card__listed_card_info__listing_datetime").first().parent_card.listed_card_info.listing_datetime)
                self.listing_datetime = self.products.order_by("parent_card__listed_card_info__listing_datetime").first().parent_card.listed_card_info.listing_datetime
                listing_dates = [p.parent_card.listed_card_info.listing_start_dt for p in self.products.all() if p.overall_status in [StatusBase.LISTED, StatusBase.CONFIRMED] and p.parent_card.listed_card_info.listing_start_dt]
                self.last_updated = max(listing_dates) if listing_dates else None

            self.skus = ";".join(p.parent_card.listed_card_info.sku for p in self.products.all() if p.overall_status in [StatusBase.LISTED, StatusBase.CONFIRMED])
            self.listing_str = self._calc_listing_str
        print("_csa", self.card_count)

    def save(self, *args, **kwargs):
        
        print("saving PG ", self.id)
        self._calculate_summary_attribs()
        super().save(*args, **kwargs)

    def listed_value(self):
        return sum(p.parent_card.listed_card_info.list_price for p in self.products.all() if p.overall_status in [StatusBase.LISTED, StatusBase.CONFIRMED])

  
    variation_data = models.JSONField(default=dict)

    @property
    def next_listing_datetime(self):
        
        # Retrieve the last CSR based on the listing date
        ocsr_list = self.products.exclude(parent_card__listed_card_info__listing_datetime__isnull=True).order_by('parent_card__listed_card_info__listing_datetime')
        
        last_csr = ocsr_list.last()
        
        if last_csr and last_csr.parent_card and last_csr.parent_card.listed_card_info:
            last_lci = last_csr.parent_card.listed_card_info
            if last_lci.listing_datetime:

                # Use timedelta to add 1 day to the existing datetime
                return max(timezone.now(), (last_csr.parent_card.listed_card_info.listing_datetime + timedelta(days=1)))
            else:
                return max(timezone.now(), (last_csr.listing_tasks.last().scheduled_for + timedelta(days=1)))
        
        # Return current time if no previous listing exists
        return timezone.now()


    @property
    def size(self):
        return self.products.count()
    
    @classmethod
    def get_or_create(cls, group_key, csrs, group_image=None):
        group, created = ProductGroup.objects.get_or_create(group_key=group_key)
        if created:
            group.group_title = group_key
            group.group_image_link = group_image or csrs[0].shareable_link_front
            listed_products_info = ListedInfo.create_from_group(group)

        for csr in csrs:
            csr.ebay_product_group = group
            csr.save()
        
        group.save()
        return group

    #below is used to create from UI
    @classmethod
    def create(cls, name, tf):
        group = ProductGroup.objects.create(group_title=name, title_format=tf)
        ListedInfo.create_from_group(group)
        group.group_key=str(group.id)
        group.save()
        return group

    def export_to_qty_update(self, csr, qty):
        
        update_qty_payload = {
            "requests": [
                {
                    "offers": [
                    {
                        "availableQuantity": qty,
                        "offerId": csr.ebay_offer_id,
                        "price": {
                            "currency": "USD",
                            "value": csr.list_price
                        }
                    }
                    ],
                    "shipToLocationAvailability": {
                        "availabilityDistributions": [
                            {
                            "merchantLocationKey": "EBAY_US",
                            "quantity": qty
                            }
                        ],
                    "quantity": qty
                    },
                    "sku": csr.sku
                }
                ]
        }

        return update_qty_payload
    
    def add_to_product_group_internal(self, new_csr):
        new_csr.ebay_product_group = self
        new_csr.save(update_fields=["ebay_product_group"])

    def export_to_ebay_variation_group(self, new_csrs):
        
        #if the group has been replaced since this card was staged, move it to the replacement group
        if self.replaced_by:
            print(f"Group {self.group_key} has been replaced by {self.replaced_by.group_key}, moving CSRs to new group")
            for csr in new_csrs:
                self.replaced_by.add_to_product_group_internal(csr)
            self.replaced_by.save()
            return self.replaced_by.export_to_ebay_variation_group(new_csrs)
        
        csrs = new_csrs + list(self.products.filter(Q(overall_status=StatusBase.LISTED) | Q(overall_status=StatusBase.SOLD) | Q(overall_status=StatusBase.CONFIRMED)))
        print(f"Adding {len(new_csrs)} new csrs to '{self.group_title}' total size to be: {len(csrs)}")
        sorted_csrs = sorted(csrs, key=lambda x: x.title_to_be)
        
        variant_skus = []
        variation_title_bases = []
        seen_titles = {}

        for csr in sorted_csrs:
            if not csr.parent_card.listed_card_info.sku:
                continue
            
            sku = csr.parent_card.listed_card_info.sku
            base_title = self.set_title_for_group(csr)
            
            # Append csr.id if title has already been seen to prevent duplicate variation errors
            if base_title in seen_titles:
                seen_titles[base_title] += 1
                final_title = f"{base_title} ({csr.id})"
            else:
                seen_titles[base_title] = 1
                final_title = base_title
                
            variant_skus.append(sku)
            variation_title_bases.append(final_title)

        image_urls = self.group_image_link if self.group_image_link else csrs[0].parent_card.listed_card_info.shareable_link_front

        inventory_group_data = {
            "aspects": {"Sport": ["Baseball"]},
            "description": "Every card is pictured, please don't hesitate to reach out with questions.", 
            "imageUrls": [image_urls],
            "inventoryItemGroupKey": self.group_key,
            #"subtitle": "",
            "title": self.group_title,
            "variantSKUs": variant_skus,
            "variesBy": {
                "aspectsImageVariesBy": [
                    "Card"
                ],
                "specifications": [
                {
                    "name": "Card",
                    "values": variation_title_bases
                }
                ]
            }
        }
        
        #self.variation_data = variation_data
        self.save()
        return inventory_group_data


    