import csv

from core.models.CardSearchResult import CardSearchResult
from core.models.ProductGroup import ProductGroup
from core.models.Card import Card
from core.models.Status import StatusBase
from core.models.ListingStatus import ListingStatus
from django.http import HttpResponse
from services.models.models import Settings
from services.google import GoogleDriveUploader
from services import ebay
from django.shortcuts import get_object_or_404
import requests, time, io, subprocess, json
from PIL import Image

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

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

import cloudinary, base64
import cloudinary.uploader
import os
import mimetypes
import requests
from io import BytesIO
from PIL import Image

#TODO:remove
cloudinary.config(
  cloud_name = "dg7c9vsis",
  api_key = "748944422398635",
  api_secret = "3xXqCNYuD3nfzStElFrviXFnioY"
)

IMGBB_API_KEY = "3d7d29fd0b01908d25e3364c1511a6f5"

CATBOX_API_URL = "https://catbox.moe/user/api.php"

def upload_image_with_catbox(image_file_path, userhash=None):
    # 1. Verify file existence
    if not os.path.exists(image_file_path):
        raise FileNotFoundError(f"[DEBUG] Local file not found: {image_file_path}")
        
    # 2. Prevent uploading 0-byte or unfinished files
    file_size = os.path.getsize(image_file_path)
    print(f"[DEBUG] Target file size: {file_size} bytes")
    if file_size == 0:
        raise ValueError(f"[DEBUG] Aborting: Local file is completely empty (0 bytes): {image_file_path}")

    # 3. Extract correct filename and MIME type
    filename = os.path.basename(image_file_path)
    content_type, _ = mimetypes.guess_type(image_file_path)
    if not content_type:
        content_type = "image/jpeg"

    data = {"reqtype": "fileupload"}
    if userhash:
        data["userhash"] = userhash

    print(f"[DEBUG] Uploading '{filename}' ({content_type}) to Catbox.moe...")

    try:
        with open(image_file_path, "rb") as f:
            # Explicitly passing the (filename, file_object, content_type) tuple
            response = requests.post(
                CATBOX_API_URL,
                data=data,
                files={"fileToUpload": (filename, f, content_type)},
                timeout=30
            )
            
        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Raw Response Text: {response.text}")
        
        if response.status_code == 200 and response.text.startswith("http"):
            image_url = response.text.strip()
            print(f"[DEBUG] Successfully uploaded. URL: {image_url}")
            return image_url
        else:
            raise Exception(f"Catbox server rejected upload: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] Network error during Catbox upload: {e}")
        raise

FREEIMAGE_API_URL = "https://freeimage.host/api/1/upload"

def upload_image_with_freeimage(image_file_path):
    # Mimic a real browser User-Agent to pass Cloudflare's bot check
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    
    print(f"[DEBUG] [Path] Target file: {image_file_path}")
    print(f"[DEBUG] [API] Uploading to FreeImage.host with browser User-Agent headers...")
    
    try:
        with open(image_file_path, "rb") as file:
            response = requests.post(
                FREEIMAGE_API_URL,
                headers=headers,
                data={
                    "key": "6d207e02198a847aa98d0a2a901485a5",       # Chevereto API v1 looks for key in payload data
                    "action": "upload",
                    "format": "json"
                },
                files={"source": file},
                timeout=30
            )
            
        print(f"[DEBUG] [Response Status Code] {response.status_code}")
        print(f"[DEBUG] [Response Headers] {dict(response.headers)}")
        
        content_type = response.headers.get("Content-Type", "")
        print(f"[DEBUG] [Content-Type] {content_type}")
        
        # Catch HTML responses triggered by Cloudflare blocks
        if "text/html" in content_type:
            print(f"[DEBUG] [Error] Received HTML instead of JSON. Cloudflare blocked the script.")
            print(f"[DEBUG] [HTML Snippet] {response.text[:400]}...")
            raise Exception("FreeImage.host returned an HTML challenge/block page.")
            
        data = response.json()
        print(f"[DEBUG] [Parsed JSON Response] {data}")
        
        if response.status_code == 200 and data.get("status_code") == 200:
            image_url = data.get("image", {}).get("url")
            print(f"[DEBUG] Successfully uploaded to FreeImage.host. URL: {image_url}")
            return image_url
            
        raise Exception(f"Upload rejected: {data}")
        
    except Exception as e:
        print(f"[DEBUG] [Error] Exception encountered: {e}")
        raise

def upload_to_imgbb(image_path, public_id=None, folder=None):
    # Build the exact curl command that you know works in your terminal
    cmd = [
        "curl", "-s", "-X", "POST",
        "https://api.imgbb.com/1/upload",
        "-F", f"key={IMGBB_API_KEY}",
        "-F", f"image=@{image_path}"
    ]
    
    if public_id:
        cmd.extend(["-F", f"name={public_id}"])

    try:
        # Run curl and capture the output
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=120
        )
        
        response_data = json.loads(result.stdout)

        if response_data.get("success"):
            return response_data["data"]["display_url"]

        error_msg = response_data.get("error", {}).get("message", "Unknown error")
        raise Exception(f"ImgBB upload failed: {error_msg}")
        
    except subprocess.TimeoutExpired:
        raise Exception("ImgBB curl subprocess timed out.")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Curl process failed: {e.stderr}")
    
