import requests, os, time, json, base64
from requests.auth import HTTPBasicAuth
from PIL import Image
from pathlib import Path
import time
from datetime import datetime, timedelta
from requests.exceptions import Timeout, RequestException
from urllib.parse import quote, quote_plus, urlencode
from core.models.Status import StatusBase
from services.models.models import Settings
from core.models.ListingStatus import ListingStatus
import fcntl
from playwright.sync_api import sync_playwright
from django.utils.timezone import timezone


CLIENT_ID = 'DanielCr-LatestSa-PRD-d11490c6b-277c9c6f'
CLIENT_SECRET = 'PRD-113ecf9c5fd1-5956-4012-a05a-9770'
RUNAME = "Daniel_Crown-DanielCr-Latest-obqqa"
IMG_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"
TXT_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SELL_URL="https://api.ebay.com/oauth/api_scope/sell.inventory"
USER_AUTH_URL = f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={RUNAME}&response_type=code&scope=https://api.ebay.com/oauth/api_scope/sell.inventory&%20https://api.ebay.com/oauth/api_scope/sell.fulfillment"

#f"https://auth.ebay.com/oauth2/authorize?client_id=DanielCr-LatestSa-PRD-d11490c6b-277c9c6f&redirect_uri=Daniel_Crown-DanielCr-Latest-obqqa&response_type=code&scope=https://api.ebay.com/oauth/api_scope/sell.inventory%20https://api.ebay.com/oauth/api_scope/sell.fulfillment"

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
ebay_offer_data_template = {
    "sku": "string",
    "marketplaceId": "EBAY_US",
    "format": "FIXED_PRICE",
    "listingDescription": "string",
    "availableQuantity": "string",
    "pricingSummary": {
        "price": {
            "value": "string",
            "currency": "USD"
        }
    },
    "condition": 4000,
    "categoryId": CATEGORY_ID,
    "listingPolicies": {    
        "fulfillmentPolicyId": "string",
        "paymentPolicyId": PAYMENT_POLICY_EBAY_MANAGED,
        "returnPolicyId": RETURN_POLICY_NO_RETURNS
    },
    "merchantLocationKey": "Freeport"
}

