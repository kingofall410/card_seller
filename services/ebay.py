import requests, os, time, json, base64
from requests.auth import HTTPBasicAuth
from PIL import Image
from pathlib import Path
import time

CLIENT_ID = 'DanielCr-LatestSa-PRD-8a6d6e5b0-96ce1b10'
CLIENT_SECRET = 'PRD-a6d6e5b02d26-532c-4825-8507-5903'
RUNAME = "Daniel_Crown-DanielCr-Latest-reqvvsrz"
IMG_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"
TXT_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SELL_URL="https://api.ebay.com/oauth/api_scope/sell.inventory"
USER_AUTH_URL = f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={RUNAME}&response_type=code&scope=https://api.ebay.com/oauth/api_scope/sell.inventory"

#business
SHIPPING_POLICY_STANDARD_ENVELOPE = "296581163011"
SHIPPING_POLICY_USPS_GROUND = "293529369011"
SHIPPING_POLICY_USPS_GROUND_FREE = "287506781011"
PAYMENT_POLICY_EBAY_MANAGED = "283258948011"
RETURN_POLICY_NO_RETURNS = "283258947011"
CATEGORY_ID = "261328"

category_expiry = None
category_id = None

#TODO: ultimately need to get this from the taxonomy API or excel file upload

ebay_item_data_template = {
    "condition":"Ungraded",
    "availability": {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        },
    "product": {    
        "title":"title_to_be",
        "imageUrls":"image_links",
        "aspects": {
            "Sport": "sport",
            "Player/Athlete": "full_name",
            "Card Name": "card_name",
            "Card Number": "card_number",
            #"Features": "features",
            "League": "league",
            "Team": "full_team",
            #"Event/Tournament": "",
            "Season": "year",
            "Set": "full_set",
            "Manufacturer": "brand",
            "Card Condition": "",#Near Mint or Better	Excellent	Very Good	Poor
            #"Grade": "",
            #"Certification Number": "",
            #"Professional Grader": "",
            "Autographed": ""
        },
    }
}


singles_excel_fields = {
    "*Action(SiteID=US|Country=US|Currency=USD|Version=1193)":"",
    "Custom label (SKU)":"",
    "Category ID":"",
    "Category name":"",
    "Title":"title_to_be",
    "Relationship":"",
    "Relationship details":"",
    "Schedule Time":"",
    "Start price":"",
    "Quantity":"",
    "Item photo URL":"",
    "VideoID":"",
    "Condition ID":"",
    "CD:Professional Grader - (ID: 27501)":"",
    "CD:Grade - (ID: 27502)":"",
    "CDA:Certification Number - (ID: 27503)":"",
    "CD:Card Condition - (ID: 40001)":"",
    "Description":"",
    "Format":"",
    "Duration":"",
    "Buy It Now price":"",
    "Best Offer Enabled":"",
    "Best Offer Auto Accept Price":"",
    "Minimum Best Offer Price":"",
    "Immediate pay required":"",
    "Location":"",
    "Shipping profile name":"",
    "Return profile name":"",
    "Payment profile name":"",
    "EconomicOperator CompanyName":"",
    "Sport":"",
    "Player/Athlete":"full_name",
    "Signed By":"",
    "Season":"year",
    "Manufacturer":"brand",
    "Parallel/Variety":"",
    "Features":"",
    "Set":"subset",
    "Team":"team",
    "League":"",
    "Autographed":"",
    "Card Name":"",
    "Card Number":"card_number",
    "Type":"",
    "Extra Title Info":"",
    "Extra Description Info":"",
    "Photo 1":"",
    "Photo 2":"",
    "Photo 3":"",
    "Photo 4":"",
    "WeightMinor":"",
    "WeightMajor":"",
    "WeightUnit":"",
    "PackageLength":"",
    "PackageDepth":"",
    "PackageWidth":"",
    "PostalCode":""
}

def has_user_consent(settings):
    
    return settings.ebay_user_auth_code or time.time() >= settings.ebay_refresh_token_expiration

