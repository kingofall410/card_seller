from django.db import models
from django.db.models import Q
from collections import defaultdict
from core.models.Utilities import FieldStructure
from core.models.Status import StatusBase
from datetime import timedelta
from django.utils import timezone

class ProductGroup(models.Model):
    group_key = models.CharField(max_length=50)#limit tied to inventoryItemGroupKey max length
    group_title = models.CharField(max_length=50, blank=True, null=True)
    group_image_link = models.CharField(max_length=250, null=True, blank=True)
    replaced_by = models.ForeignKey('self', blank=False, null=True, on_delete=models.SET_NULL, related_name='replaces')

    @property
    def value(self):
        return sum(p.parent_card.value for p in self.products)

    #variation_title_struct = models.ForeignKey(FieldStructure, related_name="groups", on_delete=models.DO_NOTHING)
  
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

        for csr in csrs:
            csr.ebay_product_group = group
            csr.save()
        
        group.save()
        return group

    @classmethod
    def create(cls, name):
        group = ProductGroup.objects.create(group_title=name)
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
        
        variant_skus = [(csr.parent_card.listed_card_info.sku) for csr in sorted_csrs if csr.parent_card.listed_card_info.sku]
        variation_title_bases = [csr.variation_title_base for csr in sorted_csrs if csr.parent_card.listed_card_info.sku]

        # Group SKUs by title
        title_to_skus = defaultdict(list)
        for title, sku in zip(variation_title_bases, variant_skus):
            title_to_skus[title].append(sku)

        # Build map: title → (SKU_suffix, quantity)
        variation_data = {}
        for title, skus in title_to_skus.items():
            variation_data[title] = (skus[0], len(skus))

        image_urls = self.group_image_link if self.group_image_link else csrs[0].parent_card.listed_card_info.shareable_link_front

        inventory_group_data = {
            "aspects": {"Sport": ["Baseball"]},
            "description": "Every card is pictured, please don't hesitate to reach out with questions.", 
            "imageUrls": [image_urls],
            "inventoryItemGroupKey": self.group_key,
            #"subtitle": "",
            "title": self.group_title,
            "variantSKUs": [sku for sku, _ in variation_data.values()],
            "variesBy": {
                "aspectsImageVariesBy": [
                    "Card"
                ],
                "specifications": [
                {
                    "name": "Card",
                    "values": sorted(variation_data.keys())
                }
                ]
            }
        }
        self.variation_data = variation_data
        self.save()
        return inventory_group_data


    