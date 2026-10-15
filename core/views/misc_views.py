import asyncio
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dateutil import parser

from django.shortcuts import render
from django.utils import timezone
from django.conf import settings as django_settings
from core.models.ProductGroup import ProductGroup
from core.models.ProductListing import ProductListing
from core.models.CardSearchResult import CardSearchResult
from services.models.models import Settings

# --- 1. SELF-CONTAINED ASYNC SCRAPER ---

async def download_image(context, img_url: str, save_path: str) -> bool:
    try:
        print(f"[DEBUG] Downloading image from: {img_url}")
        response = await context.request.get(img_url)
        if response.status == 200:
            with open(save_path, "wb") as f:
                f.write(await response.body())
            print(f"[DEBUG] Successfully downloaded image to {save_path}")
            return True
        else:
            print(f"[WARNING] Image download returned status {response.status} for {img_url}")
    except Exception as e:
        print(f"[WARNING] Image download failed: {e}")
    return False

async def scrape_marketplace(query: str, city: str, download_dir: str) -> list[dict]:
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.facebook.com/marketplace/{city}/search/?query={encoded_query}"

    os.makedirs(download_dir, exist_ok=True)
    results = []

    print("[DEBUG] Launching Playwright browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print(f"[DEBUG] Navigating to search URL: {url}")
            await page.goto(url, wait_until="networkidle", timeout=45000)

            # Scroll search results to ensure enough items load
            for i in range(3):
                print(f"[DEBUG] Scrolling search page iteration {i+1}...")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(2000)

            html_content = await page.content()
        except Exception as e:
            print(f"[ERROR] Playwright execution failed on search page: {e}")
            await browser.close()
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        item_cards = soup.find_all("a", href=lambda href: href and "/marketplace/item/" in href)
        print(f"[DEBUG] Found {len(item_cards)} raw Marketplace item cards in DOM.")

        # Collect item links and basic info from aria-label on the search page
        target_listings = []
        for card in item_cards[:5]:  # Processing top 15 results
            raw_href = card.get("href")
            if not raw_href:
                continue
                
            item_url = raw_href if raw_href.startswith("https") else f"https://www.facebook.com{raw_href.split('?')[0]}"
            id_match = re.search(r"/item/(\d+)", item_url)
            listing_id = id_match.group(1) if id_match else None

            if not item_url or any(t['url'] == item_url for t in target_listings):
                continue

            # Extract basic info from aria-label
            aria_label = card.get("aria-label", "")
            print(f"[DEBUG] Parsing card aria-label: {aria_label}")
            
            title = "N/A"
            price = "N/A"
            location = "N/A"
            
            if aria_label:
                price_match = re.search(r"([\$€£]\s*[\d,]+\.?\d*)", aria_label)
                if price_match:
                    price = price_match.group(1).strip()
                
                loc_match = re.search(r"([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})", aria_label)
                if loc_match:
                    location = loc_match.group(1).strip()
                
                cleaned_title = aria_label
                if price != "N/A":
                    cleaned_title = cleaned_title.replace(price, "")
                if location != "N/A":
                    cleaned_title = cleaned_title.replace(location, "")
                for prefix in ["Price:", "Title:", "Location:", "Listed in"]:
                    cleaned_title = cleaned_title.replace(prefix, "")
                title = cleaned_title.strip(" .,-") or "N/A"

            target_listings.append({
                "url": item_url, 
                "id": listing_id,
                "title": title,
                "price": price,
                "location": location
            })

        # Process each listing by navigating to its detail page for description and images
        for index, item_info in enumerate(target_listings):
            item_url = item_info["url"]
            listing_id = item_info["id"] or f"item_{index}"
            title = item_info["title"]
            price = item_info["price"]
            location = item_info["location"]
            
            print(f"[DEBUG] --- Processing Detail Page {index+1}/{len(target_listings)} (ID: {listing_id}) ---")

            detail_page = await context.new_page()
            try:
                print(f"[DEBUG] Navigating to detail page: {item_url}")
                await detail_page.goto(item_url, wait_until="domcontentloaded", timeout=35000)
                await detail_page.wait_for_timeout(3500)  # Wait for dynamic React content load

                detail_html = await detail_page.content()
                detail_soup = BeautifulSoup(detail_html, "html.parser")

                # 1. EXTRACT DESCRIPTION
                description = "N/A"
                og_desc = detail_soup.find("meta", property="og:description")
                if og_desc and og_desc.get("content"):
                    description = og_desc["content"]

                print(f"[DEBUG] Parsed Detail Page -> Title: '{title}' | Price: '{price}' | Location: '{location}'")

                # 2. EXTRACT IMAGES
                all_listing_images = []
                detail_imgs = detail_soup.find_all("img")
                for img in detail_imgs:
                    src = img.get("src") or img.get("data-src") or img.get("srcset")
                    if src and ("scontent" in src or "fbcdn" in src):
                        clean_src = src.split(" ")[0]
                        if clean_src not in all_listing_images:
                            all_listing_images.append(clean_src)

                print(f"[DEBUG] Extracted {len(all_listing_images)} photos from detail page.")

                # 3. DOWNLOAD IMAGES
                local_image_paths = []
                for img_idx, img_url in enumerate(all_listing_images):
                    suffix = f"_{img_idx + 1}" if img_idx > 0 else ""
                    local_filename = f"{listing_id}{suffix}.jpg"
                    target_download_path = os.path.join(download_dir, local_filename)

                    print(f"[DEBUG] Downloading image {img_idx + 1} of {len(all_listing_images)}...")
                    success = await download_image(context, img_url, target_download_path)

                    if success:
                        local_image_paths.append(os.path.join('scraped_images', local_filename))

                img_url = all_listing_images[0] if len(all_listing_images) > 0 else None
                img_url_2 = all_listing_images[1] if len(all_listing_images) > 1 else None
                img_url_3 = all_listing_images[2] if len(all_listing_images) > 2 else None
                local_img_path = local_image_paths[0] if len(local_image_paths) > 0 else None

                results.append({
                    "listing_id": listing_id,
                    "title": title,
                    "price": price,
                    "location": location,
                    "description": description,
                    "url": item_url,
                    "img_url": img_url,
                    "img_url_2": img_url_2,
                    "img_url_3": img_url_3,
                    "all_images": all_listing_images,
                    "local_image_path": local_img_path,
                    "local_image_paths": local_image_paths
                })

            except Exception as detail_err:
                print(f"[WARNING] Failed to extract details for {item_url}: {detail_err}")
            finally:
                await detail_page.close()

        await browser.close()
        print(f"[DEBUG] Scrape complete. Returning {len(results)} structured items.")
    return results

# --- 2. SYNCHRONOUS DJANGO VIEW WITH MODEL CREATION ---

def test_view(request):
    results = None
    search_term = request.GET.get('q', '').strip()
    source = request.GET.get('source', 'ebay').strip().lower()

    try:
        hours_until_end = int(request.GET.get('hours', '24'))
    except ValueError:
        hours_until_end = 24

    if search_term:
        if source == 'facebook':
            # --- FACEBOOK MARKETPLACE ---
            city = request.GET.get('location', 'nyc').strip().lower()
            media_folder = os.path.join(django_settings.MEDIA_ROOT, 'scraped_images')

            print(f"[DEBUG] Executing scrape for term: '{search_term}' in city '{city}'...")
            scraped_items = asyncio.run(scrape_marketplace(
                query=search_term,
                city=city,
                download_dir=media_folder
            ))

            results = []
            print(f"[DEBUG] Instantiating ProductListing objects in database...")
            for item in scraped_items:
                try:
                    url = item.get("url", "")
                    id_match = re.search(r"/item/(\d+)", url)
                    item_id = id_match.group(1) if id_match else "FB_N/A"

                    listing = ProductListing.objects.filter(item_id=item_id).first()

                    if not listing:
                        listing = ProductListing.from_facebook_results(
                            item=item,
                            tokenize=False
                        )
                        print(f"[DEBUG] Saved new ProductListing: ID {listing.item_id}")
                    else:
                        print(f"[DEBUG] Duplicate skipped: ID {item_id} is already in database")

                    # --- SAFE ATTACHMENT: Dynamically attach secondary images and local paths ---
                    local_paths = item.get("local_image_paths", [])
                    listing.local_image_paths = local_paths
                    listing.img_url_2 = local_paths[1] if len(local_paths) > 1 else item.get("img_url_2")
                    listing.img_url_3 = local_paths[2] if len(local_paths) > 2 else item.get("img_url_3")

                    results.append(listing)
                except Exception as db_err:
                    print(f"[ERROR] Failed to save scraped item to DB: {db_err}")

        else:
            # --- EBAY ---
            try:
                settings = Settings.get_default()
                formatted_keywords = [(search_term, {"source": "user_web_query"})]

                search_response = ebay.auction_search(
                    keyword_strings=formatted_keywords,
                    settings=settings,
                    hours_until_end=hours_until_end,
                    limit=50,
                    page=1
                )

                if search_term in search_response:
                    metadata, items_list = search_response[search_term]
                    results = items_list

                    now = timezone.now()
                    for item in results:
                        end_time_str = item.get('itemEndDate') or item.get('endDate')
                        if end_time_str:
                            try:
                                end_time = parser.isoparse(end_time_str)
                                time_diff = end_time - now
                                if time_diff.total_seconds() > 0:
                                    hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                                    minutes, _ = divmod(remainder, 60)
                                    item['countdown_text'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                                else:
                                    item['countdown_text'] = "Ended"
                            except Exception:
                                item['countdown_text'] = "Ending Soon"
                else:
                    results = []
            except Exception as e:
                print(f"[ERROR] eBay search failed: {e}")
                results = []

    context = {
        'results': results,
        'search_term': search_term,
        'hours_until_end': hours_until_end,
        'source': source,
    }
    return render(request, 'ebay_auction_finder.html', context)