ebay_item_data_template = {
    "condition":"Ungraded",
    "availability": {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        },
    "product": {    
        "title":"display_title_to_be",
        "imageUrls":"image_links",
        "aspects": {
            "Card": "variation_title_base",
            "Sport": "sport",
            "Player/Athlete": "full_name",
            "Parallel/Variety": "display_parallel",
            "Card Name": "display_card_name",
            "Card Number": "display_card_number",
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
    "Title":"display_title_to_be",
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

def get_access_token(settings, user_auth_code=None, force=False):
    now = time.time()

    if user_auth_code:
        if now < settings.ebay_access_token_expiration and settings.last_run_usered:
            print("Using existing access token...")
            return settings.ebay_access_token
        elif now < settings.ebay_refresh_token_expiration:#trade refresh token for access token
            print("Refreshing access token for eBay...")
            data = {'grant_type': 'refresh_token', 'refresh_token':settings.ebay_refresh_token}
        else:
            print("Trading user auth code...")
            data = {'grant_type': 'authorization_code', "code":"this will not work'v^1.1#i^1#I^3#f^0#p^3#r^1#t^Ul41XzQ6NkEwMUU4NEQ0QjNBQkIwM0VGQzk5OTkyOTFBQkQ5OEJfMl8xI0VeMjYw", "redirect_uri":RUNAME}

        settings.last_run_usered = True
    else:#user-less request
        print("user-less")
        data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
        settings.last_run_usered = False
        
    url = 'https://api.ebay.com/identity/v1/oauth2/token'
    headers = {"Content-Type": "application/x-www-form-urlencoded"}    

    
    #print("*"+base64.b64decode("RGFuaWVsQ3ItTGF0ZXN0U2EtUFJELWQxMTQ5MGM2Yi0yNzdjOWM2ZjpQUkQtMTEzZWNmOWM1ZmQxLTU5NTYtNDAxMi1hMDVhLTk3NzA=").decode()+"*")

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
        raise Exception(f"❌ Token request failed with status code {response.status_code}.")
    
    return settings.ebay_access_token

def build_query_params(search_string, limit, offset, category_id, sort="price"):
    return [
        f"q={quote_plus(search_string.replace('#', ''))}",
        f"limit={limit}",
        f"offset={offset}",
        f"category_ids={category_id}",
        f"sort={sort}"
    ]
def _execute_ebay_search(keyword_strings, settings, limit, page, build_params_fn):
    """
    Internal helper that handles authentication, URL requests, error tracking,
    and structures the result dictionary for a list of keyword strings.
    """
    result_data = {}
    
    # Handle token authentication safely
    access_token = None
    if has_user_consent(settings):
        access_token = get_access_token(settings, None)
        
    if not access_token:
        print("❌ Failed to retrieve a valid access token.")
        return result_data

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    category_id = get_dominant_category_id(None)
    offset = (page - 1) * limit

    for keywords in keyword_strings:
        search_term = keywords[0]
        metadata = keywords[1]
        result_data[search_term] = (metadata, [])
        
        # Call the specific lambda/function passed in to build unique filters
        params = build_params_fn(search_term, limit, offset, category_id)

        try:
            # Let requests naturally handle parameter encoding
            response = requests.get(TXT_SEARCH_URL, headers=headers, params=params, timeout=10)
        except Timeout:
            print(f"❌ Request timed out for term: {search_term}")
            continue
        except RequestException as e:
            print(f"❌ Request failed for term: {search_term}. Error: {e}")
            continue
        
        if response.status_code == 200:
            items = response.json().get("itemSummaries", [])
            if not items:
                print(f"❌ No matches found for '{search_term}'.")
            else:
                print(f"✅ Found {len(items)} matches for '{search_term}'.")
                result_data[search_term][1].extend(items)
        else:
            try:
                error_msg = response.json()["errors"][0]["message"]
                print(f"❌ eBay API Error for '{search_term}': {error_msg}")
            except (KeyError, ValueError):
                print(f"❌ HTTP Error {response.status_code}: {response.text}")
                
    return result_data


# =====================================================================
# Refactored Public Methods
# =====================================================================

def text_search(keyword_strings, settings, limit=50, page=3):
    print("text_search: ", keyword_strings)
    
    # Use your existing build_query_params logic adapted for dictionary output
    def build_standard_params(term, lim, off, cat_id):
        # Assumes build_query_params returns a dict, or you can map it here
        params = {'q': term, 'limit': lim, 'offset': off, 'category_ids': get_dominant_category_id(None)}
        return params

    return _execute_ebay_search(keyword_strings, settings, limit, page, build_standard_params)

def auction_search(keyword_strings, settings, limit=50, hours_until_end=24, page=1):
    print(f"auction_search: {keyword_strings}, ending within {hours_until_end} hours, 0 bids")
    settings = settings or Settings.get_default()
    # Set up time ranges
    now_utc = datetime.now(timezone.utc)
    end_utc = now_utc + timedelta(hours=hours_until_end)
    now_str = now_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    end_str = end_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    # Define custom query filters for zero-bid auctions
    def build_auction_params(term, lim, off, cat_id):
        filter_query = f"buyingOptions:{{AUCTION}},endDate:[{now_str}..{end_str}]"
        params = {
            'q': term,
            'limit': lim,
            'offset': off,
            'filter': filter_query,
            'sort': 'endingSoonest'  # <-- Added: Ensures items ending in minutes appear first
        }
        if cat_id:
            params['category_ids'] = cat_id
        return params

    return _execute_ebay_search(keyword_strings, settings, limit, page, build_auction_params)

#TODO: the standard way of getting dominant category has never worked.  It's hardcoded for now
def get_dominant_category_id(payload):
    return '261328'
    
#TODO: I don't think this will actually work if settings=None
def image_search(loaded_img, limit=10, page=1, settings=None):
    print("image_search: ", loaded_img.name)
    #if not auth_token:
    if has_user_consent(settings):
        access_token = get_access_token(settings, None)
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
            response = requests.post(search_url, headers=headers, json=payload, timeout=120)
        except Timeout:
            print("❌ Request timed out while contacting eBay image search API.")
            return
        except RequestException as e:
            print(f"❌ Request failed: {e}")

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
            raise Exception(response.json()["errors"][0]["message"])

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
    if response.status_code == 200 or response.status_code == 204:
        return True
    else:
        raise Exception(response.json()["errors"][0]["message"])

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
    #print("Inventory response: ", response, response.text)
    if response.status_code == 200 or response.status_code == 204:
        return True
    else:
        raise Exception(response.json()["errors"][0]["message"])

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
    if response.status_code == 200 or response.status_code == 204:
        return True
    elif response.json()["errors"][0]["errorId"] == 25703 or response.json()["errors"][0]["errorId"] == 25711:
        #missing a previous variant SKU from the group
        error_message = response.json()["errors"][0]["message"] + ": " + "; ".join(group_data["variantSKUs"])
        raise Exception(error_message)
    else:
        error_message = response.json()["errors"][0]["message"]
        raise Exception(error_message)
        
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
    if response.status_code == 200 or response.status_code == 204:
        return True
    else:
        raise Exception(response.json()["errors"][0]["message"])


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
    if response.status_code == 200 or response.status_code == 204:
        return True
    else:
        raise Exception(response.json()["errors"][0]["message"])


def get_inventory_item(sku, settings, access_token=None):
    #get_user_auth()
    access_token = access_token or get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    response = requests.get(url, headers=headers)
    print("Item get request:", sku)
    print("Item Get response: ", response, response.text)
    if response.status_code == 200 or response.status_code == 204:
        return True
    else:
        raise Exception(response.json()["errors"][0]["message"])


def backfill_order_by_id(order_ids, settings):
    access_token = get_access_token(settings, settings.ebay_user_auth_code)
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # URL for a single specific order
    url = f"https://api.ebay.com/sell/fulfillment/v1/order/{order_id}"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        order_data = response.json()
        # Reuse your existing logic to map this to ListedInfo/ListingStatus
        # (Pass order_data into a version of your update logic)
        return order_data
    else:
        print(f"Failed to fetch {order_id}: {response.text}")
        return None

def bulk_order_update(listing_ids, settings):
    access_token = get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    start_date = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Filter by creation date range
    url = f"https://api.ebay.com/sell/fulfillment/v1/order?filter=creationdate:[{start_date}..]"
    
    response = requests.get(url, headers=headers)
    data = response.json()
    #print(response)
    if response.status_code == 200:
        orders = data.get("orders", [])
        
        # 1. Map by SKU for variations and Listing ID for singles
        # Fetch all records that match the provided listing IDs
        from core.models.ListedInfo import ListedInfo
        infos = ListedInfo.objects.filter(listing_id__in=listing_ids)
        
        # Create two maps: one for direct ID lookup and one for SKU lookup
        listing_id_map = {str(info.listing_id): info for info in infos}
        sku_map = {str(info.sku): info for info in infos if info.sku}
        
        updated_count = 0

        for order in orders:
            for item in order.get("lineItems", []):
                legacy_id = str(item.get("legacyItemId"))
                # Variation SKU usually lives inside the 'sku' field of the line item directly
                # or sometimes nested in 'variation'
                sku = item.get("sku") 
                
                # 2. MATCHING LOGIC
                parent_info = None
                
                # Priority 1: Match by SKU (Variation)
                if sku and sku in sku_map:
                    parent_info = sku_map[sku]
                # Priority 2: Match by Legacy ID (Single Listing)
                elif legacy_id in listing_id_map:
                    parent_info = listing_id_map[legacy_id]
                
                if parent_info:
                    # 3. Get latest status or create new
                    obj = ListingStatus.objects.filter(listing_info=parent_info).order_by('-id').first()

                    if not obj:
                        obj = ListingStatus(
                            listing_info=parent_info, 
                            available_qty=0, 
                            listing_status=StatusBase.SOLD, 
                            sold_qty=1, 
                            is_published=True
                        )
                        print(f"Creating new ListingStatus for SKU: {sku or legacy_id}")

                    # 4. Update the fields
                    obj.order_id = order["orderId"]
                    obj.status = order["orderFulfillmentStatus"]

                    # Use the 'total' field of the line item. 
                    # This is CRITICAL for variations so you don't get the whole order total.
                    line_item_price = item.get("lineItemCost", {}).get("value")
                    summary_total = order.get("pricingSummary", {}).get("priceSubtotal", {}).get("value")
                    obj.sold_value = line_item_price or summary_total

                    obj.sold_date = order["creationDate"]
                    obj.save()
                    parent_info.card.active_search_results.save()
                    updated_count += 1
                    print(f"Synced {parent_info}: Sold for {obj.sold_value}")

        return access_token
    else:
        raise Exception(data.get("errors")[0].get("message"))

def get_sale_details(listing_id, settings, listing_status_obj, access_token=None):
    access_token = access_token or get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    start_date = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Filter by creation date range
    url = f"https://api.ebay.com/sell/fulfillment/v1/order?filter=creationdate:[{start_date}..]"
    
    response = requests.get(url, headers=headers)
    data = response.json()
    #print(response)
    if response.status_code == 200:
        orders = data.get("orders", [])
        #print(orders)
        # Manually find the order that contains our listing_id
        target_order = None
        for order in orders:
            #print("ORDER", order)
            for item in order.get("lineItems", []):
                if str(item.get("legacyItemId")) == str(listing_id):
                    target_order = order
                    break
            if target_order: break

        if not target_order:
            print(f"No orders found for listing {listing_id} in the last 30 days.")
            return None

        # Process the found order
        order_id = target_order["orderId"]
        status = target_order["orderFulfillmentStatus"]
        listing_status_obj.sold_value = target_order["pricingSummary"]["priceSubtotal"]["value"]
        listing_status_obj.sold_date = target_order["creationDate"]
        listing_status_obj.save()
        return access_token
    else:
        raise Exception(data.get("errors")[0].get("message"))


def get_offer_status(offer_id, settings, info, access_token=None):
    settings = settings or Settings.get_default()
    access_token = access_token or get_access_token(settings, settings.ebay_user_auth_code)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-US",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"
    response = requests.get(url, headers=headers)
    data = response.json()
    if response.status_code == 200:
        avail_qty = data["availableQuantity"]
        print(data)
        if "listing" in data:
            ebay_listing_status = data["listing"]["listingStatus"]
            if ebay_listing_status == "OUT_OF_STOCK":
                list_status = StatusBase.SOLD
            elif ebay_listing_status == "ENDED":
                list_status = StatusBase.UNLISTED
            else:
                list_status = StatusBase.CONFIRMED
            sold_qty = data["listing"]["soldQuantity"]
            published = data["status"] == "PUBLISHED"
        else:#change this --> it should just send the actual status back and let individual cards do what they will
            if info.card.active_search_results.overall_status == StatusBase.STAGED:
                list_status = StatusBase.FAILED
            else:
                list_status = StatusBase.UNLISTED
            sold_qty = 0
            published = False
        #print(avail_qty, list_status, sold_qty, published)
        ListingStatus.create(info, avail_qty, list_status, sold_qty, published)
        return True, access_token, list_status
    else:
        ListingStatus.create(info, 0, StatusBase.UNKNOWN, 0, False)
        #print(response)
        return False, access_token, StatusBase.UNKNOWN
    

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
        else:
            raise Exception(response.json()["errors"][0]["message"])

    return offer_id, response.status_code

#TODO: capture insertion fee from the publish response and allocate to listing as appropriate
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

#TODO: capture insertion fee from the publish response and allocate to listing as appropriate
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
    print ("group name", group_name)
    print ("PIG response", response.text)
    if response.status_code == 200 or response.status_code == 204:
        return response.json()["listingId"]
    else:
        raise Exception(response.json()["errors"][0]["message"])

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
    pass
    '''this all has to be reworked in accordance with the new playwright mechanism in scrape_with_profile
    with sync_playwright() as p:
        #user_data_dir = "ebay_profile"
        #browser = p.chromium.launch_persistent_context(user_data_dir, headless=False)#, args=["--no-sandbox", "--disable-dev-shm-usage"])        
        user_data_dir = "/home/dcrown/.config/dev-chrome-dir"
        browser = p.chromium.launch_persistent_context(user_data_dir, headless=False, executable_path="/usr/bin/google-chrome", \
            args=["--use-gl=desktop", "--ignore-gpu-blocklist", "--disable-gpu-sandbox", \
            "--enable-gpu-rasterization", "--enable-zero-copy", "--use-angle=gl", "--gpu-launcher-wait-time=5000"])
        page = browser.new_page()
        page.goto("https://www.ebay.com/signin")
        #page.screenshot(path="login debug.png")
        print("Log in manually, then close the browser window.")
        page.wait_for_timeout(120000)  # 60 seconds to log in
        browser.close()'''

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

def scrape_with_profile(keyword_strings, limit=50, max_pages=3, days=1095):
    print("keywords:", keyword_strings)
    result_data = {}
    
    # Define paths
    user_data_dir = "/home/dcrown/.config/chrome-clean-playwright"
    exe_path = "/usr/bin/google-chrome"
    # We use a custom lock file to coordinate between our own python processes
    lock_file_path = os.path.join(user_data_dir, "profile.lock")
    
    # Ensure directory exists for the lock file
    os.makedirs(user_data_dir, exist_ok=True)

    # The 'with' block opens the lock file; fcntl.flock then BLOCKS execution 
    # if another task is already running.
    print("Requesting profile lock...")
    with open(lock_file_path, "w") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        print("Lock acquired. Starting Chrome...")

        try:
            # Clear any stale Chrome-internal locks that might cause an abort
            singleton_lock = os.path.join(user_data_dir, "SingletonLock")
            if os.path.exists(singleton_lock):
                try:
                    os.remove(singleton_lock)
                except OSError:
                    pass

            with sync_playwright() as p:
                args = [
                    "--use-gl=desktop", 
                    "--use-angle=gl", 
                    "--ignore-gpu-blocklist", 
                    "--password-store=basic", 
                    "--no-first-run", 
                    "--no-default-browser-check", 
                    "--disable-extensions", 
                    "--disable-sync", 
                    "--disable-default-apps", 
                    "--disable-component-update"
                ]
                
                browser = p.chromium.launch_persistent_context(
                    user_data_dir, 
                    headless=False, 
                    executable_path=exe_path, 
                    args=args
                )

                # Subtract the window (e.g., 180 days)
                start_date, end_date = get_ebay_date_range(days)

                base_url = "http://www.ebay.com/sh/research"
                query = {
                    "marketplace": "EBAY-US",
                    "dayRange": str(days),
                    "categoryId": "0",
                    "tabName": "SOLD",
                    "tz": "America/New_York",
                    "limit": str(limit),
                    "startDate": start_date,
                    "endDate": end_date,
                    "sorting":"-datelastsold"
                }
                for keywords in keyword_strings:
                    row_count = 0
                    page_num = 0

                    # keywords is expected to be a tuple/list: (search_string, some_id)
                    current_search = keywords[0]
                    query["keywords"] = quote_plus(current_search)
                    result_data[current_search] = (keywords[1], [])

                    while page_num < max_pages:
                        query["offset"] = page_num * limit
                        url = base_url + "?" + "&".join(f"{k}={v}" for k, v in query.items())
                        print("URL:", url)
                        
                        page = browser.pages[0]
                        page.goto(url, timeout=60000)

                        try:
                            page.wait_for_selector("table, h2.page-notice__title", timeout=60000)
                        except Exception:
                            print(f"Timed out waiting for table on page {page_num}.")
                            break

                        rows_data = page.evaluate("""() => {
                            return Array.from(document.querySelectorAll('.research-table-row')).map(row => {
                                const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
                                const img = row.querySelector('img');
                                const imgUrl = img ? img.src : null;
                                return { cells, imgUrl };
                            });
                        }""")

                        print(f"Found {len(rows_data)} rows.")
                        
                        for row_data in rows_data:
                            cells = row_data["cells"]
                            if len(cells) < 8:
                                continue

                            # Assuming get_split_part_text exists in your scope
                            result_data[keywords[0]][1].append({
                            "title": get_split_part_text(cells[0], 0, 1),
                            "price": get_split_part_text(cells[2], 0, 0),
                            "format": get_split_part_text(cells[2], 0, 1),
                            "sold_date": cells[7],
                            "shipping": get_split_part_text(cells[3], 0, 0),
                            "qty": cells[4],
                            "bids": cells[6],
                            "itemWebUrl": row_data["imgUrl"]
                        })
                        
                        page_num += 1
                        row_count += len(rows_data)
                        
                        # Break if we didn't get a full page (means no more results)
                        if len(rows_data) < limit:
                            break

                browser.close()
                
        finally:
            # Release the file lock so the next task waiting can proceed
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            print("Lock released.")

    return result_data