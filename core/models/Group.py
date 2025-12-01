from django.db import models
from collections import defaultdict
from core.models.Utilities import FieldStructure

class ProductGroup(models.Model):
    group_key = models.CharField(max_length=50)#limit tied to inventoryItemGroupKey max length
    group_title = models.CharField(max_length=50, blank=True, null=True)
    group_image_link = models.CharField(max_length=250, null=True, blank=True)

    #variation_title_struct = models.ForeignKey(FieldStructure, related_name="groups", on_delete=models.DO_NOTHING)
  
    variation_data = models.JSONField(default=dict)

    @property
    def size(self):
        return self.products.count()
    
    @classmethod
    def create(cls, group_key, csrs, group_image=None):
        group, created = ProductGroup.objects.get_or_create(group_key=group_key)
        if created:
            group.group_title = group_key
            group.group_image_link = group_image or csrs[0].shareable_link_front

        for csr in csrs:
            csr.ebay_product_group = group
            csr.save()
        
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
    
    def export_to_ebay_variation_group(self):
        
        csrs = list(self.products.all())
        variant_skus = [csr.sku for csr in csrs]
        variation_title_bases = [csr.variation_title_base for csr in csrs]

        # Group SKUs by title
        title_to_skus = defaultdict(list)
        for title, sku in zip(variation_title_bases, variant_skus):
            title_to_skus[title].append(sku)

        # Build map: title → (SKU_suffix, quantity)
        variation_data = {}
        for title, skus in title_to_skus.items():
            variation_data[title] = (skus[0], len(skus))

            image_urls = self.group_image_link if self.group_image_link else csrs[0].shareable_link_front

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


    