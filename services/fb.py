import asyncio
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

async def download_image(context, img_url: str, save_path: str) -> bool:
    """
    Downloads an image using Playwright's built-in API request context.
    """
    try:
        # Use context.request to fetch the binary image data
        response = await context.request.get(img_url)
        if response.status == 200:
            image_bytes = await response.body()
            with open(save_path, "wb") as f:
                f.write(image_bytes)
            return True
    except Exception as e:
        print(f"[WARNING] Failed to download image {img_url}: {e}")
    return False

async def scrape_marketplace(query: str, city: str = "nyc", max_scrolls: int = 5, download_dir: str = "scraped_images") -> list[dict]:
    """
    Scrapes public Facebook Marketplace listings and downloads their main images.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.facebook.com/marketplace/{city}/search/?query={encoded_query}"
    
    # Ensure the output image directory exists
    os.makedirs(download_dir, exist_ok=True)
    
    results = []
    
    print("[DEBUG] Launching browser instance...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print(f"[DEBUG] Navigating to: {url}")
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"[ERROR] Timeout or navigation error: {e}")
            await browser.close()
            return []

        try:
            await page.wait_for_selector('div[role="feed"]', timeout=3000)
        except Exception:
            print("[WARNING] Could not find explicit feed container. Scraping raw layout...")

        # Scroll to load listings
        for i in range(max_scrolls):
            print(f"[DEBUG] Scrolling page (Step {i+1}/{max_scrolls})...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await page.wait_for_timeout(2000)

        html_content = await page.content()
        
        print("[DEBUG] Parsing HTML payload and preparing downloads...")
        soup = BeautifulSoup(html_content, "html.parser")
        item_cards = soup.find_all("a", href=lambda href: href and "/marketplace/item/" in href)
        print(f"[DEBUG] Found {len(item_cards)} raw item anchors.")

        for index, card in enumerate(item_cards):
            try:
                raw_href = card.get("href")
                item_url = raw_href if raw_href.startswith("https") else f"https://www.facebook.com{raw_href.split('?')[0]}"
                
                # Extract Listing ID from URL to generate a clean, unique file name
                id_match = re.search(r"/item/(\d+)", item_url)
                listing_id = id_match.group(1) if id_match else f"item_{index}"
                
                img_tag = card.find("img")
                img_url = img_tag.get("src") if img_tag else None
                
                text_spans = [span.get_text().strip() for span in card.find_all("span") if span.get_text()]
                if not text_spans:
                    continue
                    
                filtered_spans = [t for t in text_spans if t not in ("Free", "Ships to you", "New")]
                
                price, title, location = "N/A", "N/A", "N/A"
                price_index = next((i for i, val in enumerate(filtered_spans) if "$" in val), None)
                
                if price_index is not None:
                    price = filtered_spans[price_index]
                    if len(filtered_spans) > price_index + 1:
                        title = filtered_spans[price_index + 1]
                    if len(filtered_spans) > price_index + 2:
                        location = filtered_spans[price_index + 2]
                else:
                    price = filtered_spans[0] if len(filtered_spans) > 0 else "N/A"
                    title = filtered_spans[1] if len(filtered_spans) > 1 else "N/A"
                    location = filtered_spans[2] if len(filtered_spans) > 2 else "N/A"

                if any(item["url"] == item_url for item in results):
                    continue

                # Download image if URL exists
                local_img_path = None
                if img_url:
                    local_img_filename = f"{listing_id}.jpg"
                    local_img_path = os.path.join(download_dir, local_img_filename)
                    print(f"[DOWNLOAD] Fetching image for: {title[:30]}...")
                    success = await download_image(context, img_url, local_img_path)
                    if not success:
                        local_img_path = None

                results.append({
                    "title": title,
                    "price": price,
                    "location": location,
                    "url": item_url,
                    "image_url": img_url,
                    "local_image_path": local_img_path
                })
                
            except Exception as e:
                print(f"[DEBUG] Error parsing card index {index}: {e}")
                continue

        await browser.close()

    print(f"[DEBUG] Finished extraction. Total processed: {len(results)}")
    return results

if __name__ == "__main__":
    search_query = "topps baseball cards box"
    target_dir = "card_images"
    
    print(f"Starting Scraper for: '{search_query}'...")
    scraped_data = asyncio.run(
        scrape_marketplace(query=search_query, city="boston", max_scrolls=3, download_dir=target_dir)
    )
    
    print("\n--- Scrape & Download Summary ---")
    for idx, item in enumerate(scraped_data[:5]):
        print(f"{idx+1}. {item['title']} - {item['price']}")
        print(f"   Image saved to: {item['local_image_path']}")