def upload_to_postimages_account(image_path_or_bytes, account_key="375d65b31ef5453eb9652cc870e769e9"):
    """
    Uploads an image to Postimages using an official account API key.
    """
    # Official Postimages API endpoint
    url = "https://api.postimages.org/" # or your specific account API endpoint provided in your dashboard
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }
    
    # Account authentication payload
    data = {
        "key": account_key,
        "expire": "0",  # 0 = never expire
        "link": "direct"
    }

    if isinstance(image_path_or_bytes, (str, os.PathLike)):
        files = {"file": open(image_path_or_bytes, "rb")}
    else:
        files = {"file": ("image.jpg", image_path_or_bytes)}

    try:
        response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        
        if isinstance(image_path_or_bytes, (str, os.PathLike)):
            files["file"].close()

        if response.status_code == 200:
            print(response.text)
            res_json = response.json()
            # Returns the direct image URL from the official API response
            return res_json.get("url") or res_json.get("image", {}).get("url")
        else:
            raise Exception(f"HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"[Error] Postimages account upload failed: {e}")
        return None
import time

def upload_to_postimages_with_key(image_path_or_bytes, api_key="268fdcc1ff5406aa50f3545e759e2a47", max_retries=3):
    """
    Uploads an image to Postimages using your account API key/token.
    Accepts either a local file path (str) or raw image bytes.
    """
    url = "https://postimages.org/json"
    
    headers = {
        "User-Agent": "Postimage Uploader",
        "Referer": "https://postimages.org/",
        "Origin": "https://postimages.org"
    }
    
    data = {
        "token": api_key,
        "version": "2.0",
        "app": "desktop",
        "numfiles": "1",
        "mode": "php",
        "link": "direct",
        "expire": "0",
        "ui": "1"
    }

    try:
        # 1. Load and compress image into memory once to keep file size tiny (<150KB)
        if isinstance(image_path_or_bytes, (str, os.PathLike)):
            img = Image.open(image_path_or_bytes)
        else:
            img = Image.open(BytesIO(image_path_or_bytes))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        max_width = 1200
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=85)
        
        # 2. Retry loop to handle transient VPN socket drops/timeouts
        for attempt in range(1, max_retries + 1):
            try:
                output_buffer.seek(0)
                files = {"file": ("card_image.jpg", output_buffer, "image/jpeg")}

                # Generous timeout: 15s to establish socket, 90s for write/read stream over VPN
                response = requests.post(
                    url, 
                    headers=headers, 
                    data=data, 
                    files=files, 
                    timeout=(15, 90)
                )

                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "xml" in content_type or response.text.strip().startswith("<?xml"):
                        print(f"[Error] Postimages version block on attempt {attempt}: {response.text[:100]}")
                        return None
                        
                    res_json = response.json()
                    if res_json.get("status") == "success":
                        return res_json.get("url")  # Success! Returns direct image URL
                    else:
                        print(f"[Error] Postimages API rejected upload: {res_json}")
                        return None
                else:
                    print(f"[Warning] HTTP {response.status_code} on attempt {attempt}. Retrying...")
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                if attempt < max_retries:
                    print(f"[Warning] Network timeout/drop on attempt {attempt}/{max_retries}. Retrying in 2s...")
                    time.sleep(2)
                else:
                    print(f"[Error] Postimages upload failed after {max_retries} attempts due to network timeout.")
                    raise net_err

    except Exception as e:
        print(f"[Error] Upload process failed: {e}")
        
    return None

