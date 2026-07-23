import os
import time
import random
import fcntl
import subprocess
import urllib.parse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class CardScraper130pt:
    def __init__(self, user_data_dir="/home/dcrown/.config/google-chrome-130pt", exe_path="/usr/bin/google-chrome"):
        self.base_url = "https://130point.com/cards/"
        self.user_data_dir = user_data_dir
        self.exe_path = exe_path
        self.lock_file_path = os.path.join(self.user_data_dir, "runner_130pt.lock")
        self.port = 9225  # Using a distinct port to avoid conflicts with other scripts
        
        os.makedirs(self.user_data_dir, exist_ok=True)

    def scrape_comps(self, keyword_strings):
        """Launches a vanilla Chrome process, forces tabs to load inside the profile
        using a native system launch to bypass Cloudflare, then harvests card comps.
        """
        result_data = {}
        
        print("\n=== STARTING 130PT AUTOMATION RUN ===")
        print("Target Keywords Array:", keyword_strings)
        
        with open(self.lock_file_path, "w") as lock_f:
            print("Acquiring script runner file lock...")
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            
            # Clean up stale crash locks
            singleton_lock = os.path.join(self.user_data_dir, "SingletonLock")
            if os.path.exists(singleton_lock):
                try:
                    os.remove(singleton_lock)
                except OSError:
                    pass

            # Spin up the native browser shell
            chrome_cmd = [
                self.exe_path,
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={self.user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            
            print(f"Spawning native Chrome instance on port {self.port}...")
            chrome_process = subprocess.Popen(
                chrome_cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            # Give the window manager a moment to initialize the socket
            time.sleep(2.0)
            
            print("Connecting Playwright interface layer...")
            try:
                with sync_playwright() as p:
                    browser = None
                    for attempt in range(1, 11):
                        try:
                            browser = p.chromium.connect_over_cdp(f"http://localhost:{self.port}")
                            print(f"[+] Playwright attached successfully on attempt {attempt}.")
                            break
                        except Exception:
                            if attempt == 10:
                                raise RuntimeError("CDP socket connection timed out.")
                            time.sleep(1.0)
                    
                    context = browser.contexts[0]
                    if not context.pages:
                        context.new_page()
                        
                    for index, keyword_item in enumerate(keyword_strings):
                        current_search = keyword_item[0]
                        tracking_id = keyword_item[1]
                        
                        # Encode search term to construct 130point hash query parameters
                        encoded_query = urllib.parse.quote(current_search)
                        url = f"{self.base_url}#search={encoded_query}"
                        
                        print(f"\n--- Processing Item: {current_search} ---")
                        print(f"[+] Launching native URL target context via process thread...")
                        
                        # Pass the URL directly to the native browser process binary.
                        # This tricks Cloudflare into seeing a normal user click or bookmark launch.
                        subprocess.Popen([
                            self.exe_path,
                            f"--user-data-dir={self.user_data_dir}",
                            url
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        print("Waiting for page loop to route target URL configuration...")
                        time.sleep(4.0)
                        
                        # Identify the correct open tab running our target domain
                        target_page = None
                        for open_page in context.pages:
                            if "130point.com" in open_page.url:
                                target_page = open_page
                                break
                                
                        if not target_page:
                            print("[!] Execution loop missed the target window context tab.")
                            target_page = context.pages[-1]
                            
                        try:
                            print(f"Locked onto active tab URL: {target_page.url}")
                            print("Waiting for dynamic sales comps data table to render...")
                            
                            # 130pt heavily relies on dynamic JS table generations.
                            # We look for the main search output block, tables, or row data containers.
                            target_page.wait_for_selector("#search-results, table, tbody tr", timeout=60000)
                            print("[+] Comps data elements rendered onto screen successfully.")
                            
                            # Random organic delay to simulate a human scrolling down to check values
                            time.sleep(random.uniform(2.5, 5.0))
                            
                            html_content = target_page.content()
                            result_data[current_search] = (tracking_id, self._parse_130pt_table(html_content))
                            
                            # Close the processed tab so the browser doesn't bloat memory resources
                            if len(context.pages) > 1:
                                target_page.close()
                                
                        except Exception as e:
                            print(f"[!] Data table resolution failure or timeout: {e}")
                            result_data[current_search] = (tracking_id, [])
                            
                    browser.close()
                    
            finally:
                print("\nShutting down 130pt background Chrome layers...")
                chrome_process.terminate()
                chrome_process.wait()
                print("Execution scope complete. Environment lock dropped.\n")
                
        return result_data

    def _parse_130pt_table(self, html_content):
        """Parses the loaded HTML content extracted from the 130pt data stream
        to capture sold dates, listing descriptions, and final actual sale prices.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        extracted_comps = []
        
        # Look for table data rows inside the search layout
        rows = soup.select("table tbody tr, tr.sold-row")
        print(f"Parser Engine located {len(rows)} raw transaction data points.")
        
        for row in rows:
            try:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                    
                # Standard column mapping on typical comp search tools:
                # Often: [Date, Image/Platform, Title/Link, Price]
                title_node = row.select_one("a.listing-title, td a, .title")
                title = title_node.text.strip() if title_node else ""
                url = title_node["href"] if title_node and title_node.has_attr("href") else ""
                
                # Fallback to parsing raw text cells if structured layout selectors shift
                if not title and cells:
                    title = cells[1].text.strip()
                
                price_node = row.select_one(".price, .sold-price, strong")
                price = price_node.text.strip() if price_node else ""
                if not price and len(cells) >= 3:
                    price = cells[-1].text.strip()
                    
                date_node = row.select_one(".date, .sold-date")
                date_str = date_node.text.strip() if date_node else ""
                if not date_str and cells:
                    date_str = cells[0].text.strip()
                
                if title and price:
                    extracted_comps.append({
                        "date": date_str,
                        "title": title,
                        "price": price,
                        "url": url
                    })
            except Exception:
                continue
                
        return extracted_comps

if __name__ == "__main__":
    scraper = CardScraper130pt()
    
    # Example targets: Player details and tracking identity tags
    targets = [
        ("2022 Bowman Chrome Elly De La Cruz PSA 10", 3001),
        ("2011 Topps Update Mike Trout Rookie", 3002)
    ]
    
    dataset = scraper.scrape_comps(targets)
    print("\nFinal Aggregated 130pt Dataset Map:\n", dataset)