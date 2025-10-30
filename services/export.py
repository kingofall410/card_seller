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

def add_to_variation_group(csrs, access_token, group_name=None, publish=False):
    #TODO:check to see if the group exists before overwriting it once we create django objects
    group_name = group_name or csrs[0].display_full_name
    settings = Settings.get_default()
    
    #find or create django group object
    group, _ = ProductGroup.objects.get_or_create(name=group_name)
    for csr in csrs:
        csr.ebay_product_group = group
        csr.save()

    listing_id = None
    if ebay.has_user_consent(settings):
        csrs = [csr for csr in group.products.all()]
        variant_skus = [csr.sku for csr in csrs]
        variant_card_titles = [csr.variation_title for csr in csrs]
        variant_fronts = [csr.shareable_link_front for csr in csrs]

        inventory_group_data = {
            "aspects": {"Sport": ["Baseball"]},
            "description": "Every card is pictured, please don't hesitate to reach out with questions.", 
            "imageUrls": [csrs[0].shareable_link_front],
            "inventoryItemGroupKey": group_name,
            #"subtitle": "",
            "title": group_name,
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
        
        if ebay.create_inventory_group(group_name, inventory_group_data, access_token):
            if publish:
                listing_id = ebay.publish_inventory_group(group_name, access_token)
    return listing_id


#TODO: This whole process is cobbled together.  needs to be fixed
def export_to_ebay(csrs, publish=False, group=None):
    
    print("ebay export")
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
        #print(item_data)
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
            
            if group:
                csr.ebay_listing_id = add_to_variation_group([csr], access_token, group_name=group, publish=publish)
            elif publish:
                csr.ebay_listing_id = ebay.publish_offer(offer_id, access_token)

            csr.save()

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
