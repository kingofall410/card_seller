import requests, os, time, json, base64
from requests.auth import HTTPBasicAuth
from PIL import Image
from pathlib import Path
import time
from datetime import datetime, timedelta
from requests.exceptions import Timeout, RequestException
from urllib.parse import quote, quote_plus, urlencode


CLIENT_ID = 'DanielCr-LatestSa-PRD-d11490c6b-277c9c6f'
CLIENT_SECRET = 'PRD-113ecf9c5fd1-5956-4012-a05a-9770'
RUNAME = "Daniel_Crown-DanielCr-Latest-obqqa"
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

ebay_item_group_template = {
    "aspects": {}, #"pattern": ["solid"]
    "description": "string",
    "imageUrls": [
        "string"
    ],
    "inventoryItemGroupKey": "string",
    "subtitle": "string",
    "title": "string",
    "variantSKUs": [
        "string"
    ],
    "variesBy": {
    "aspectsImageVariesBy": [
        "string"
    ],
    "specifications": [
        {
        "name": "string",
        "values": [
            "string"
        ]
        }
    ]
    },
}
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
            "Card": "variation_title_base",
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
    #else:#user-less request
        #print("user-less")
        #data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
       
    url = 'https://api.ebay.com/identity/v1/oauth2/token'
    headers = {"Content-Type": "application/x-www-form-urlencoded"}    

    
    print("*"+base64.b64decode("RGFuaWVsQ3ItTGF0ZXN0U2EtUFJELWQxMTQ5MGM2Yi0yNzdjOWM2ZjpQUkQtMTEzZWNmOWM1ZmQxLTU5NTYtNDAxMi1hMDVhLTk3NzA=").decode()+"*")

    response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET))
    
    print("🔗 URL:", response.request.url)
    print("📨 Method:", response.request.method)
    print("🧾 Headers:", response.request.headers)
    print("📦 Body:", response.request.body)

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

def build_query_params(search_string, limit, offset, category_id, sort="price"):
    return [
        f"q={quote_plus(search_string.replace('#', ''))}",
        f"limit={limit}",
        f"offset={offset}",
        f"category_ids={category_id}",
        f"sort={sort}"
    ]

def text_search(keyword_strings, settings, limit=50, page=1):
    print("text_search: ", keyword_strings)

    result_data = {}
    if has_user_consent(settings):
        access_token = get_access_token(settings, settings.ebay_user_auth_code)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    category_id = get_dominant_category_id(None)
    offset = (page - 1) * limit

    for keywords in keyword_strings:
        row_count = 0
        page_num = 0

        result_data[keywords[0]] = (keywords[1], [])    
        query_params = build_query_params(keywords[0], limit, offset, category_id)
        search_url = f"{TXT_SEARCH_URL}?{'&'.join(query_params)}"

        #search_url = f"{TXT_SEARCH_URL}?q={urlencode(keywords[0].replace("#", ""))}{'&'.join(query_params)}"
        print("Search URL:", search_url)

        try:
            response = requests.get(search_url, headers=headers, timeout=10)
        except Timeout:
            print("❌ Request timed out while contacting eBay image search API.")
            break
        except RequestException as e:
            print(f"❌ Request failed: {e}")
        
        if response and response.status_code == 200:
            #print(response.json())
            items = response.json().get("itemSummaries", [])
            if not items:
                print("❌ No matches found.")
                break
            else:
                print(f"✅ Found {len(items)} matches for the input string.")
                result_data[keywords[0]][1].extend(items)
        else:
            print(response.json())
        
    return result_data

#TODO: the standard way of getting dominant category has never worked.  It's hardcoded for now
def get_dominant_category_id(payload):
    return '261328'
    
