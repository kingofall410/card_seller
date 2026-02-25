import csv
from core.models.CardSearchResult import CardSearchResult
from core.models.Group import ProductGroup
from django.http import HttpResponse
from services import ebay
from services.models.models import Settings
from services.google import GoogleDriveUploader
from django.shortcuts import get_object_or_404
import requests


def export_csrs_to_csv(csrs):
    """Exports Card objects to CSV and returns a downloadable response."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="card_collection.csv"'

    writer = csv.writer(response)
    writer.writerow(CardSearchResult.listing_fields + CardSearchResult.dynamic_listing_fields)
    
    for csr in csrs:
        writer.writerow(csr.export_to_csv())

    return response


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
    group = ProductGroup.create(group_key, csrs)
    
    inventory_group_data = group.export_to_ebay_variation_group(csrs=csrs)
    
    if ebay.create_inventory_group(group.group_key, inventory_group_data, access_token):
        if publish:
            listing_id = ebay.publish_inventory_group(group.group_key, access_token)
    return listing_id


def clear_inventory_group(group_key):

    group, _ = ProductGroup.objects.get_or_create(group_key=group_key)
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

#TODO: This whole process is cobbled together.  needs to be fixed
def export_to_ebay(csr_id, publish=False, group_key=None):
    
    print("ebay export ", csr_id, publish, group_key)

    settings = Settings.get_default()
    #uploader = GoogleDriveUploader()
    if ebay.has_user_consent(settings):

        csr = get_object_or_404(CardSearchResult, id=csr_id)
        listed_info = csr.parent_card.listed_card_info
        #TODO: update these methods to check before creating new?
        listed_info.shareable_link_front = upload_to_cloudinary(csr.get_latest_front())
        listed_info.shareable_link_reverse = upload_to_cloudinary(csr.get_latest_reverse())

        #also upload to google drive
        #uploader = GoogleDriveUploader()
        #uploader.upload_and_share(csr.get_latest_front(), csr.display_full_name)
        #uploader.upload_and_share(csr.get_latest_reverse(), csr.display_full_name)
        #print("am i here", csr.sku)
        listed_info.sku = csr.build_sku()
        #print("am i here", csr.sku)
        print("SKU:", listed_info.sku)
        print("🔗 Public link:", listed_info.shareable_link_front)
        print("🔗 Public link:", listed_info.shareable_link_reverse)

        print(listed_info.list_price)

        item_data = None
        if group_key:
            group = ProductGroup.create(group_key, [csr])
            print(csr.variation_title_base)
            print(group.variation_data)
            #print("single row:", group.variation_data[csr.variation_title_base])
            if False:#csr.variation_title_base in group.variation_data:
                #This is a full dup of something already listed under a diff sku in this group, add 1 to that item instead of creating a new item
                group.variation_data[csr.variation_title_base][1] += 1
                group.save()
                #print("single row:", group.variation_data[csr.variation_title_base])
                csr_for_sku = group.products.get(sku=group.variation_data[csr.variation_title_base][0])
                update_data = group.export_to_qty_update(csr_for_sku, group.variation_data[csr.variation_title_base][1])
                
                access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
                if ebay.update_inventory_item_qty(update_data, access_token):
                    #link to main sku
                    csr.ebay_listed_under_sku = csr_for_sku
                    csr.save()
                    #item was updated successfully
                    return True, csr_for_sku.ebay_offer_id, csr_for_sku.ebay_listing_id
            
        print("new item")
        #if we didn't fill item data above, this needs a new inv item and offer    
        item_data = csr.export_to_template(listed_info.sku, ebay.ebay_item_data_template, [listed_info.shareable_link_front, listed_info.shareable_link_reverse])
        print("Item data:", item_data)

        offer_data = {
            "sku": listed_info.sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "listingDescription": listed_info.listing_detail_text,
            "availableQuantity": listed_info.list_qty,
            "pricingSummary": {
                "price": {
                "value": listed_info.list_price,
                "currency": "USD"
                }
            },
            "condition": 4000,
            "categoryId": ebay.CATEGORY_ID,
            #"conditionId":4000,
            #"storeCategoryId": "",
            "listingPolicies": {    
                "bestOfferTerms": {
                    "bestOfferEnabled": "true"
                },
                "fulfillmentPolicyId": ebay.SHIPPING_POLICY_STANDARD_ENVELOPE if listed_info.list_price <= 20.0 else ebay.SHIPPING_POLICY_USPS_GROUND,
                "paymentPolicyId": ebay.PAYMENT_POLICY_EBAY_MANAGED,
                "returnPolicyId": ebay.RETURN_POLICY_NO_RETURNS
            },
            "merchantLocationKey": "Freeport"

        }
        #print(csr.list_price)
        print("Offer data:", offer_data)
        
        if listed_info.list_price <= 0:
            raise Exception("List price not valid")
        elif not publish:
            return True, None, None#don't talk to ebay if we're not publishing
        
        access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        #csr.check_category_metadata("261328",access_token)
        if ebay.create_inventory_item(listed_info.sku, item_data, access_token):
            #item was created successfully
            #print("checkinv: ", csr.check_inventory_item_exists(sku, access_token))
            offer_id, status = ebay.get_or_create_offer(offer_data, access_token, listed_info.sku)
            print(offer_id, status, publish)
            if status == 201:
                #csr.ebay_listing_id = ebay.publish_offer(offer_id, access_token)
                listed_info.ebay_offer_id = offer_id
            else:
                #"Error response from ebay"
                listed_info.ebay_listing_id = ""
            
            if group_key:
                listed_info.ebay_listing_id = add_to_variation_group([csr], access_token, group_key=group_key, publish=publish)
            elif publish:
                listed_info.ebay_listing_id = ebay.publish_offer(offer_id, access_token)

            csr.save()
            listed_info.save()
        else:
            ebay.get_inventory_group(group_key, settings, access_token)

        return True, listed_info.ebay_offer_id, listed_info.ebay_listing_id
    
        #print("asking for token ")
        #access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        #print(access_token)
        #ebay.publish_offer("66119568011", access_token)

    else:
        raise Exception("Missing user consent")


''''
#TODO: These are "working" upload functions but the sites themselves are broken at this time
eventually we want to loop this into a configurable upload location
POSTIMAGE_API_KEY = "375d65b31ef5453eb9652cc870e769e9"
IMAGEBB_API_KEY = "18d2d0172a59b3f8e7134eea7dcd2bb3"

def upload_to_postimage(image):
    url = "https://api.postimage.org/1/upload"
    files = {"file":open(image, "rb")}
    data = {
        "key": POSTIMAGE_API_KEY,
        "expire": "0",  # 0 = never expire
        "adult": "0"    # 0 = safe content
    }
    response = requests.post(url, files=files, data=data)
    print(response.text)
    response.raise_for_status()
    return response.json().get("url")


def upload_to_imageBB(image):
    url = "https://api.imgbb.com/1/upload"
    with open(image, "rb") as file:
        encoded_image = base64.b64encode(file.read()).decode("utf-8")

    with open(image, "rb") as file:
        payload = {
            "key": IMAGEBB_API_KEY,
            "image": encoded_image
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return response.json()["data"]["url"]'''
