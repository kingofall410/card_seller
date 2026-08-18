import csv
from core.models.CardSearchResult import CardSearchResult
from core.models.ProductGroup import ProductGroup
from core.models.Status import StatusBase
from core.models.ListingStatus import ListingStatus
from django.http import HttpResponse
from services.models.models import Settings
from services.google import GoogleDriveUploader
from services import ebay
from django.shortcuts import get_object_or_404
import requests


def export_csrs_to_csv(csrs):
    """Exports Card objects to CSV and returns a downloadable response."""
    '''legacy
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="card_collection.csv"'

    writer = csv.writer(response)
    writer.writerow(CardSearchResult.listing_fields + CardSearchResult.dynamic_listing_fields)
    
    for csr in csrs:
        writer.writerow(csr.export_to_csv())

    return response'''
    pass


def export_zip(csrs):
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="card_collection.csv"'
    writer = csv.writer(response)
    
    writer.writerow(ebay.singles_excel_fields.keys())
            
    uploader = GoogleDriveUploader()
   
    for csr in csrs:
        shareable_link_front = uploader.upload_and_share(csr.get_latest_front(), csr.title_to_be)
        shareable_link_reverse = uploader.upload_and_share(csr.get_latest_reverse(), csr.title_to_be)
        print("🔗 Public link:", shareable_link_front)
        print("🔗 Public link:", shareable_link_reverse)
        writer.writerow(csr.export_to_csv(ebay.singles_excel_fields) + [shareable_link_front, shareable_link_reverse])

    return response

import cloudinary
import cloudinary.uploader

#TODO:remove
cloudinary.config(
  cloud_name = "dg7c9vsis",
  api_key = "748944422398635",
  api_secret = "3xXqCNYuD3nfzStElFrviXFnioY"
)

def upload_to_cloudinary(image_path, public_id=None, folder=None):
    response = cloudinary.uploader.upload(
        image_path,
        public_id=public_id,
        folder=folder,
        overwrite=True,
        resource_type="image"
    )
    return response["secure_url"]

    response = requests.post(url, headers=headers, json=payload)
    print(response.text)
    response.raise_for_status()
    return response.json()


def test_create_ebay_location():
    settings = Settings.get_default()
    if ebay.has_user_consent(settings):
        access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        ebay.create_location(access_token)

def add_to_variation_group(csrs, access_token, group_key=None, publish=False):
    #TODO:this is stupid just pass the group
    if group_key == "-1":
        group_key = csrs[0].display_full_name + "Dollar Bin"
    elif group_key == "-2":
        group_key = csrs[0].full_set + "Commons"
    
    #find or create django group object
    group = ProductGroup.get_or_create(group_key, csrs)
    if group.replaced_by:
        group = group.replaced_by
    
    inventory_group_data = group.export_to_ebay_variation_group(new_csrs=csrs)
    
    #this sequence is a bit overkill but it supports all types of changes without incurring additional insertion
    listing_id = None
    if ebay.create_inventory_group(group.group_key, inventory_group_data, access_token):
        if publish:
            listing_id = ebay.publish_inventory_group(group.group_key, access_token)
    return listing_id


def clear_inventory_group(group_key):

    group, _ = ProductGroup.get_or_create(group_key=group_key)
    csrs = [csr for csr in group.products.all()]
    inventory_group_data = {
        "aspects": {"Sport": ["Baseball"]},
        "description": "Every card is pictured, please don't hesitate to reach out with questions.", 
        "imageUrls": ["http://www.google.com"],
        "inventoryItemGroupKey": group_key,
        #"subtitle": "",
        "title": group_key,
        "variantSKUs": [],
        "variesBy": {
            "aspectsImageVariesBy": [
                "Card"
            ],
            "specifications": [
            {
                "name": "Card",
                "values": []
            }
            ]
        }
    }
    settings = Settings.get_default()
    access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
    ebay.create_inventory_group(group_key, inventory_group_data, access_token)

from django.shortcuts import get_object_or_404
from django.db import transaction

