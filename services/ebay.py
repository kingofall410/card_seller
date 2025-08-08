import requests, os, time, json, base64
from requests.auth import HTTPBasicAuth
from PIL import Image
from pathlib import Path
from core.models.Card import Card
import time
from urllib.parse import quote

CLIENT_ID = 'DanielCr-LatestSa-PRD-8a6d6e5b0-96ce1b10'
CLIENT_SECRET = 'PRD-a6d6e5b02d26-532c-4825-8507-5903'

IMG_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image?limit="
TXT_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

auth_token = None
auth_token_expiry = None

headers = {
    "Authorization": f"Bearer {auth_token}",
    "Content-Type": "application/json",
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
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
    "C:Sport":"",
    "C:Player/Athlete":"full_name",
    "C:Signed By":"",
    "C:Season":"year",
    "C:Manufacturer":"brand",
    "C:Parallel/Variety":"",
    "C:Features":"",
    "C:Set":"subset",
    "C:Team":"team",
    "C:League":"",
    "C:Autographed":"",
    "C:Card Name":"",
    "C:Card Number":"card_number",
    "C:Type":"",
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

def get_access_token():
    global auth_token, headers, auth_token_expiry
    if not auth_token_expiry:
        print("Requesting new access token for eBay...")
    elif time.time() >= auth_token_expiry:
        print("Refreshing access token for eBay...")
    else:
        print(f"✅ Using existing access token which expires at {auth_token_expiry} (currently {time.time()})")
        return auth_token

    url = 'https://api.ebay.com/identity/v1/oauth2/token'
    headers = {'Content-Type': 'application/json'}
    data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
    response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET))
    if response.status_code == 200:     
        auth_token = response.json()['access_token']  
        auth_token_expires_in = response.json()['expires_in']  
        auth_token_expiry = time.time() + auth_token_expires_in
        print(f"✅ Access token received successfully. Valid until {auth_token_expiry} (currently {time.time()})") 
        headers["Authorization"] = f"Bearer {auth_token}"

    else:
        print(f"❌ Token request failed with status code {response.status_code}.")
        print(response.text)
    
    return auth_token

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

def image_search(loaded_img, limit=10):
    print("image_search: ", loaded_img.name)
    #if not auth_token:
    get_access_token()
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    try:
        encoded = base64.b64encode(loaded_img.read()).decode("utf-8")
    except Exception as e:
        print(f"❌ Failed to encode image: {e}")
        return
    
    category_id = "261328"
    search_url = f"{IMG_SEARCH_URL}{limit}"
    print(search_url)
    payload = { 
        "image": encoded
    }
    response = requests.post(search_url, headers=headers, json=payload)
    print("resp: ", response)
    if response.status_code == 200:
        print(response.json())
        items = response.json().get("itemSummaries", [])
        if not items:
            print("❌ No matches found.")
            return
        else:
            print(f"✅ Found {len(items)} matches for the input image.")
            return items
        





    '''def create_inventory_item(self, sku, item_data):
        url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
        response = requests.put(url, headers=self.headers, json=item_data)
        return response.json()

    def create_offer(self, offer_data):
        url = "https://api.ebay.com/sell/inventory/v1/offer"
        response = requests.post(url, headers=self.headers, json=offer_data)
        return response.json()

    def publish_offer(self, offer_id):
        url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
        response = requests.post(url, headers=self.headers)
        return response.json()'''