def upload_to_postimages(image_path_or_bytes):
    """
    Uploads an image to Postimages and returns the direct image URL.
    Accepts either a file path (str) or raw image bytes.
    """
    url = "https://postimages.org/json"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Referer": "https://postimages.org/",
        "Origin": "https://postimages.org"
    }
    
    # Payload fields required by Postimages backend session
    data = {
        "upload_session": "",
        "numfiles": "1",
        "mode": "php",
        "link": "direct",
        "expire": "0",  # 0 means never expire
        "ui": "1",
        "optsize": "0"
    }

    # Handle file path vs raw bytes input
    if isinstance(image_path_or_bytes, (str, os.PathLike)):
        files = {"file": open(image_path_or_bytes, "rb")}
    else:
        files = {"file": ("image.jpg", image_path_or_bytes)}

    try:
        response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        
        # Ensure file handle is closed if opened from path
        if isinstance(image_path_or_bytes, (str, os.PathLike)):
            files["file"].close()

        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                return res_json.get("url")  # Direct hotlink URL
            else:
                raise Exception(f"Postimages upload rejected: {res_json}")
        else:
            raise Exception(f"HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"[Error] Postimages upload failed: {e}")
        return None
    
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

def upload_to_telegraph(image_path):
    url = "https://telegra.ph/upload"
    with open(image_path, "rb") as f:
        response = requests.post(url, files={"file": ("image.jpg", f, "image/jpeg")})
    data = response.json()
    if isinstance(data, list) and "src" in data[0]:
        return f"https://telegra.ph{data[0]['src']}"
    raise Exception(f"Telegraph upload failed: {data}")

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
            group.listing_id = ebay.publish_inventory_group(group.group_key, access_token)
            #if group.listing_datetime
            group.save()
    return group.listing_id

def withdraw(card, and_delete=True):
    
    settings = Settings.get_default()
    if not ebay.has_user_consent(settings):
        raise Exception("Missing user consent for eBay Operations")

    # 1. Fetch the authentication token ONCE for the entire batch lifecycle
    access_token = None
    access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
    offer_id = card.listed_card_info.offer_id
    print(f"Withdraw {card.id} {card.listed_card_info.offer_id}")
    success = ebay.withdraw_offer(offer_id, access_token)
    if success:
        #Do the internal unpublishing here so that even if ebay fails to delete the offer we still withdraw
        card.unlist()
        if and_delete:
            success = ebay.delete_offer(offer_id, access_token)
    return success
   
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

                print(listed_info.sku)
                #print(item_data)
                #print(offer_data)
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

                #check for an existing offer_id to re-use to skip item/offer creation
                if listed_info.offer_id:
                    offer_id = listed_info.offer_id
                    status = 201
                else:

                    # Create the item and offer on eBay
                    if ebay.create_inventory_item(listed_info.sku, item_data, access_token):
                        print("Offer data: ", offer_data)
                        offer_id, status = ebay.get_or_create_offer(offer_data, access_token, listed_info.sku)
                        
                        if status == 201:
                            listed_info.offer_id = offer_id
                        else:
                            listed_info.listing_id = ""
                            offer_id = None
                    else:
                        results_summary["success_count"] += 1
                        offer_id = None
                        # Fallback recovery strategy matching your original blueprint rules
                        #ebay.get_inventory_group(group_key, settings, access_token)

                if offer_id:#item and offer successfully created

                    # Branch logic handling: Single standalone items publish immediately
                    if not group_key or group_key == "-1":
                        listed_info.listing_id = ebay.publish_offer(offer_id, access_token)
                        if listed_info.listing_id is None:
                            raise Exception("eBay offer failed to publish.")
                        listed_info.listing_datetime = timezone.now()            
                        csr.overall_status = StatusBase.LISTED
                        csr.save()
                        ListingStatus.create(listed_info, listed_info.list_qty, StatusBase.LISTED, 0, True)
                        results_summary["success_count"] += 1
                        results_summary["details"].append({
                            "csr_id": csr_id,
                            "status": "PUBLISHED",
                            "offer_id": listed_info.offer_id,
                            "listing_id": listed_info.listing_id
                        })
                        
                        csr.save()
                        print(f"✅ Successfully published standalone CSR ID {csr_id} to eBay")
                    
                    else:
                        # Hold this validated item back for the final batch variation grouping call
                        successful_group_csrs.append(csr)
                        print(f"📦 Staged CSR ID {csr_id} for batch group listing processing")
                        
                    # Persist synchronized updates back to local db
                    csr.save()
                    listed_info.save()

        except Exception as e:
            results_summary["failed_count"] += 1
            results_summary["details"].append({
                "csr_id": csr_id,
                "status": "FAILED",
                "error": str(e)
            })
            csr.overall_status = StatusBase.FAILED
            csr.save()
            print(f"❌ Failed to process CSR ID {csr_id}: {str(e)}")
            #if we have an access_token epiration, go get it again
            try: 
                if e.args[0].find("access") >= 0:
                    access_token = ebay.get_access_token(settings, settings.ebay_user_auth_code)
            except Exception:
                pass

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
                    card_listed_info = csr.parent_card.listed_card_info
                    card_listed_info.listing_id = batch_listing_id
                    group_listed_info = card_listed_info.assigned_product_group.listed_products_info.filter(is_pg=True).first()
                    group_listed_info.listing_id = batch_listing_id
                    csr.overall_status = StatusBase.LISTED
                    csr.save()
                    ListingStatus.create(card_listed_info, card_listed_info.list_qty, StatusBase.LISTED, 0, True)
                    card_listed_info.save()
                    group_listed_info.save()

                    results_summary["success_count"] += 1
                    results_summary["details"].append({
                        "csr_id": csr.id,
                        "status": "GROUP_PUBLISHED",
                        "offer_id": listed_info.offer_id,
                        "listing_id": batch_listing_id
                    })
            print(f"🚀 Batch grouping complete! eBay Listing ID: {batch_listing_id}")
            #extra save
            #print("extra save?")
            #if successful_group_csrs:
            #print("extra save")
            #successful_group_csrs[0].parent_card.listed_card_info.assigned_product_group.listed_products_info.filter(is_pg=True).first().save()
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