def export_to_ebay(csr_id=None, csr_ids=None, publish=False, group_key=None):
    """
    Unified Bulk eBay Export Engine with Batch Variation Grouping.
    
    Accepts:
      - csr_ids: A list of integer IDs (e.g., [105, 106, 107])
      
    Returns a dictionary summarizing execution counts and tracking statuses.
    """
    settings = Settings.get_default()
    if not ebay.has_user_consent(settings):
        raise Exception("Missing user consent for eBay Operations")

    results_summary = {
        "success_count": 0,
        "failed_count": 0,
        "details": []
    }

    # Gather successfully prepared CSR objects for a single batch variation upload
    successful_group_csrs = []

    # 1. Fetch the authentication token ONCE for the entire batch lifecycle
    access_token = None
    if publish:
        access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)

    csr_ids = [csr_id] if csr_id else csr_ids
    print(f"Starting eBay export execution targeting {len(csr_ids)} item(s)...")

    # 2. PHASE 1: Process individual items, images, and inventory records
    for csr_id in csr_ids:
        try:
            with transaction.atomic():
                csr = get_object_or_404(CardSearchResult, id=csr_id)
                listed_info = csr.parent_card.listed_card_info

                if listed_info.list_price <= 0:
                    raise Exception("List price not valid")

                listed_info.upload_listing_images(csr.get_latest_front(), csr.get_latest_reverse())
                listed_info.build_sku()                

                # Prepare API Payload Data structures
                item_data = csr.export_to_template(
                    listed_info.sku, 
                    ebay.ebay_item_data_template, 
                    [listed_info.shareable_link_front, listed_info.shareable_link_reverse],
                    group_key
                )
                offer_data = listed_info.export_to_offer_template(ebay.ebay_offer_data_template, (not group_key))

                # If preview/dry-run mode, save assets locally and move to next item
                if not publish:
                    csr.save()
                    listed_info.save()
                    
                    results_summary["success_count"] += 1
                    results_summary["details"].append({
                        "csr_id": csr_id,
                        "status": "DRAFT_SAVED",
                        "offer_id": None,
                        "listing_id": None
                    })
                    print(f"📁 Saved local draft for CSR ID {csr_id} (Publish=False)")
                    continue

                # Create the item and offer on eBay
                if ebay.create_inventory_item(listed_info.sku, item_data, access_token):
                    print("Offer data: ", offer_data)
                    offer_id, status = ebay.get_or_create_offer(offer_data, access_token, listed_info.sku)
                    
                    if status == 201:
                        listed_info.offer_id = offer_id
                    else:
                        listed_info.listing_id = ""

                    # Branch logic handling: Single standalone items publish immediately
                    if not group_key or group_key == "-1":
                        listed_info.listing_id = ebay.publish_offer(offer_id, access_token)
                        if listed_info.listing_id is None:
                            raise Exception("eBay offer failed to publish.")
                        
                        ListingStatus.create(listed_info, listed_info.list_qty, StatusBase.LISTED, 0, True)
                        results_summary["success_count"] += 1
                        results_summary["details"].append({
                            "csr_id": csr_id,
                            "status": "PUBLISHED",
                            "offer_id": listed_info.offer_id,
                            "listing_id": listed_info.listing_id
                        })
                        print(f"✅ Successfully published standalone CSR ID {csr_id} to eBay")
                    
                    else:
                        # Hold this validated item back for the final batch variation grouping call
                        successful_group_csrs.append(csr)
                        print(f"📦 Staged CSR ID {csr_id} for batch group listing processing")

                    # Persist synchronized updates back to local db
                    csr.save()
                    listed_info.save()
                    
                else:
                    # Fallback recovery strategy matching your original blueprint rules
                    ebay.get_inventory_group(group_key, settings, access_token)
                    results_summary["success_count"] += 1

        except Exception as e:
            results_summary["failed_count"] += 1
            results_summary["details"].append({
                "csr_id": csr_id,
                "status": "FAILED",
                "error": str(e)
            })
            print(f"❌ Failed to process CSR ID {csr_id}: {str(e)}")

    # 3. PHASE 2: Handle batch variation grouping all at once
    if publish and group_key and group_key != "-1" and successful_group_csrs:
        print(f"🔗 Combining {len(successful_group_csrs)} items into eBay Variation Group: {group_key}...")
        try:
            # Send the entire batch list together in one API call
            batch_listing_id = add_to_variation_group(
                successful_group_csrs, 
                access_token, 
                group_key=group_key, 
                publish=publish
            )
            #add_to_variation_group will throw exception if it fails, thus we can assume success here
    
            # Update all local database objects with the single returned group listing ID
            with transaction.atomic():
                for csr in successful_group_csrs:
                    listed_info = csr.parent_card.listed_card_info
                    listed_info.listing_id = batch_listing_id
                    
                    csr.save()
                    listed_info.save()
                    ListingStatus.create(listed_info, listed_info.list_qty, StatusBase.LISTED, 0, True)

                    results_summary["success_count"] += 1
                    results_summary["details"].append({
                        "csr_id": csr.id,
                        "status": "GROUP_PUBLISHED",
                        "offer_id": listed_info.offer_id,
                        "listing_id": batch_listing_id
                    })
            print(f"🚀 Batch grouping complete! eBay Listing ID: {batch_listing_id}")
            
        except Exception as e:
            print(f"❌ Critical failure publishing batch variation group: {str(e)}")
            # Log individual failures for the items that were in the group batch
            for csr in successful_group_csrs:
                results_summary["failed_count"] += 1
                results_summary["details"].append({
                    "csr_id": csr.id,
                    "status": "GROUP_FAILED",
                    "error": f"Group packaging crash: {str(e)}"
                })

    print(f"Export execution run finished. Success: {results_summary['success_count']} | Failed: {results_summary['failed_count']}")
    return results_summary