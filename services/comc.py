import os
import time
import random
import subprocess
import urllib.parse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class COMCFullPipelineAutomator:
    def __init__(self, user_data_dir="/home/dcrown/.config/google-chrome-scraper", exe_path="/usr/bin/google-chrome"):
        self.base_url = "https://www.comc.com"
        self.user_data_dir = user_data_dir
        self.exe_path = exe_path
        self.port = 9222
        
        os.makedirs(self.user_data_dir, exist_ok=True)

    def execute_automated_run(self, keyword_strings):
        """Simulates the terminal execution by spinning up Chrome with preloaded 
        target links, waiting for layout stabilization, and harvesting data via CDP.
        """
        all_scraped_data = []
        
        # Guard against stale instance locks inside the custom profile directory
        singleton_lock = os.path.join(self.user_data_dir, "SingletonLock")
        if os.path.exists(singleton_lock):
            try:
                os.remove(singleton_lock)
            except OSError:
                pass

        # --- PHASE 1: BUILD THE EXACT TERMINAL LAUNCH COMMAND ---
        chrome_cmd = [
            self.exe_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        
        # Natively append the target URLs directly to the terminal command arguments
        print("\n=== PHASE 1: GENERATING PRELOADED BROWSER COMMAND ===")
        for current_search, _ in keyword_strings:
            encoded_query = urllib.parse.quote_plus(current_search)
            target_url = f"{self.base_url}/cards,={encoded_query}"
            chrome_cmd.append(target_url)
            print(f"[+] Injecting target query URL: {target_url}")
            
        print(f"\n[+] Spawning background process shell...")
        chrome_process = subprocess.Popen(
            chrome_cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        # Dynamic, safety-first delay window.
        # Increased baseline pause to 20 seconds to give complex media assets, 
        # multi-tab thread allocations, and heavy cloudflare verification grids
        # absolute breathing room to load into a settled DOM state.
        print("[!] Pausing 20 seconds to allow comprehensive visual loading sequence...")
        time.sleep(20.0)

        # --- PHASE 2: ATTACH PLAYWRIGHT POST-INITIALIZATION ---
        print("\n=== PHASE 2: CONNECTING AUTOMATION BRIDGE ===")
        try:
            with sync_playwright() as p:
                print(f"[+] Connecting Playwright to debugging socket 127.0.0.1:{self.port}...")
                browser = p.chromium.connect_over_cdp(f"http://localhost:{self.port}")
                context = browser.contexts[0]
                active_pages = context.pages
                
                print(f"[+] Active bridge established. Found {len(active_pages)} open windows/tabs.")
                
                comc_tabs_found = 0
                for idx, page in enumerate(active_pages):
                    current_url = page.url
                    
                    if "comc.com" in current_url.lower():
                        comc_tabs_found += 1
                        print(f"\n[Tab {idx}] Processing isolated data target: {current_url}")
                        
                        try:
                            # Extract the full raw DOM state off the viewport
                            html_content = page.content()
                            
                            if "/card/" in current_url.lower():
                                parsed_items = self._parse_single_card(html_content, current_url)
                            else:
                                parsed_items = self._parse_grid_layout(html_content)
                                
                            all_scraped_data.extend(parsed_items)
                            
                        except Exception as e:
                            print(f"      [!] Layout parsing extraction failure on tab {idx}: {e}")
                            
                browser.close()
        except Exception as e:
            print(f"[!] Critical automation sync failure: {e}")
        finally:
            # --- PHASE 3: TEARDOWN PROCESS CLEANLY ---
            print("\n=== PHASE 3: SHUTTING DOWN BROWSER ENVIRONMENT ===")
            chrome_process.terminate()
            chrome_process.wait()
            print("[+] Process scope terminated cleanly.")
            
        return all_scraped_data

    def _parse_grid_layout(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        extracted_rows = []
        items = soup.select(".cardInfoWrapper")
        print(f"      -> Parser extracted {len(items)} trading cards from grid.")
        
        for item in items:
            try:
                card_data = item.select_one(".carddata")
                if not card_data: continue
                
                title_node = card_data.select_one("h3.title")
                title = title_node.text.strip() if title_node else "Unknown Card"
                
                price_node = card_data.select_one(".listprice")
                price = price_node.text.strip() if price_node else "$0.00"
                
                link_node = title_node.find("a", href=True) if title_node else item.find("a", href=True)
                card_url = self.base_url + link_node["href"] if link_node else ""
                
                img_node = item.find("img")
                img_url = img_node.get("src") or img_node.get("data-src") if img_node else ""
                
                extracted_rows.append({
                    "id": card_url.rstrip("/").split("/")[-1] if card_url else "",
                    "title": title,
                    "price": price,
                    "url": card_url,
                    "thumbnail": img_url
                })
            except Exception:
                continue
        return extracted_rows

    def _parse_single_card(self, html_content, page_url):
        soup = BeautifulSoup(html_content, "html.parser")
        try:
            title_node = soup.select_one("h1, title")
            title = title_node.text.replace(" - COMC", "").strip() if title_node else "Direct Catalog Item"
            price_node = soup.select_one(".buy-panel .price, .asking-price, .price")
            price = price_node.text.strip() if price_node else "$0.00"
            img_node = soup.select_one("#main-card-img, .card-image img")
            img_url = img_node.get("src") if img_node else ""
            
            print("      -> Parser matched single catalog page item layout.")
            return [{
                "id": page_url.rstrip("/").split("/")[-1],
                "title": title,
                "price": price,
                "url": page_url,
                "thumbnail": img_url
            }]
        except Exception:
            return []

if __name__ == "__main__":
    automator = COMCFullPipelineAutomator()
    
    # Input targets array matching your database tracking signature maps
    targets = [
        ("2022 Bowman Chrome Elly De La Cruz", 2001),
        ("2023 Bowman Chrome Corbin Carroll", 2002)
    ]
    
    final_dataset = automator.execute_automated_run(targets)
    
    print("\n--- FINAL AGGREGATED PIPELINE OUTPUT MAP ---")
    for row in final_dataset:
        print(row)