def get_access_token(settings, user_auth_code=None):
    now = time.time()

    if user_auth_code:
        if now < settings.ebay_access_token_expiration:
            print("Using existing access token...")
            return settings.ebay_access_token
        elif now < settings.ebay_refresh_token_expiration:#trade refresh token for access token
            print("Refreshing access token for eBay...")
            data = {'grant_type': 'refresh_token', 'refresh_token':settings.ebay_refresh_token}
        else:
            print("Trading user auth code...")
            data = {'grant_type': 'authorization_code', "code":user_auth_code, "redirect_uri":RUNAME}
    else:#user-less request
        data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
       
    url = 'https://api.ebay.com/identity/v1/oauth2/token'
    headers = {"Content-Type": "application/x-www-form-urlencoded"}    

    response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET))
    print(response)
    if response.status_code == 200:
        data = response.json()

        #we may not get a refresh token if we already have one
        settings.ebay_refresh_token = data.get('refresh_token', settings.ebay_refresh_token)
        settings.ebay_refresh_token_expiration = (
            time.time() + data['refresh_token_expires_in']
            if 'refresh_token_expires_in' in data
            else settings.ebay_refresh_token_expiration
        )

        settings.ebay_access_token = data.get('access_token', settings.ebay_access_token)
        auth_token_expires_in = data.get('expires_in', 0.0)
        settings.ebay_access_token_expiration = time.time() + auth_token_expires_in

        settings.save()
        print(f"✅ Access token received successfully.") 

    else:
        print(f"❌ Token request failed with status code {response.status_code}.")
        print(response.text)
    
    return settings.ebay_access_token


def text_search(search_string, limit=10):
    print("text_search: ", search_string)
    #if not auth_token:
    get_access_token()
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    #url = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
    params = {'q': search_string, 'limit': 50, 'sort': 'price'}
    response = requests.get(TXT_SEARCH_URL, headers=headers, params=params)
    if response.status_code != 200:
        print(f"❌ eBay query failed with status code {response.status_code}.")
    #category_id = "261328"
    #search_url = f'{TXT_SEARCH_URL}q={quote(search_string)}&limit={limit}&category_ids={category_id}'
    
    #print(f"Request to: {search_url}")
    #response = requests.post(search_url, headers=headers)
    print("Response: ", response)
    if response.status_code == 200:
        print(response.json())
        items = response.json().get("itemSummaries", [])
        if not items:
            print("❌ No matches found.")
            return
        else:
            print(f"✅ Found {len(items)} matches for the input image.")
            return items

#TODO: the standard way of getting dominant category has never worked.  It's hardcoded for now
def get_dominant_category_id(payload):
    return '261328'
    

def image_search(loaded_img, limit=10, settings=None):
    print("image_search: ", loaded_img.name)
    #if not auth_token:
    if has_user_consent(settings):
        access_token = get_access_token(settings)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }
        try:
            encoded = base64.b64encode(loaded_img.read()).decode("utf-8")
        except Exception as e:
            print(f"❌ Failed to encode image: {e}")
            return


        payload = { 
            "image": encoded
        }

        category_id = get_dominant_category_id(payload)
        
        limit_str = f"limit={limit}"

        #TODO: these query params don't seem to have any effect; will have to do this manbually based on title results
        #TODO: it's possible they only work on text search, haven't tried
        category_str = f"category_ids={category_id}"
        brands = "{Topps|Bowman}"
        filter_str = f"aspect_filter=categoryId:{category_id},Team:San Diego Padres"

        search_url = f"{IMG_SEARCH_URL}?{limit_str}&{category_str}"
        print(search_url)
        
        response = requests.post(search_url, headers=headers, json=payload)
        print("resp: ", response)
        if response.status_code == 200:
            #print(response.json())
            items = response.json().get("itemSummaries", [])
            if not items:
                print("❌ No matches found.")
                return
            else:
                print(f"✅ Found {len(items)} matches for the input image.")
                return items


#https://auth.ebay.com/oauth2/authorize?client_id=DanielCr-LatestSa-PRD-8a6d6e5b0-96ce1b10&redirect_uri=Daniel_Crown-DanielCr-Latest-reqvvsrz&response_type=code&scope=https://api.ebay.com/oauth/api_scope/sell.inventory
def create_inventory_item(sku, item_data, access_token):
    #get_user_auth()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    response = requests.put(url, headers=headers, json=item_data)
    print("Inventory response: ", response.text)
    return response.status_code == 204

def create_offer(offer_data, access_token):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = "https://api.ebay.com/sell/inventory/v1/offer"
    
    offerId = None
    response = requests.post(url, headers=headers, json=offer_data)
    print("Offer response: ", response.text)
    data = response.json()
    offerId = data.get('offerId', None)
    return offerId


def publish_offer(offer_id, access_token):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
    response = requests.post(url, headers=headers)
    print (response.text)
    return response.json()["listingId"]


def create_location(access_token, merchant_location_key="Freeport"):
    url = "https://api.ebay.com/sell/inventory/v1/location/"+merchant_location_key
    location_data = {
        "location": {
            "address": {
                "country": "US",
                "postalCode": "04032"
            },
            #"geoCoordinates": {
            #"latitude": "number",
            #"longitude": "number"

            
            #}
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    response = requests.post(url, headers=headers, json=location_data)
    
    print ("Create Location: ", response)
    return response.status_code == 204