#TODO: I don't think this will actually work if settings=None
def image_search(loaded_img, limit=10, page=1, settings=None):
    print("image_search: ", loaded_img.name)
    #if not auth_token:
    if has_user_consent(settings):
        access_token = get_access_token(settings, settings.ebay_user_auth_code)
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

        offset = (page - 1) * limit
        query_params = [
            f"limit={limit}",
            f"offset={offset}",
            f"category_ids={category_id}"
        ]
        search_url = f"{IMG_SEARCH_URL}?{'&'.join(query_params)}"
        print("Search URL:", search_url)
        try:
            response = requests.post(search_url, headers=headers, json=payload, timeout=10)
        except Timeout:
            print("❌ Request timed out while contacting eBay image search API.")
            return
        except RequestException as e:
            print(f"❌ Request failed: {e}")

        print("resp: ", response)
        #print("resp: ", response.json())
        if response and response.status_code == 200:
            #print(response.json())
            items = response.json().get("itemSummaries", [])
            if not items:
                print("❌ No matches found.")
                return
            else:
                print(f"✅ Found {len(items)} matches for the input image.")
                return items
        else:
            print(response.json())

def update_inventory_item_qty(update_data, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = "https://api.ebay.com/sell/inventory/v1/bulk_update_price_quantity"

    print("URL:", url)
    print("update_data:", update_data)
    response = requests.post(url, headers=headers, json=update_data)
    print("Update Qty response: ", response, response.text)
    return response.status_code == 200 or response.status_code == 204

#https://auth.ebay.com/oauth2/authorize?client_id=DanielCr-LatestSa-PRD-8a6d6e5b0-96ce1b10&redirect_uri=Daniel_Crown-DanielCr-Latest-reqvvsrz&response_type=code&scope=https://api.ebay.com/oauth/api_scope/sell.inventory
def create_inventory_item(sku, item_data, access_token, patch=False):
    #get_user_auth()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
   
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    print("URL:", url)
    print("item_data:", item_data)
    if patch:
        print("patching")
        response = requests.patch(url, headers=headers, json=item_data)
    else:
        response = requests.put(url, headers=headers, json=item_data)
    #print("Inventory request: ", response.request.text)
    print("Inventory response: ", response, response.text)
    return response.status_code == 200 or response.status_code == 204

def create_inventory_group(group_id, group_data, access_token):
    #get_user_auth()
    #delete_inventory_group(group_id, access_token)
    #get_inventory_group(group_id, access_token)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_id}"
    print("Inventory Group request data:", group_data)
    response = requests.put(url, headers=headers, json=group_data)
    print("Inventory Group response: ", response, response.text)
    return response.status_code == 200 or response.status_code == 204

def delete_inventory_group(group_id, settings, access_token=None):
    #get_user_auth()
    access_token = access_token or get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_id}"
    response = requests.delete(url, headers=headers)
    print("Inventory Delete response: ", response, response.text)
    return response.status_code == 200 or response.status_code == 204


def get_inventory_group(group_id, settings, access_token=None):
    #get_user_auth()
    access_token = access_token or get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_id}"
    response = requests.get(url, headers=headers)
    print("inventory get request:", group_id)
    print("Inventory Get response: ", response, response.text)
    return
    return response.status_code == 200 or response.status_code == 204


def get_or_create_offer(offer_data, access_token, sku=None):

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = "https://api.ebay.com/sell/inventory/v1/offer"
    
    offer_id = None
    response = requests.post(url, headers=headers, json=offer_data)
    print("Offer response: ", response, response.text)
    
    #TODO this should be cleaned up and generalized
    data = response.json()
    if response.status_code == 201:#offer created
        offer_id = data.get('offerId', None)
    elif response.status_code == 400 and sku:#offer already exists, delete it
        #TODO:ultimately the right thing to do here is update the offer, not delete, but fine for now
        offer_id = data['errors'][0]['parameters'][0]['value']
        delete_url = url + f"/{offer_id}"        
        response = requests.delete(delete_url, headers=headers, json=offer_data)
        response = requests.post(url, headers=headers, json=offer_data)
        print("Offer response 2: ", response, response.text)
        
        if response.status_code == 201:
            offer_id = response.json().get('offerId', None)

    return offer_id, response.status_code


