import asyncio
import logging
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dateutil import parser

from django.shortcuts import render
from django.utils import timezone
from django.conf import settings as django_settings
from core.models.ListingGroup import ProductListing
from core.models.CardSearchResult import CardSearchResult

logger = logging.getLogger(__name__)

# --- 1. SELF-CONTAINED ASYNC SCRAPER ---

async def download_image(context, img_url: str, save_path: str) -> bool:
    try:
        logger.info(f"[DEBUG] Downloading image from: {img_url}")
        response = await context.request.get(img_url)
        if response.status == 200:
            with open(save_path, "wb") as f:
                f.write(await response.body())
            return True
    except Exception as e:
        logger.warning(f"[WARNING] Image download failed: {e}")
    return False


async def scrape_marketplace(query: str, city: str, download_dir: str) -> list[dict]:
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.facebook.com/marketplace/{city}/search/?query={encoded_query}"
    
    os.makedirs(download_dir, exist_ok=True)
    results = []
    
    logger.info("[DEBUG] Launching Playwright browser...")
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
            logger.info(f"[DEBUG] Navigating to: {url}")
            await page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Fast, 2-step scroll
            for i in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(1500)
                
            html_content = await page.content()
        except Exception as e:
            logger.error(f"[ERROR] Playwright execution failed: {e}")
            await browser.close()
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        item_cards = soup.find_all("a", href=lambda href: href and "/marketplace/item/" in href)
        
        for index, card in enumerate(item_cards[:15]): # Fast-limit to top 15 results
            try:
                raw_href = card.get("href")
                item_url = raw_href if raw_href.startswith("https") else f"https://www.facebook.com{raw_href.split('?')[0]}"
                
                id_match = re.search(r"/item/(\d+)", item_url)
                listing_id = id_match.group(1) if id_match else f"item_{index}"
                
                img_tag = card.find("img")
                img_url = img_tag.get("src") if img_tag else None
                
                text_spans = [span.get_text().strip() for span in card.find_all("span") if span.get_text()]
                filtered_spans = [t for t in text_spans if t not in ("Free", "Ships to you", "New")]
                if not filtered_spans:
                    continue
                
                price = filtered_spans[0] if len(filtered_spans) > 0 else "N/A"
                title = filtered_spans[1] if len(filtered_spans) > 1 else "N/A"
                location = filtered_spans[2] if len(filtered_spans) > 2 else "N/A"

                # Image Download
                local_img_path = None
                if img_url:
                    local_filename = f"{listing_id}.jpg"
                    # We store it inside 'scraped_images' within your MEDIA folder
                    local_img_path = os.path.join(download_dir, local_filename)
                    success = await download_image(context, img_url, local_img_path)
                    
                    # Convert to a relative media path for the Django Model field 
                    # (e.g., 'scraped_images/12345.jpg')
                    if success:
                        local_img_path = os.path.join('scraped_images', local_filename)
                    else:
                        local_img_path = None

                results.append({
                    "title": title,
                    "price": price,
                    "location": location,
                    "url": item_url,
                    "image_url": img_url,
                    "local_image_path": local_img_path
                })
            except Exception as card_err:
                logger.warning(f"[DEBUG] Error parsing card {index}: {card_err}")
                
        await browser.close()
        
    return results


# --- 2. SYNCHRONOUS DJANGO VIEW WITH MODEL CREATION ---

def test_view(request):
    logger.info("--- [DEBUG] Entering test_view ---")
    
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
            
            # 1. Resolve physical media output path
            media_folder = os.path.join(django_settings.MEDIA_ROOT, 'scraped_images')
            
            # 2. Scrape raw data
            logger.info(f"[DEBUG] Executing scrape for term: '{search_term}'...")
            scraped_items = asyncio.run(scrape_marketplace(
                query=search_term,
                city=city,
                download_dir=media_folder
            ))
            
            # 4. Transform scraped dictionaries into saved database objects
            results = []
            logger.info(f"[DEBUG] Instantiating ProductListing objects in database...")
            for item in scraped_items:
                try:
                    # Check if listing already exists to prevent duplicate entries
                    url = item.get("url", "")
                    id_match = re.search(r"/item/(\d+)", url)
                    item_id = id_match.group(1) if id_match else "FB_N/A"
                    
                    listing = ProductListing.objects.filter(item_id=item_id).first()
                    
                    if not listing:
                        # Instantiate using your custom classmethod
                        listing = ProductListing.from_facebook_results(
                            item=item,
                            tokenize=False
                        )
                        logger.info(f"[DEBUG] Saved new ProductListing: ID {listing.item_id}")
                    else:
                        logger.info(f"[DEBUG] Duplicate skipped: ID {item_id} is already in database")
                    
                    results.append(listing)
                except Exception as db_err:
                    logger.error(f"[ERROR] Failed to save scraped item to DB: {db_err}", exc_info=True)

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
                logger.error(f"[ERROR] eBay search failed: {e}", exc_info=True)
                results = []

    context = {
        'results': results,
        'search_term': search_term,
        'hours_until_end': hours_until_end,
        'source': source,
    }
    return render(request, 'ebay_auction_finder.html', context)