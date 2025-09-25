import csv, io
from core.models.CardSearchResult import CardSearchResult, ResultStatus
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
import random

#TODO: This whole process is cobbled together.  needs to be fixed
def export_to_ebay(csrs, publish=False):
    
    print("ebay export")
    settings = Settings.get_default()
    #uploader = GoogleDriveUploader()
    if ebay.has_user_consent(settings):

        csr = csrs[0]
        #shareable_link_front = uploader.upload_and_share(csr.get_latest_front(), csr.title_to_be)
        #shareable_link_reverse = uploader.upload_and_share(csr.get_latest_reverse(), csr.title_to_be)
        #TODO:abstract away google vs imagur vs postimage etc
        
        shareable_link_front = upload_to_cloudinary(csr.get_latest_front())
        shareable_link_reverse = upload_to_cloudinary(csr.get_latest_reverse())
        csr.ebay_item_id = csr.build_sku()
        print("SKU:", csr.ebay_item_id)
        print("🔗 Public link:", shareable_link_front)
        print("🔗 Public link:", shareable_link_reverse)

        item_data = csr.export_to_template(csr.ebay_item_id, ebay.ebay_item_data_template, [shareable_link_front, shareable_link_reverse])
        print(item_data)
        offer_data = {
            "sku": csr.ebay_item_id,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "listingDescription": csr.title_to_be,
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
                "fulfillmentPolicyId": ebay.SHIPPING_POLICY_USPS_GROUND,
                "paymentPolicyId": ebay.PAYMENT_POLICY_EBAY_MANAGED,
                "returnPolicyId": ebay.RETURN_POLICY_NO_RETURNS
            },
            "merchantLocationKey": "Freeport"

        }
        print(offer_data)
        access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
        #create_ebay_location(access_token)
        #csr.check_category_metadata("261328",access_token)
        if ebay.create_inventory_item(csr.ebay_item_id, item_data, access_token):
            #print("checkinv: ", csr.check_inventory_item_exists(sku, access_token))
            csr.ebay_offer_id = ebay.create_offer(offer_data, access_token)
            #csr.get_offer(offer_id, access_token)

            if publish:
                csr.ebay_listing_id = ebay.publish_offer(csr.ebay_offer_id, access_token)
            else:
                csr.ebay_listing_id = ""
            csr.status = ResultStatus.LISTED
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
