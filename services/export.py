import csv, io
from core.models.CardSearchResult import CardSearchResult, ProductGroup
from core.models import Status
from django.http import HttpResponse
import zipfile
from services import ebay
from services.models import Settings
from services.google import GoogleDriveUploader
import requests
import base64


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
    group, _ = ProductGroup.objects.get_or_create(group_key=group_key)
    group_title = group.group_title or group_key
    
    for csr in csrs:
        csr.ebay_product_group = group
        csr.save()

    listing_id = None
    
    csrs = [csr for csr in group.products.all()]
    variant_skus = [csr.sku for csr in csrs]
    #TODO:every card that was ever part of the group needs to remain valid as a variant for now
    variant_card_titles = [csr.variation_title for csr in csrs] + ['1990 Topps Kay Bee #29', '1980 O-Pee-Chee #205,' '1988 Topps Tiffany #400 NM',   '1988 Topps Tiffany #400 NM', '1988 Topps Tiffany #400 NM+']
    
    inventory_group_data = {
        "aspects": {"Sport": ["Baseball"]},
        "description": "Every card is pictured, please don't hesitate to reach out with questions.", 
        "imageUrls": [csrs[0].shareable_link_front],
        "inventoryItemGroupKey": group.group_key,
        #"subtitle": "",
        "title": group_title,
        "variantSKUs": variant_skus,
        "variesBy": {
            "aspectsImageVariesBy": [
                "Card"
            ],
            "specifications": [
            {
                "name": "Card",
                "values": variant_card_titles
            }
            ]
        }
    }
    
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
def export_to_ebay(csrs, publish=False, group_key=None):
    
    print("ebay export ", group_key)
    settings = Settings.get_default()
    #uploader = GoogleDriveUploader()
    if ebay.has_user_consent(settings):

        csr = csrs[0]
        #shareable_link_front = uploader.upload_and_share(csr.get_latest_front(), csr.title_to_be)
        #shareable_link_reverse = uploader.upload_and_share(csr.get_latest_reverse(), csr.title_to_be)
        #TODO:abstract away google vs imagur vs postimage etc
        #print("here i am", csr.sku)
        csr.shareable_link_front = upload_to_cloudinary(csr.get_latest_front())
        csr.shareable_link_reverse = upload_to_cloudinary(csr.get_latest_reverse())
        #print("am i here", csr.sku)
        csr.sku = csr.build_sku()
        #print("am i here", csr.sku)
        print("SKU:", csr.sku)
        print("🔗 Public link:", csr.shareable_link_front)
        print("🔗 Public link:", csr.shareable_link_reverse)

        print(csr.list_price)
        item_data = csr.export_to_template(csr.sku, ebay.ebay_item_data_template, [csr.shareable_link_front, csr.shareable_link_reverse])
        print(item_data)
        offer_data = {
            "sku": csr.sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "listingDescription": csr.parent_card.listing_details,
            "availableQuantity": 1,
            "pricingSummary": {
                "price": {
                "value": csr.list_price,
                "currency": "USD"
                }
            },
            "condition": 4000,
            "categoryId": ebay.CATEGORY_ID,
            #"conditionId":4000,
            #"storeCategoryId": "",
            "listingPolicies": {
                "fulfillmentPolicyId": ebay.SHIPPING_POLICY_STANDARD_ENVELOPE if csr.list_price <= 20.0 else ebay.SHIPPING_POLICY_USPS_GROUND,
                "paymentPolicyId": ebay.PAYMENT_POLICY_EBAY_MANAGED,
                "returnPolicyId": ebay.RETURN_POLICY_NO_RETURNS
            },
            "merchantLocationKey": "Freeport"

        }
        #print(csr.list_price)
        print("Offer data:", offer_data)
        if csr.list_price <= 0:
            return False, None, None#kick out before corrupting the group with a 0 price offer
        
        access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        #create_ebay_location(access_token)
        #csr.check_category_metadata("261328",access_token)
        if ebay.create_inventory_item(csr.sku, item_data, access_token):
            #item was created successfully
            #print("checkinv: ", csr.check_inventory_item_exists(sku, access_token))
            offer_id, status = ebay.get_or_create_offer(offer_data, access_token, csr.sku)
            print(offer_id, status, publish)
            if status == 201:
                #csr.ebay_listing_id = ebay.publish_offer(offer_id, access_token)
                csr.ebay_offer_id = offer_id
            else:
                "Error response from ebay"
                csr.ebay_listing_id = ""
            
            if group_key:
                csr.ebay_listing_id = add_to_variation_group([csr], access_token, group_key=group_key, publish=publish)
            elif publish:
                csr.ebay_listing_id = ebay.publish_offer(offer_id, access_token)

            csr.save()
        else:
            ebay.get_inventory_group(group_key, settings, access_token)

        return True, csr.ebay_offer_id, csr.ebay_listing_id
    
        #print("asking for token ")
        #access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        #print(access_token)
        #ebay.publish_offer("66119568011", access_token)

    else:
        return False, None, None


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