def publish_offer(offer_id, access_token):
    print("publish", offer_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
    response = requests.post(url, headers=headers)
    print ("Publish response", response.text)
    return response.json()["listingId"]

def publish_inventory_group(group_name, access_token):
    print("PIG:", group_name)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = f"https://api.ebay.com/sell/inventory/v1/offer/publish_by_inventory_item_group"
    
    inventory_group_listing_data = {
        "inventoryItemGroupKey": group_name,
        "marketplaceId": "EBAY_US"
    }
    response = requests.post(url, json=inventory_group_listing_data, headers=headers)
    print ("PIG response", response.text)
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


from playwright.sync_api import sync_playwright
import time
import random

def launch_and_login():
    with sync_playwright() as p:
        user_data_dir = "ebay_profile"
        browser = p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = browser.new_page()
        page.goto("https://www.ebay.com/signin")

        print("Log in manually, then close the browser window.")
        page.wait_for_timeout(120000)  # 60 seconds to log in
        browser.close()

def get_split_part_text(text, index, split_index):
    try:
        return text.split("\n")[split_index].strip()
    except (IndexError, AttributeError):
        return None


def get_ebay_date_range(days=90):
    now = datetime.now()

    # First day of next month
    first_next_month = datetime(now.year + (now.month // 12), (now.month % 12) + 1, 1)

    # Last day of current month at 11:59:59 PM
    end_dt = first_next_month - timedelta(seconds=1)

    # Start date: N days before end date
    start_dt = end_dt - timedelta(days=days)

    # Convert to Unix timestamps in milliseconds
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    return start_ts, end_ts


#TODO: if this persists, will need to improve the login process
from playwright.sync_api import TimeoutError
import time

def scrape_with_profile(keyword_strings, limit=50, max_pages=3, days=180):
    print("keywords:", keyword_strings)
    result_data = {}

    with sync_playwright() as p:
        user_data_dir = "ebay_profile"
        browser = p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = browser.new_page()
        start_date, end_date = get_ebay_date_range(days=90)

        base_url = "http://www.ebay.com/sh/research"
        query = {
            "marketplace": "EBAY-US",
            "dayRange": "90",
            "categoryId": "0",
            "tabName": "SOLD",
            "tz": "America/New_York",
            "limit": str(limit),
            "startDate": start_date,
            "endDate": end_date,
        }

        for keywords in keyword_strings:
            row_count = 0
            page_num = 0

            query["keywords"] = quote_plus(keywords[0])
            result_data[keywords[0]] = (keywords[1], [])
            while row_count < limit and page_num < max_pages:
                
                query["offset"] = page_num*limit
                url = base_url + "?" + "&".join(f"{k}={v}" for k, v in query.items())
                print("url", url)
                page.goto(url, timeout=10000)

                try:
                    page.wait_for_selector("table", timeout=15000)
                    page.wait_for_timeout(2000)
                except TimeoutError:
                    #exit after a perfect match between limit and query
                    print(f"Timeout waiting for table on page {page_num}.")
                    break

                rows = page.query_selector_all(".research-table-row")
                row_count = len(rows)
                print("row_count:", len(rows))

                rows_data = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('.research-table-row')).map(row => {
                    const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
                    const img = row.querySelector('img');
                    const imgUrl = img ? img.src : null;
                    return { cells, imgUrl };
                });
                }""")

                for row_data in rows_data:
                    cells = row_data["cells"]
                    if len(cells) < 8:
                        continue

                    result_data[keywords[0]][1].append({
                            "title": get_split_part_text(cells[0], 0, 1),
                            "price": get_split_part_text(cells[2], 0, 0),
                            "format": get_split_part_text(cells[2], 0, 1),
                            "sold_date": cells[7],
                            "shipping": get_split_part_text(cells[3], 0, 0),
                            "qty": cells[4],
                            "itemWebUrl": row_data["imgUrl"]
                        })
                    
                page_num += 1
                row_count += limit

        browser.close()
        return result_data


