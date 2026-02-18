#!/usr/bin/env python3
"""
Gmail Follow-up Tool
Automatically follows up on emails in your Gmail Sent folder using Playwright.
"""

import asyncio
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Try to import yaml
try:
    import yaml
except ImportError:
    yaml = None
    print("⚠ Warning: PyYAML not installed. Install with: pip install PyYAML")

GENERIC_NAME_TOKENS = {
    "there",
    "friend",
    "friends",
    "everyone",
    "everybody",
    "beauty",
    "beautiful",
    "queen",
    "love",
    "lovely",
    "babe",
    "babes",
    "bestie",
    "besties",
    "fam",
    "sis",
    "hun",
    "honey",
    "yall",
    "ya'll",
    "you",
    "unknown",
    "me",  # Filter out "me" as it's not a valid username
    "a17",  # Filter out company name
    "a17.so",  # Filter out company domain
}

USERNAME_REGEXES = [
    re.compile(r"(?:hey|hi|hello|heyyy|hiya|yo|sup)\s+@?([a-z0-9_.'’-]{2,})", re.IGNORECASE),
    re.compile(r"\bhiya\s+@?([a-z0-9_.'’-]{2,})", re.IGNORECASE),
    re.compile(r"(?:^|[\s,;])@([a-z0-9_.'’-]{2,})", re.IGNORECASE),
    re.compile(r"^([a-z0-9_.'’-]{2,})\s*[,–—-]", re.IGNORECASE),
]

class GmailFollowUp:
    def __init__(
        self,
        followup_days: int = 5,
        headless: bool = False,
        use_arc: bool = False,
        arc_debug_port: int = 9222,
        profile: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize the Gmail Follow-up tool.
        
        Args:
            followup_days: Number of days to wait before following up (default: 5)
            headless: Run browser in headless mode (default: False)
            use_arc: Connect to existing Arc browser instead of launching new one
            arc_debug_port: Remote debugging port for Arc browser
            profile: Sender profile to use (e.g., "pretti")
            config_path: Path to config.yaml file
        """
        self.followup_days = followup_days
        self.headless = headless
        self.use_arc = use_arc
        self.arc_debug_port = arc_debug_port
        self.profile_name = profile
        self.config_path = config_path or Path(__file__).parent / "config.yaml"
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.profile_config: Dict[str, str] = {}
        self.sent_search_query = 'in:sent PAID PROMO OPPORTUNITY - Pretti App -label:"pretti responses"'
        self._sent_search_initialized = False
        self._last_search_query: Optional[str] = None
        self._in_thread_view = False
        self._is_paginating = False  # Flag to prevent re-search during pagination
        self.followup_markers: Dict[int, List[str]] = {}
        
        # Load profile config
        self._load_profile_config()
        self._refresh_followup_markers()
        
    async def start_browser(self):
        """Start or connect to browser."""
        playwright = await async_playwright().start()
        
        if self.use_arc:
            # Connect to existing Arc browser
            print(f"Connecting to Arc browser on port {self.arc_debug_port}...")
            try:
                self.browser = await playwright.chromium.connect_over_cdp(
                    f"http://localhost:{self.arc_debug_port}"
                )
                print("✓ Connected to Arc browser")
                
                # When connecting via CDP, try to use existing context or create new one
                contexts = self.browser.contexts
                if contexts:
                    # Use the first existing context
                    self.context = contexts[0]
                    print("✓ Using existing browser context")
                else:
                    # Create a new context
                    self.context = await self.browser.new_context()
                    print("✓ Created new browser context")
                    
            except Exception as e:
                print(f"✗ Failed to connect to Arc: {e}")
                print("Make sure Arc is running with remote debugging enabled.")
                print("Run: ./launch_arc_debug.sh or:")
                print("     open -a Arc --args --remote-debugging-port=9222")
                print("Falling back to regular Chromium...")
                self.browser = await playwright.chromium.launch(headless=self.headless)
                self.context = await self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
        else:
            # Launch new browser
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=["--start-maximized"] if not self.headless else []
            )
            # Create a new context with realistic settings
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        
        # Get or create a page
        pages = self.context.pages
        if pages:
            # Use existing page if available
            self.page = pages[0]
        else:
            # Create a new page
            self.page = await self.context.new_page()
    
    def _load_profile_config(self):
        """Load sender profile configuration from config.yaml"""
        if not yaml:
            print("⚠ Warning: YAML not available. Using default profile.")
            self.profile_config = {
                "from_name": "Advaith",
                "app_name": "Pretti",
                "link_url": "https://apps.apple.com/us/app/pretti-ai-makeup-assistant/id6749188903",
            }
            return
        
        try:
            if not os.path.exists(self.config_path):
                print(f"⚠ Config file not found at {self.config_path}, using defaults")
                self.profile_config = {
                    "from_name": "Advaith",
                    "app_name": "Pretti",
                    "link_url": "https://apps.apple.com/us/app/pretti-ai-makeup-assistant/id6749188903",
                }
                return
            
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            profiles = config.get('profiles', {})
            default_profile = config.get('default_profile', 'pretti')
            
            # Determine which profile to use
            profile_key = (self.profile_name or default_profile).lower()
            
            if profile_key not in profiles:
                print(f"⚠ Profile '{profile_key}' not found in config. Available: {list(profiles.keys())}")
                print(f"   Using default profile: {default_profile}")
                profile_key = default_profile
            
            self.profile_config = profiles.get(profile_key, {})
            print(f"✓ Using sender profile: {profile_key}")
            print(f"   From: {self.profile_config.get('from_name', 'Unknown')}")
            print(f"   App: {self.profile_config.get('app_name', 'Unknown')}")
            
        except Exception as e:
            print(f"⚠ Error loading config: {e}")
            print("   Using default profile")
            self.profile_config = {
                "from_name": "Advaith",
                "app_name": "Pretti",
                "link_url": "https://apps.apple.com/us/app/pretti-ai-makeup-assistant/id6749188903",
            }
        
        self._refresh_followup_markers()
        
    def _refresh_followup_markers(self):
        """Build key phrases we can use to detect which templates already appear in a thread."""
        app_name = self.profile_config.get('app_name', 'pretti').lower()
        from_name = self.profile_config.get('from_name', 'advaith').lower()
        
        self.followup_markers = {
            1: [
                f"following up on my email about the {app_name}",
                "makes that guidance tangible",
            ],
            2: [
                "hope you're doing well! just wanted to follow up one more time",
                "it meaningfully serves your audience's confidence and routines",
                "let me know either way",
            ],
            3: [
                "this is my final follow-up",
                "if you're interested, great! if not, no worries at all - i'll stop reaching out.",
                "just leaving this here because your audience would genuinely benefit",
                "thanks for your time!",
            ],
        }
    
    async def _fast_message_area_lookup(self):
        """
        Quickly locate Gmail's message body by targeting its standard selectors first.
        Returns the locator if found, otherwise None.
        """
        if not self.page:
            return None
        
        fast_selectors = [
            'div[aria-label="Message Body"][contenteditable="true"]',
            'div[role="textbox"][aria-label="Message Body"]',
            'div[role="textbox"][aria-label*="Message"]',
            'div[contenteditable="true"][aria-label*="Message"]',
            'div[role="textbox"][g_editable="true"]',
        ]
        
        for selector in fast_selectors:
            locator = self.page.locator(selector)
            try:
                count = await locator.count()
            except Exception:
                continue
            if count == 0:
                continue
            candidate = locator.last
            try:
                await candidate.wait_for(state="visible", timeout=1500)
                return candidate
            except Exception:
                continue
        
        return None
        
    def _is_in_sent_list_view(self) -> bool:
        """
        Check if we're looking at the Sent/search results list (not inside a thread).
        Gmail shows filtered results under #search when a query is active, so treat those
        URLs as valid as long as we're not drilled into a specific thread.
        """
        if self._in_thread_view:
            return False
        if not self.page:
            return False
        url = (self.page.url or "").lower()
        # If URL contains "thread/" followed by a thread ID, we're in thread view
        if re.search(r'thread/[a-f0-9]+', url):
            return False
        if "#" not in url:
            return False
        fragment = url.split("#", 1)[1]
        # Remove query parameters for checking
        fragment_base = fragment.split("?")[0]
        if fragment_base.startswith("sent"):
            return True
        if fragment_base.startswith("search/"):
            # Allow search URLs that don't have thread IDs
            return "/" not in fragment_base[len("search/"):]
        return False
    
    async def _return_to_sent_list(self):
        """Return to the Sent/search list view using Gmail's back controls if a thread is open."""
        if not self._in_thread_view:
            return
        
        back_clicked = False
        try:
            back_clicked = await self.page.evaluate("""
                (() => {
                    const selectors = [
                        'div[aria-label*="Back to Inbox" i]',
                        'div[aria-label*="Back to Sent" i]',
                        'div[aria-label*="Back to search results" i]',
                        'div[aria-label="Back"]',
                        'button[aria-label*="Back" i]'
                    ];
                    for (const selector of selectors) {
                        const el = document.querySelector(selector);
                        if (el && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                })();
            """)
            if back_clicked:
                await asyncio.sleep(2)
        except Exception:
            back_clicked = False
        
        if not back_clicked:
            try:
                await self.page.go_back()
                await asyncio.sleep(2)
                back_clicked = True
            except Exception:
                back_clicked = False
        
        self._in_thread_view = False
        
        # Only navigate to sent folder if we're NOT in the middle of pagination
        # During pagination, the back button should return us to the current page
        if not self._is_in_sent_list_view() and not self._is_paginating:
            await self.go_to_sent_folder()
        
    async def navigate_to_gmail(self):
        """Navigate to Gmail and wait for login if needed."""
        print("Navigating to Gmail...")
        # Gmail doesn't reach networkidle, so use domcontentloaded
        try:
            await self.page.goto("https://mail.google.com", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"⚠ Navigation warning: {e}, continuing anyway...")
        await asyncio.sleep(2)
        
        # Check if we need to log in
        if "accounts.google.com" in self.page.url:
            print("⚠ Please log in to Gmail in the browser window...")
            print("Waiting for you to complete login...")
            # Wait for redirect to Gmail
            await self.page.wait_for_url("https://mail.google.com/**", timeout=120000)
            print("✓ Login detected, proceeding...")
        else:
            print("✓ Already logged in to Gmail")
        
        await asyncio.sleep(2)
        
    async def go_to_sent_folder(self, force_search: bool = False):
        """Navigate to the Sent folder and verify we're there."""
        need_navigation = not self._is_in_sent_list_view()
        
        if need_navigation:
            print("Going to Sent folder...")
            
            # First, try direct URL navigation (most reliable)
            try:
                await self.page.goto("https://mail.google.com/mail/u/0/#sent", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)  # Give Gmail time to load emails
                
                # Verify we're actually in sent folder
                current_url = self.page.url
                if "#sent" in current_url.lower():
                    print("✓ Navigated to Sent folder (via URL)")
                    
                    # Wait a bit more and verify the page shows sent emails
                    await asyncio.sleep(2)
                    
                    # Check if we can see sent email rows
                    sent_rows = await self.page.evaluate("""
                        () => document.querySelectorAll('tr[role="row"]:has(td)').length
                    """)
                    
                    if sent_rows > 0:
                        print(f"✓ Confirmed: Found {sent_rows} email rows in Sent folder")
                    else:
                        print("⚠ Warning: No email rows found, but URL is correct")
                else:
                    print(f"⚠ Warning: URL doesn't contain #sent: {current_url}")
            except Exception as e:
                print(f"⚠ URL navigation warning: {e}, trying other methods...")
            
            # Fallback: Try clicking on Sent link in sidebar
            sent_selectors = [
                'a[href*="#sent"]',
                'a[aria-label*="Sent" i]',
                'a[title*="Sent" i]',
                'div[role="navigation"] a:has-text("Sent")',
            ]
            
            for selector in sent_selectors:
                try:
                    sent_link = self.page.locator(selector).first
                    if await sent_link.is_visible(timeout=5000):
                        await sent_link.click()
                        await asyncio.sleep(3)
                        current_url = self.page.url
                        if "#sent" in current_url.lower():
                            print("✓ Navigated to Sent folder (via click)")
                            await asyncio.sleep(2)
                            break
                except Exception as e:
                    continue
        
        should_search = (
            force_search
            or need_navigation
            or not self._sent_search_initialized
            or (self._last_search_query or "").lower() != self.sent_search_query.lower()
        )
        
        if should_search:
            await self.search_emails(self.sent_search_query)
        
        self._in_thread_view = False
    
    async def search_emails(self, search_query: str):
        """Search for emails using Gmail's search bar."""
        print(f"Searching for: {search_query}...")
        
        try:
            # Find the search box - Gmail has multiple possible selectors
            search_selectors = [
                'input[aria-label*="Search" i]',
                'input[placeholder*="Search" i]',
                'input[type="text"][name="q"]',
                'input[aria-label="Search mail"]',
                'input[aria-label="Search"]',
                'input[placeholder="Search mail"]',
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = self.page.locator(selector).first
                    if await search_box.is_visible(timeout=3000):
                        break
                except:
                    continue
            
            if not search_box:
                # Try using keyboard shortcut to focus search (Cmd+K or /)
                await self.page.keyboard.press("Meta+k")
                await asyncio.sleep(1)
                # Try to find the search box again after keyboard shortcut
                for selector in search_selectors:
                    try:
                        search_box = self.page.locator(selector).first
                        if await search_box.is_visible(timeout=2000):
                            break
                    except:
                        continue
            
            if search_box:
                # Clear any existing text and type the search query
                await search_box.click()
                await asyncio.sleep(0.5)
                await search_box.fill("")  # Clear first
                await search_box.fill(search_query)
                await asyncio.sleep(0.5)
                
                # Press Enter to search
                await search_box.press("Enter")
                await asyncio.sleep(3)  # Wait for search results to load
                
                print(f"✓ Search completed: {search_query}")
                
                # Verify we have results
                email_count = await self.page.evaluate("""
                    () => document.querySelectorAll('tr[role="row"]:has(td), tbody tr[role="row"]').length
                """)
                print(f"✓ Found {email_count} emails matching search")
                self._sent_search_initialized = True
                self._last_search_query = search_query.lower()
                
            else:
                print("⚠ Could not find search box, trying JavaScript method...")
                # Fallback: Use JavaScript to find and use search box
                search_done = await self.page.evaluate(f"""
                    (() => {{
                        // Try to find search input
                        const searchInputs = document.querySelectorAll('input[type="text"], input[aria-label*="Search" i]');
                        for (let input of searchInputs) {{
                            if (input.offsetParent !== null) {{ // visible
                                input.focus();
                                input.value = '{search_query}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                                input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                                return true;
                            }}
                        }}
                        return false;
                    }})()
                """)
                
                if search_done:
                    await asyncio.sleep(3)
                    print(f"✓ Search completed via JavaScript: {search_query}")
                    self._sent_search_initialized = True
                    self._last_search_query = search_query.lower()
                else:
                    print("⚠ Warning: Could not perform search, proceeding with all sent emails")
                    
        except Exception as e:
            print(f"⚠ Search error: {e}, proceeding with all sent emails")
        
    async def load_more_emails(self, target_count: int):
        """
        Load more emails in Gmail by scrolling and clicking "Load more" buttons.
        
        Args:
            target_count: Target number of emails to load
        """
        print(f"Loading emails (target: {target_count})...")
        
        max_attempts = 5  # Only 5 scroll attempts
        attempts = 0
        last_count = 0
        stable_count = 0
        
        while attempts < max_attempts:
            # Get current email count using JavaScript (faster)
            current_count = await self.page.evaluate("""
                () => document.querySelectorAll('tr[role="row"]:has(td), tbody tr[role="row"]').length
            """)
            
            if current_count >= target_count:
                print(f"   ✓ Loaded {current_count} emails")
                break
            
            # Check if count changed
            if current_count == last_count:
                stable_count += 1
                
                # If count hasn't changed, try clicking "Load more" button
                if stable_count >= 2:
                    # Look for "Load more" button using JavaScript
                    clicked = await self.page.evaluate("""
                        (() => {
                            const buttons = Array.from(document.querySelectorAll('div[role="button"], button, span'));
                            for (let btn of buttons) {
                                const text = btn.innerText || btn.textContent || '';
                                const label = btn.getAttribute('aria-label') || '';
                                if (text.toLowerCase().includes('load more') || 
                                    text.toLowerCase().includes('show more') ||
                                    label.toLowerCase().includes('load more')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        })();
                    """)
                    
                    if clicked:
                        print(f"   Clicked 'Load more' button")
                        await asyncio.sleep(2)
                        stable_count = 0
                    elif stable_count >= 3:
                        print(f"   Reached end at {current_count} emails")
                        break
            else:
                stable_count = 0
            
            last_count = current_count
            
            # Scroll to trigger loading (if no button was clicked)
            if stable_count < 2:
                await self.page.evaluate("""
                    (() => {
                        const mainArea = document.querySelector('div[role="main"]');
                        if (mainArea) {
                            mainArea.scrollTop = mainArea.scrollHeight;
                        }
                        window.scrollTo(0, document.body.scrollHeight);
                    })();
                """)
                await asyncio.sleep(1.5)
            
            attempts += 1
            
            if attempts % 2 == 0:
                print(f"   Loaded {current_count} emails so far...")
        
        # Final count
        final_count = await self.page.evaluate("""
            () => document.querySelectorAll('tr[role="row"]:has(td), tbody tr[role="row"]').length
        """)
        print(f"   Final: {final_count} emails loaded")
        await asyncio.sleep(1)
    
    async def go_to_next_page(self) -> bool:
        """
        Click the next page arrow to load the next set of emails.
        Returns: True if successfully clicked next, False if no next button or on last page
        """
        try:
            # Find the next arrow button - Gmail uses various selectors
            selectors = [
                '[aria-label="Older"]',
                '[aria-label="Older conversations"]',
                '[aria-label="Next page"]',
                '[aria-label*="Less relevant" i]',
                '[data-tooltip="Older"]',
                '[data-tooltip="Less relevant"]',
                '[data-tooltip*="Older" i]',
                '[data-tooltip*="Less" i]',
                'div[role="button"][aria-label*="Older" i]',
                'span[role="button"][aria-label*="Older" i]',
                'button[aria-label*="Older" i]',
                'div.T-I[aria-label*="Older" i]',
                'span.T-I[aria-label*="Older" i]',
            ]
            next_clicked = False
            for sel in selectors:
                locator = self.page.locator(sel).first
                try:
                    count = await locator.count()
                except Exception:
                    continue
                if count == 0:
                    continue
                try:
                    await locator.wait_for(state="visible", timeout=1000)
                    await locator.click()
                    next_clicked = True
                    break
                except Exception:
                    continue
            
            if next_clicked:
                print("   → Clicked 'Next' arrow")
                await asyncio.sleep(3)  # Wait for next page to load
                return True
            else:
                return False
                
        except Exception as e:
            print(f"   ⚠ Error clicking next: {str(e)[:50]}")
            return False

    async def get_pagination_info(self) -> Optional[Dict[str, int]]:
        """
        Get pagination info (current range, total emails).
        Returns: {'current_start': 1, 'current_end': 50, 'total': 845} or None
        """
        try:
            pagination_info = await self.page.evaluate("""
                (() => {
                    // Look for pagination text like "1-50 of 845"
                    const text = document.body.innerText || document.body.textContent || '';
                    
                    // Match patterns like "1-50 of 845" or "1 – 50 of 845"
                    const match = text.match(/(\\d+)[\\s–-]+(\\d+)[\\s]+of[\\s]+(\\d+)/i);
                    if (match) {
                        return {
                            current_start: parseInt(match[1]),
                            current_end: parseInt(match[2]),
                            total: parseInt(match[3])
                        };
                    }
                    
                    // Also check in specific pagination elements
                    const paginationEls = document.querySelectorAll('[aria-label*="of" i], [title*="of" i]');
                    for (let el of paginationEls) {
                        const text = el.innerText || el.textContent || '';
                        const match = text.match(/(\\d+)[\\s–-]+(\\d+)[\\s]+of[\\s]+(\\d+)/i);
                        if (match) {
                            return {
                                current_start: parseInt(match[1]),
                                current_end: parseInt(match[2]),
                                total: parseInt(match[3])
                            };
                        }
                    }
                    
                    return null;
                })();
            """)
            
            return pagination_info
        except Exception as e:
            return None
        
    async def get_sent_emails(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get list of sent emails that might need follow-ups.
        Processes emails page by page, clicking "next" arrow when needed.
        
        Args:
            limit: Maximum number of emails to check
            
        Returns:
            List of email dictionaries with subject, recipient, date, etc.
        """
        if limit:
            print(f"Scanning up to {limit} sent emails...")
        else:
            print("Scanning ALL sent emails (no limit)...")
        
        emails = []
        cutoff_date = datetime.now() - timedelta(days=self.followup_days)
        
        # Wait for initial emails to load
        await asyncio.sleep(2)
        
        # Process emails page by page
        page_num = 1
        max_pages = 100  # Safety limit to prevent infinite loops
        processed_count = 0
        
        while page_num <= max_pages:
            print(f"\n📄 Processing page {page_num}...")
            
            # Get pagination info
            pagination = await self.get_pagination_info()
            if pagination:
                print(f"   Showing {pagination['current_start']}-{pagination['current_end']} of {pagination['total']}")
            
            # Wait for emails to load on current page
            await asyncio.sleep(2)
            
            # Get emails from current page
            limit_val = limit if limit else 999999
            sender_email = (self.profile_config.get("gmail_sender") or "").lower()
            email_data = await self.page.evaluate(
                r"""
                (args) => {
                    const mainArea = document.querySelector('div[role=\"main\"]') || document.body;
                    const rows = mainArea.querySelectorAll('tbody tr[role=\"row\"], tr[role=\"row\"]:has(td[role=\"gridcell\"])');
                    const emails = [];
                    const limit = args?.limit ?? 999999;
                    const maxRows = Math.min(rows.length, limit);
                    
                    for (let i = 0; i < maxRows; i++) {
                        const row = rows[i];
                        if (!row.querySelector('td')) continue;
                        
                        const text = row.innerText || row.textContent || '';
                        const cells = row.querySelectorAll('td');
                        if (cells.length < 2 || text.trim().length < 10) continue;
                        
                        let subject = '';
                        let maxLength = 0;
                        for (let cell of cells) {
                            const cellText = cell.innerText || '';
                            if (cellText.length > maxLength && 
                                !cellText.match(/^\d+[:]\d+\s*(AM|PM)$/i) &&
                                !cellText.match(/^\s*[★☆✓]\s*$/)) {
                                subject = cellText.trim();
                                maxLength = cellText.length;
                            }
                        }
                        if (!subject || subject.length < 5) {
                            for (let cell of cells) {
                                const cellText = cell.innerText || '';
                                if (cellText.trim().length > subject.length) {
                                    subject = cellText.trim();
                                }
                            }
                        }
                        
                        let dateText = '';
                        for (let cell of Array.from(cells).reverse()) {
                            const cellText = cell.innerText || '';
                            if (cellText.match(/\\d+[:]\\d+|AM|PM|ago|day|week|month|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct/i)) {
                                dateText = cellText.trim();
                                break;
                            }
                        }
                        
                        let recipient = '';
                        const emailMatch = text.match(/\[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\/);
                        if (emailMatch) {
                            recipient = emailMatch[0];
                        }
                        
                        const threadId = row.getAttribute('data-legacy-thread-id') || row.dataset?.legacyThreadId || '';
                        
                        let displayName = '';
                        const displaySelectors = [
                            '.yW span[email]',
                            '.yW span',
                            'span[email]',
                            '.bA4 span',
                            '.y2'
                        ];
                        for (const sel of displaySelectors) {
                            const el = row.querySelector(sel);
                            if (el && el.innerText && el.innerText.trim().length > 0) {
                                displayName = el.innerText.trim();
                                break;
                            }
                        }
                        
                        // Extract Gmail labels/tags
                        let labels = [];
                        const labelSelectors = [
                            '.ar', // Label chip class
                            '.at', // Another label class
                            '.aZ', // Label badge class
                            'span[aria-label*="Label:"]',
                            'div[aria-label*="Label:"]',
                            '.aZo', // Label container
                            '[data-label-name]'
                        ];
                        
                        for (const sel of labelSelectors) {
                            const labelEls = row.querySelectorAll(sel);
                            labelEls.forEach(el => {
                                const labelText = el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('data-label-name') || '';
                                if (labelText && labelText.trim()) {
                                    // Clean up label text (remove "Label:" prefix if present)
                                    let cleanLabel = labelText.trim().replace(/^Label:\s*/i, '');
                                    if (cleanLabel && !labels.includes(cleanLabel)) {
                                        labels.push(cleanLabel);
                                    }
                                }
                            });
                        }
                        
                        // Also check for labels in the row text directly
                        const labelPattern = /\[([^\]]+)\]/g;
                        let match;
                        while ((match = labelPattern.exec(text)) !== null) {
                            const labelText = match[1].trim();
                            if (labelText && !labels.includes(labelText)) {
                                labels.push(labelText);
                            }
                        }
                        
                        if (subject || text.trim().length > 10) {
                            emails.push({
                                index: i,
                                subject: subject.substring(0, 150) || '(no subject)',
                                recipient: recipient,
                                date_text: dateText,
                                row_text: text.substring(0, 300),
                                thread_id: threadId,
                                display_name: displayName,
                                labels: labels
                            });
                        }
                    }
                    return emails;
                }
                """,
                {"limit": limit_val},
            )
            # Process emails from current page
            page_emails_count = 0
            for email_info in email_data:
                try:
                    subject = email_info.get('subject', '').strip()
                    recipient = email_info.get('recipient', '').strip()
                    date_text = email_info.get('date_text', '').strip()
                    row_text = email_info.get('row_text', '').strip()
                    display_name = email_info.get('display_name', '').strip()
                    username_hint = (
                        self._extract_username_from_text(row_text)
                        or self._extract_username_from_text(subject)
                        or self._extract_username_from_text(display_name)
                    )
                    if not username_hint and recipient:
                        username_hint = self._sanitize_username(recipient.split("@")[0])
                    
                    email_date = self._parse_email_date(date_text)
                    if not email_date:
                        email_date = datetime.now() - timedelta(days=1)
                    
                    days_old = (datetime.now() - email_date).days if email_date else 0
                    
                    emails.append({
                        "recipient": recipient or "unknown",
                        "subject": subject or "(no subject)",
                        "date": email_date,
                        "date_text": date_text or "unknown",
                        "index": email_info['index'],
                        "days_old": days_old,
                        "page": page_num,  # Track which page this email came from
                        "username_hint": username_hint,
                        "thread_id": email_info.get('thread_id', '').strip(),
                        "display_name": display_name,
                        "labels": email_info.get('labels', []),  # Include labels/tags
                    })
                    processed_count += 1
                    page_emails_count += 1
                    
                    # Check if we've reached the limit
                    if limit and processed_count >= limit:
                        print(f"   ✓ Reached limit of {limit} emails")
                        break
                        
                except Exception as e:
                    continue
            
            print(f"   ✓ Found {page_emails_count} emails on page {page_num} (total: {processed_count})")
            
            # Check if we've reached the limit
            if limit and processed_count >= limit:
                break
            
            # Check if there's a next page
            if pagination:
                # If we're on the last page (current_end >= total), stop
                if pagination['current_end'] >= pagination['total']:
                    print(f"   ✓ Reached last page ({pagination['current_end']} of {pagination['total']})")
                    break
            
            # Try to go to next page
            has_next = await self.go_to_next_page()
            if not has_next:
                print(f"   ✓ No more pages available")
                break
            
            page_num += 1
        
        print(f"\n✓ Found {len(emails)} emails total across {page_num} page(s)")
        return emails
    
    def _parse_email_date(self, date_text: str) -> Optional[datetime]:
        """Parse Gmail date text into datetime object."""
        if not date_text:
            return None
            
        try:
            date_text = date_text.strip()
            date_lower = date_text.lower()
            
            # Handle relative dates FIRST
            if "minute" in date_lower or "hour" in date_lower or "just now" in date_lower:
                return datetime.now()
            
            if "day" in date_lower:
                days_match = re.search(r'(\d+)\s*days?', date_lower)
                if days_match:
                    days_ago = int(days_match.group(1))
                    return datetime.now() - timedelta(days=days_ago)
                if "yesterday" in date_lower:
                    return datetime.now() - timedelta(days=1)
                if "today" in date_lower:
                    return datetime.now()
            
            if "week" in date_lower:
                weeks_match = re.search(r'(\d+)\s*weeks?', date_lower)
                if weeks_match:
                    weeks_ago = int(weeks_match.group(1))
                    return datetime.now() - timedelta(weeks=weeks_ago)
            
            if "month" in date_lower:
                months_match = re.search(r'(\d+)\s*months?', date_lower)
                if months_match:
                    months_ago = int(months_match.group(1))
                    return datetime.now() - timedelta(days=months_ago * 30)
            
            # Try parsing absolute dates
            formats = [
                "%a, %b %d, %Y, %I:%M %p",  # "Sat, Nov 8, 2025, 6:27 PM"
                "%a, %b %d, %Y",            # "Mon, Dec 15, 2024"
                "%b %d, %Y, %I:%M %p",      # "Nov 8, 2025, 6:27 PM"
                "%b %d, %Y",                # "Dec 15, 2024"
                "%m/%d/%Y",                 # "12/15/2024"
                "%Y-%m-%d",                 # "2024-12-15"
                "%d %b %Y",                 # "15 Dec 2024"
                "%d %B %Y",                 # "15 December 2024"
            ]
            
            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_text, fmt)
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=datetime.now().year)
                    return parsed
                except:
                    continue
            
            # If we can't parse, assume it's old enough
            return datetime.now() - timedelta(days=self.followup_days + 10)
                
        except Exception as e:
            return datetime.now() - timedelta(days=self.followup_days + 10)
    
    def _sanitize_username(self, username: Optional[str]) -> Optional[str]:
        """Clean up extracted username/handle to avoid garbage values."""
        if not username:
            return None
        cleaned = (
            username.strip()
            .strip(",.!?;:\"'()[]{}<>")
            .replace("'", "'")
            .replace("`", "'")
        )
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"[^A-Za-z0-9_.'-]", "", cleaned)
        if not cleaned:
            return None
        if "@" in cleaned:
            return None
        if cleaned.lower() in GENERIC_NAME_TOKENS:
            return None
        
        # Reject domain-like patterns (contains dots and looks like a domain)
        if "." in cleaned:
            # Common TLDs that indicate this is a domain, not a username
            common_tlds = ['.com', '.net', '.org', '.io', '.so', '.co', '.app', '.dev', '.ai', '.me']
            cleaned_lower = cleaned.lower()
            for tld in common_tlds:
                if cleaned_lower.endswith(tld):
                    return None
            # If it has a dot and is short (likely a domain like "a17.so")
            if len(cleaned) <= 10 and "." in cleaned:
                return None
        
        # Reject patterns that look like email domains (e.g., "a17.so", "gmail.com")
        if re.match(r'^[a-z0-9]+\.(com|net|org|io|so|co|app|dev|ai|me)$', cleaned.lower()):
            return None
        
        if len(cleaned) < 2 or len(cleaned) > 30:
            return None
        return cleaned
    
    def _extract_username_from_text(self, text: Optional[str]) -> Optional[str]:
        """Try to pull a username/handle from a free-form text snippet."""
        if not text:
            return None
        for regex in USERNAME_REGEXES:
            match = regex.search(text)
            if match:
                candidate = self._sanitize_username(match.group(1))
                if candidate:
                    return candidate
        return None
    
    async def detect_followup_level(self, thread_id: str = "") -> Tuple[int, int, Optional[str]]:
        """Determine next follow-up level by scanning our prior messages in the thread."""
        sender_email = (self.profile_config.get("gmail_sender") or "").lower()
        sender_name = (self.profile_config.get("from_name") or "").lower()
        markers = {int(k): v for k, v in self.followup_markers.items()}
        
        try:
            messages = await self.page.evaluate(
                """
                (args) => {
                    const senderEmail = (args?.senderEmail || "").toLowerCase();
                    const senderName = (args?.senderName || "").toLowerCase();
                    const threadId = args?.threadId || "";
                    const normalize = (value) => (value || "").trim().toLowerCase();
                    const stripQuotes = (element) => {
                        if (!element) return "";
                        const clone = element.cloneNode(true);
                        clone.querySelectorAll('.gmail_quote, blockquote, .yj6qo, .adL').forEach(node => node.remove());
                        const text = (clone.innerText || clone.textContent || "").trim();
                        return text;
                    };
                    
                    const expanders = document.querySelectorAll('.ajT .ajV, .ajT span[role="link"], .ajT span[role="button"]');
                    expanders.forEach(btn => {
                        try { btn.click(); } catch (e) {}
                    });
                    
                    const mainArea = document.querySelector('div[role="main"]');
                    let threadArea = null;
                    if (threadId) {
                        threadArea = document.querySelector(`div[data-legacy-thread-id="${threadId}"]`);
                    }
                    if (!threadArea) {
                        threadArea = mainArea?.querySelector('div[role="list"], div[aria-label*="Conversation" i]');
                    }
                    if (!threadArea) {
                        threadArea = mainArea;
                    }
                    const threadSelectors = ['div[data-message-id]'];
                    let threadMessages = [];
                    if (threadArea) {
                        threadSelectors.forEach(sel => {
                            threadMessages = threadMessages.concat(Array.from(threadArea.querySelectorAll(sel)));
                        });
                    }
                    const seen = new Set();
                    const uniqueThreadMessages = [];
                    threadMessages.forEach(msg => {
                        if (msg && !seen.has(msg)) {
                            seen.add(msg);
                            uniqueThreadMessages.push(msg);
                        }
                    });
                    
                    return uniqueThreadMessages.map(msg => {
                        const senderEl = msg.querySelector('[email], span[email], .gD, .gB, .go, .gF');
                        const emailAttr = normalize(senderEl?.getAttribute('email')) || normalize(senderEl?.getAttribute('data-hovercard-id'));
                        const label = normalize(senderEl?.getAttribute('aria-label'));
                        const senderText = normalize(senderEl?.innerText);
                        
                        let fromMe = false;
                        if (senderEmail) {
                            if (emailAttr) {
                                fromMe = emailAttr === senderEmail;
                            } else if (label && label.includes(senderEmail)) {
                                fromMe = true;
                            } else if (senderText && senderText.includes(senderEmail)) {
                                fromMe = true;
                            }
                        }
                        
                        if (!fromMe && senderName) {
                            if (senderText && (senderText.includes(senderName) || senderText === "me")) {
                                fromMe = true;
                            } else if (label && label.includes(senderName)) {
                                fromMe = true;
                            }
                        }
                        
                    const text = stripQuotes(msg);
                        return { fromMe, text };
                    });
                }
                """,
                {"senderEmail": sender_email, "senderName": sender_name, "threadId": thread_id},
            )
            
            if not isinstance(messages, list) or not messages:
                messages = []
            
            if messages and not any(m.get("fromMe") for m in messages):
                messages[0]["fromMe"] = True
            
            # Count messages from us for debugging
            my_messages = [m for m in messages if m.get("fromMe")]
            
            highest_level = 0
            detected_name: Optional[str] = None
            # Process messages in reverse order (most recent first) to get name from latest follow-up
            for msg in reversed(messages):
                if not msg.get("fromMe"):
                    continue
                text = (msg.get("text") or "")
                text_lower = text.lower()
                # Extract name from this message (prioritize most recent)
                if not detected_name:
                    name_candidate = self._extract_username_from_text(text)
                    if name_candidate:
                        detected_name = name_candidate
                # Check for follow-up level markers
                for level in sorted(markers.keys(), reverse=True):
                    phrases = markers[level]
                    if any((phrase or "").lower() in text_lower for phrase in phrases):
                        highest_level = max(highest_level, level)
                        break
            
            if highest_level <= 0:
                next_level = 1
            elif highest_level == 1:
                next_level = 2
            elif highest_level == 2:
                next_level = 3
            else:
                next_level = 3
            
            return next_level, highest_level, detected_name
        
        except Exception as e:
            print(f"   ⚠ Could not detect follow-up level: {str(e)[:50]}, defaulting to level 1")
            return 1, 0, None

    async def process_email_fast(self, email: Dict, followup_templates: Dict[int, str]) -> Tuple[bool, Optional[str], int]:
        """
        Process one email: detect level, extract username, send follow-up.
        Returns: (success: bool, username: str or None, level: int)
        """
        email_index = email["index"]
        sender_email = (self.profile_config.get("gmail_sender") or "").lower()
        sender_name = (self.profile_config.get("from_name") or "").lower()
        result: Tuple[bool, Optional[str], int] = (False, None, 1)
        
        thread_id = (email.get("thread_id") or "").strip()

        try:
            # Verify we're still in sent folder before clicking
            # Skip this check during pagination as we're already in the right place
            if not self._is_paginating and not self._is_in_sent_list_view():
                print("   ⚠ Not in sent folder, navigating...")
                await self.go_to_sent_folder()
                await asyncio.sleep(2)
            
            # Step 1: Click on email - use JavaScript to ensure we're clicking sent emails from main area
            clicked = False
            if thread_id:
                clicked = await self.page.evaluate(
                    """
                    (threadId) => {
                        const selector = `tr[data-legacy-thread-id="${threadId}"]`;
                        const row = document.querySelector(selector);
                        if (row) {
                            row.scrollIntoView({block: 'center', behavior: 'auto'});
                            row.click();
                            return true;
                        }
                        return false;
                    }
                    """,
                    thread_id,
                )
            
            if not clicked:
                clicked = await self.page.evaluate(f"""
                    (() => {{
                        const mainArea = document.querySelector('div[role="main"]');
                        if (!mainArea) {{
                            return false;
                        }}
                        const rows = mainArea.querySelectorAll('tbody tr[role="row"]');
                        if (rows.length <= {email_index}) {{
                            return false;
                        }}
                        const row = rows[{email_index}];
                        if (!row || !row.querySelector('td')) {{
                            return false;
                        }}
                        row.scrollIntoView({{block: 'center', behavior: 'auto'}});
                        row.click();
                        return true;
                    }})();
                """)
            
            # Wait for email to open
            await asyncio.sleep(1)
            
            if not clicked:
                print("   ⚠ Could not click email row")
                return False, None, 1
            
            await asyncio.sleep(3)  # Wait longer for email thread to open
            self._in_thread_view = True
            try:
                await self.page.wait_for_selector('div[data-message-id], div[jsmodel][data-message-id]', timeout=7000)
            except:
                pass
            try:
                await self.page.wait_for_function(
                    """
                    () => {
                        const main = document.querySelector('div[role="main"]');
                        if (!main) return false;
                        const tableRows = main.querySelectorAll('tbody tr[role="row"]');
                        return tableRows.length === 0;
                    }
                    """,
                    timeout=7000,
                )
            except Exception:
                pass
            
            # Expand all collapsed messages in the thread before detecting level
            try:
                expanded = await self.page.evaluate(
                    """
                    () => {
                        let count = 0;
                        // Expand any collapsed messages
                        const expanders = document.querySelectorAll('.ajT .ajV, .ajT span[role="link"], .ajT span[role="button"], span[role="button"][aria-label*="Show trimmed"]');
                        expanders.forEach(btn => {
                            try { 
                                btn.click(); 
                                count++;
                            } catch (e) {}
                        });
                        return count;
                    }
                    """
                )
                if expanded > 0:
                    await asyncio.sleep(1.5)  # Wait for expansion to complete
            except:
                pass
            
            # Step 2: Detect follow-up level
            followup_level, followups_sent, detected_name = await self.detect_followup_level(thread_id)
            if followups_sent >= 3:
                print("   📊 Detected follow-up level: 3 (already sent final follow-up) — skipping thread")
                return False, None, followup_level
            print(f"   📊 Detected follow-up level: {followup_level}")
            
            # Step 3: Extract username intelligently - PRIORITIZE current email's subject/row text FIRST
            # This prevents reusing old usernames from previous follow-ups in the thread
            username = None
            
            # FIRST: Try to extract from the current email's subject/row text (most reliable)
            username_hint = email.get("username_hint")
            if username_hint:
                username = self._sanitize_username(username_hint)
            
            # SECOND: Try display name from the email row
            if not username:
                display_name = email.get("display_name", "")
                if display_name:
                    username = self._sanitize_username(display_name)
                    if not username:
                        username = self._extract_username_from_text(display_name)
                        username = self._sanitize_username(username)
            # THIRD: Try detected_name from detect_followup_level (might have old username)
            if not username:
                username = detected_name
                if username:
                    username = self._sanitize_username(username)
            
            # FOURTH: Try extracting from thread messages (last resort - might have old usernames)
            if not username:
                username = await self.page.evaluate(
            r"""
            (args) => {
                const senderEmail = (args?.senderEmail || "").toLowerCase();
                const senderName = (args?.senderName || "").toLowerCase();
                    const normalize = (value) => (value || "").trim().toLowerCase();
                    
                    const stripQuotes = (element) => {
                        if (!element) return "";
                        const clone = element.cloneNode(true);
                        clone.querySelectorAll('.gmail_quote, blockquote, .yj6qo, .adL').forEach(node => node.remove());
                        return clone.innerText || clone.textContent || "";
                    };
                    
                    const determineFromMe = (msg) => {
                        const senderEl = msg.querySelector('[email], span[email], .gD, .gB, .go, .gF');
                        const emailAttr = normalize(senderEl?.getAttribute('email')) || normalize(senderEl?.getAttribute('data-hovercard-id'));
                        const label = normalize(senderEl?.getAttribute('aria-label'));
                        const senderText = normalize(senderEl?.innerText);
                        
                        let fromMe = false;
                        if (senderEmail) {
                            if (emailAttr) {
                                fromMe = emailAttr === senderEmail;
                            } else if (label && label.includes(senderEmail)) {
                                fromMe = true;
                            } else if (senderText && senderText.includes(senderEmail)) {
                                fromMe = true;
                            }
                        }
                        if (!fromMe && senderName) {
                            if (senderText && (senderText.includes(senderName) || senderText === "me")) {
                                fromMe = true;
                            } else if (label && label.includes(senderName)) {
                                fromMe = true;
                            }
                        }
                        return fromMe;
                    };
                    
                    const scanTexts = (texts) => {
                        // Try multiple patterns to catch usernames
                        const patterns = [
                            /(?:hey|hi|hello|heyyy|hiya|yo|sup)\s+@?([a-z0-9_.''-]{2,})/i,
                            /^([a-z0-9_.''-]{2,})\s*[,–—-]/i,
                            /@([a-z0-9_.''-]{2,})/i,
                        ];
                        
                        // Helper to check if candidate looks like a domain
                        const isDomainLike = (candidate) => {
                            const lower = candidate.toLowerCase();
                            // Reject if it contains a dot and ends with common TLD
                            const commonTlds = ['.com', '.net', '.org', '.io', '.so', '.co', '.app', '.dev', '.ai', '.me'];
                            for (const tld of commonTlds) {
                                if (lower.endsWith(tld)) return true;
                            }
                            // Reject short strings with dots (likely domains like "a17.so")
                            if (candidate.includes('.') && candidate.length <= 10) return true;
                            // Reject domain patterns
                            if (/^[a-z0-9]+\.(com|net|org|io|so|co|app|dev|ai|me)$/i.test(candidate)) return true;
                            return false;
                        };
                        
                        for (const text of texts) {
                            if (!text) continue;
                            for (const pattern of patterns) {
                                const match = text.match(pattern);
                                if (match && match[1]) {
                                    const candidate = match[1].trim();
                                    // Filter out generic words and domain-like patterns
                                    const generic = ['me', 'there', 'you', 'friend', 'friends', 'everyone', 'everybody', 'a17', 'a17.so'];
                                    if (candidate && candidate.length >= 2 && 
                                        !generic.includes(candidate.toLowerCase()) &&
                                        !isDomainLike(candidate)) {
                                        return candidate;
                                    }
                                }
                            }
                        }
                        return null;
                    };
                    
                    const messages = Array.from(document.querySelectorAll('div[role="listitem"], div[data-message-id], div[jsmodel]'));
                    if (!messages.length) return null;
                    
                    const fromMeTexts = [];
                    const otherTexts = [];
                    
                    // Process messages in reverse order (most recent first)
                    for (let i = messages.length - 1; i >= 0; i--) {
                        const msg = messages[i];
                        const text = stripQuotes(msg);
                        if (!text) continue;
                        if (determineFromMe(msg)) {
                            fromMeTexts.push(text);
                        } else {
                            otherTexts.push(text);
                        }
                    }
                    
                    // Prioritize most recent follow-up (first in fromMeTexts since we reversed)
                    const name = scanTexts(fromMeTexts) || scanTexts(otherTexts);
                    return name ? name.trim() : null;
                }
                """,
                {"senderEmail": sender_email, "senderName": sender_name},
            )
                username = self._sanitize_username(username)
            
            # LAST RESORT: Try extracting from recipient email (but be careful - only if it looks like a real username)
            if not username:
                recipient = (email.get("recipient") or "").strip()
                if recipient:
                    email_local = recipient.split("@")[0]
                    # Only use email local part if it doesn't look like a domain/company name
                    # and is reasonable length (not too short, not too long)
                    if email_local and len(email_local) >= 3 and len(email_local) <= 25:
                        # Check if it's not obviously a domain-like pattern
                        if not re.match(r'^[a-z0-9]+\.(com|net|org|io|so|co|app|dev|ai|me)$', email_local.lower()):
                            username = self._sanitize_username(email_local)
                            # Double-check it's not a domain-like pattern after sanitization
                            if username and "." in username and len(username) <= 10:
                                username = None  # Reject short domain-like patterns
            
            if not username:
                username = "there"
                print("   ⚠ Could not determine username – defaulting to 'there'")
            else:
                print(f"   📝 Using username: {username}")
            
            # Get the appropriate template for this level
            followup_template = followup_templates.get(followup_level, followup_templates.get(1))
            
            # Step 3: Verify email thread opened and trigger reply
            # Wait for email thread to be visible (check for message content)
            try:
                # Wait for email content to appear
                await self.page.wait_for_selector('div[role="listitem"], div[data-message-id]', timeout=5000)
                print("   ✓ Email thread opened")
            except:
                print("   ⚠ Email thread may not have opened properly")
            
            # Wait a bit for thread to fully load
            await asyncio.sleep(0.7)
            
            # Step 4: Try to trigger reply - use multiple methods
            print("   Triggering reply...")
            reply_triggered = False
            
            # Method 1: Use JavaScript to find and click Reply button (more reliable)
            reply_clicked = await self.page.evaluate("""
                (() => {
                    // Look for reply button in multiple ways
                    const buttons = document.querySelectorAll('div[role="button"], button, span[role="button"]');
                    for (let btn of buttons) {
                        const ariaLabel = btn.getAttribute('aria-label') || '';
                        const text = btn.innerText || btn.textContent || '';
                        if (ariaLabel.toLowerCase().includes('reply') || 
                            text.toLowerCase().includes('reply')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })();
            """)
            
            if reply_clicked:
                print("   ✓ Clicked Reply button (JS)")
                reply_triggered = True
                await asyncio.sleep(0.8)
            else:
                # Method 2: Try Playwright locators
                try:
                    reply_buttons = [
                        'div[role="button"][aria-label*="Reply" i]',
                        'div[aria-label*="Reply" i]',
                        'button[aria-label*="Reply" i]',
                    ]
                    
                    for selector in reply_buttons:
                        try:
                            reply_btn = self.page.locator(selector).first
                            if await reply_btn.is_visible(timeout=3000):
                                await reply_btn.click()
                                print(f"   ✓ Clicked Reply button ({selector})")
                                reply_triggered = True
                                await asyncio.sleep(0.8)
                                break
                        except:
                            continue
                except Exception as e:
                    pass
            
            # Method 3: If button click didn't work, try keyboard shortcut
            if not reply_triggered:
                try:
                    # Click on the email thread area to ensure focus
                    await self.page.click('div[role="main"]')
                    await asyncio.sleep(0.3)
                    await self.page.keyboard.press("r")
                    print("   ✓ Pressed 'r' key")
                    reply_triggered = True
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"   ⚠ Keyboard shortcut failed: {str(e)[:30]}")
            
            if not reply_triggered:
                print("   ⚠ Could not trigger reply - trying to continue anyway")
                await asyncio.sleep(1)
            
            # Wait a bit for compose window to appear
            await asyncio.sleep(0.8)
            
            # Step 5: Find and fill compose window
            try:
                compose_window = None
                inline_reply = False
                message_area = await self._fast_message_area_lookup()
                
                if message_area:
                    print("   ✓ Found message area (fast lookup)")
                else:
                    # First, try to find compose window using JavaScript (faster)
                    dialog_found = await self.page.evaluate("""
                        (() => {
                            const dialogs = document.querySelectorAll('div[role="dialog"]');
                            return dialogs.length > 0;
                        })();
                    """)
                    
                    if dialog_found:
                        print("   ✓ Dialog found, waiting for it...")
                    
                    # Try multiple selectors for compose window - wait longer
                    compose_selectors = [
                        'div[role="dialog"]',
                        'div[aria-label*="Compose"]',
                        'div[aria-label*="Reply"]',
                        'div[aria-label*="New Message"]',
                    ]
                    
                    for selector in compose_selectors:
                        try:
                            compose_window = self.page.locator(selector).first
                            # Check if it's visible
                            if await compose_window.is_visible(timeout=5000):
                                print(f"   ✓ Found compose window with: {selector}")
                                break
                            # Or wait for it to become visible
                            await compose_window.wait_for(state="visible", timeout=5000)
                            print(f"   ✓ Compose window appeared with: {selector}")
                            break
                        except:
                            continue
                    
                    if not compose_window:
                        # Last resort: look for any dialog that might be compose
                        try:
                            dialogs = await self.page.locator('div[role="dialog"]').all()
                            if dialogs:
                                compose_window = dialogs[0]
                                if await compose_window.is_visible(timeout=3000):
                                    print("   ✓ Found compose window (fallback - first dialog)")
                        except:
                            pass
                    
                    if not compose_window:
                        # Try to find inline reply box (might be in the thread view)
                        try:
                            inline_areas = self.page.locator('div[role="main"] div[contenteditable="true"]').all()
                            if inline_areas:
                                # The last contenteditable in main area might be the reply box
                                for area in reversed(inline_areas):
                                    if await area.is_visible(timeout=2000):
                                        message_area = area
                                        inline_reply = True
                                        print("   ✓ Found inline reply box")
                                        break
                        except:
                            pass
                    
                    if not message_area and compose_window:
                        # Find message area in compose window/dialog
                        try:
                            # Try getting all contenteditable areas in compose window
                            areas = await compose_window.locator('div[contenteditable="true"]').all()
                            if areas:
                                # The message body is usually the last contenteditable
                                message_area = areas[-1]
                                await message_area.wait_for(state="visible", timeout=5000)
                                print("   ✓ Found message area in compose window")
                        except:
                            # Fallback: try direct selector
                            try:
                                message_area = compose_window.locator('div[contenteditable="true"]').last
                                await message_area.wait_for(state="visible", timeout=5000)
                                print("   ✓ Found message area (fallback)")
                            except:
                                pass
                    
                    if not message_area:
                        # Last resort: look for any visible contenteditable on the page that's large enough to be a message area
                        try:
                            all_areas = await self.page.locator('div[contenteditable="true"]').all()
                            for area in all_areas:
                                try:
                                    if await area.is_visible(timeout=1000):
                                        # Check if it's large enough to be a message area (not just a small input)
                                        box = await area.bounding_box()
                                        if box and box['height'] > 50:  # Message areas are usually taller
                                            message_area = area
                                            print("   ✓ Found message area (last resort - by size)")
                                            break
                                except:
                                    continue
                        except:
                            pass
                
                if not message_area:
                    # Debug: see what's on the page
                    page_info = await self.page.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('div[role="dialog"]');
                            const contenteditables = document.querySelectorAll('div[contenteditable="true"]');
                            const visibleCEs = Array.from(contenteditables).filter(el => {
                                const rect = el.getBoundingClientRect();
                                return rect.width > 0 && rect.height > 0;
                            });
                            return {
                                dialogCount: dialogs.length,
                                ceCount: contenteditables.length,
                                visibleCECount: visibleCEs.length,
                                hasCompose: document.querySelector('[aria-label*="Compose"]') !== null,
                                hasReply: document.querySelector('[aria-label*="Reply"]') !== null,
                            };
                        }
                    """)
                    print(f"   ⚠ Debug info: {page_info}")
                    raise Exception(f"Message area not found. Dialogs: {page_info.get('dialogCount', 0)}, ContentEditables: {page_info.get('visibleCECount', 0)}")
                
                # Wait a bit for message area to be ready
                await asyncio.sleep(0.5)
                
                # Format template with username
                formatted_message = self._format_template(followup_template, username, followup_level)
                
                # Fill message
                await message_area.fill(formatted_message)
                await asyncio.sleep(0.2)
                
                # Step 5: Send email
                await self.page.keyboard.press("Meta+Enter")
                await asyncio.sleep(0.4)
                
                # Step 6: Close compose/reply area
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
                await asyncio.sleep(0.2)
                
                result = (True, username, followup_level)
                return result
                
            except Exception as e:
                print(f"   ⚠ Compose error: {str(e)[:50]}")
                # Try to close anyway
                try:
                    await self.page.keyboard.press("Escape")
                except:
                    pass
                result = (False, None, followup_level)
                return result
            
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:50]}")
            try:
                await self.page.keyboard.press("Escape")
            except:
                pass
            result = (False, None, 1)
            return result
        
        finally:
            if self._in_thread_view:
                await self._return_to_sent_list()
        return result
    
    def _format_template(self, template: str, username: str, level: int = 1) -> str:
        """Format the follow-up template with variables."""
        app_name = self.profile_config.get('app_name', 'Pretti')
        from_name = self.profile_config.get('from_name', 'Advaith')
        link_url = self.profile_config.get('link_url', 'https://apps.apple.com/us/app/pretti-ai-makeup-assistant/id6749188903')
        
        formatted = template.replace('{username}', username)
        formatted = formatted.replace('{app_name}', app_name)
        formatted = formatted.replace('{from_name}', from_name)
        formatted = formatted.replace('{link_url}', link_url)
        
        return formatted
    
    async def run(self, followup_templates: Dict[int, str], dry_run: bool = False, max_emails: Optional[int] = None):
        """Run the follow-up process page by page."""
        try:
            await self.start_browser()
            await self.navigate_to_gmail()
            await self.go_to_sent_folder()
            
            if max_emails:
                print(f"Processing up to {max_emails} emails...")
            else:
                print(f"Processing ALL emails in Sent folder (page by page)...")
            
            # Process page by page
            sent_count = 0
            failed_count = 0
            skipped_count = 0  # Emails skipped due to tags
            total_processed = 0  # Total emails examined (including skipped)
            total_attempted = 0  # Emails actually attempted (excluding skipped)
            page_num = 1
            max_pages = 100  # Safety limit
            
            # Set pagination flag to prevent accidental re-search during email processing
            self._is_paginating = True
            
            while page_num <= max_pages:
                print(f"\n{'='*60}")
                print(f"📄 PAGE {page_num}")
                print(f"{'='*60}\n")
                
                # Get pagination info
                pagination = await self.get_pagination_info()
                if pagination:
                    print(f"   Gmail showing: {pagination['current_start']}-{pagination['current_end']} of {pagination['total']}")
                
                # Wait for emails to load on current page
                await asyncio.sleep(2)
                
                # Get emails from current page only
                sender_email = (self.profile_config.get("gmail_sender") or "").lower()
                email_data = await self.page.evaluate(
                    r"""
                    (args) => {
                        const mainArea = document.querySelector('div[role=\"main\"]') || document.body;
                        const rows = mainArea.querySelectorAll('tbody tr[role=\"row\"], tr[role=\"row\"]:has(td[role=\"gridcell\"])');
                        const emails = [];
                        
                        for (let i = 0; i < rows.length; i++) {
                            const row = rows[i];
                            if (!row.querySelector('td')) continue;
                            
                            const text = row.innerText || row.textContent || '';
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 2 || text.trim().length < 10) continue;
                            
                            let subject = '';
                            let maxLength = 0;
                            for (let cell of cells) {
                                const cellText = cell.innerText || '';
                                if (cellText.length > maxLength && 
                                    !cellText.match(/^\\d+[:]\\d+\\s*(AM|PM)$/i) &&
                                    !cellText.match(/^\\s*[★☆✓]\\s*$/)) {
                                    subject = cellText.trim();
                                    maxLength = cellText.length;
                                }
                            }
                            
                            let dateText = '';
                            for (let cell of Array.from(cells).reverse()) {
                                const cellText = cell.innerText || '';
                                if (cellText.match(/\\d+[:]\\d+|AM|PM|ago|day|week|month|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct/i)) {
                                    dateText = cellText.trim();
                                    break;
                                }
                            }
                            
                            let recipient = '';
                            const emailMatch = text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}/);
                            if (emailMatch) {
                                recipient = emailMatch[0];
                            }
                            
                            const threadId = row.getAttribute('data-legacy-thread-id') || row.dataset?.legacyThreadId || '';
                            
                            let displayName = '';
                            const displaySelectors = ['.yW span[email]', '.yW span', 'span[email]', '.bA4 span', '.y2'];
                            for (const sel of displaySelectors) {
                                const el = row.querySelector(sel);
                                if (el && el.innerText && el.innerText.trim().length > 0) {
                                    displayName = el.innerText.trim();
                                    break;
                                }
                            }
                            
                            // Extract Gmail labels/tags
                            let labels = [];
                            const labelSelectors = [
                                '.ar', // Label chip class
                                '.at', // Another label class
                                '.aZ', // Label badge class
                                'span[aria-label*="Label:"]',
                                'div[aria-label*="Label:"]',
                                '.aZo', // Label container
                                '[data-label-name]'
                            ];
                            
                            for (const sel of labelSelectors) {
                                const labelEls = row.querySelectorAll(sel);
                                labelEls.forEach(el => {
                                    const labelText = el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('data-label-name') || '';
                                    if (labelText && labelText.trim()) {
                                        // Clean up label text (remove "Label:" prefix if present)
                                        let cleanLabel = labelText.trim().replace(/^Label:\s*/i, '');
                                        if (cleanLabel && !labels.includes(cleanLabel)) {
                                            labels.push(cleanLabel);
                                        }
                                    }
                                });
                            }
                            
                            // Also check for labels in the row text directly
                            const labelPattern = /\[([^\]]+)\]/g;
                            let match;
                            while ((match = labelPattern.exec(text)) !== null) {
                                const labelText = match[1].trim();
                                if (labelText && !labels.includes(labelText)) {
                                    labels.push(labelText);
                                }
                            }
                            
                            if (subject || text.trim().length > 10) {
                                emails.push({
                                    index: i,
                                    subject: subject.substring(0, 150) || '(no subject)',
                                    recipient: recipient,
                                    date_text: dateText,
                                    row_text: text.substring(0, 300),
                                    thread_id: threadId,
                                    display_name: displayName,
                                    labels: labels
                                });
                            }
                        }
                        return emails;
                    }
                    """,
                    {},
                )
                
                # Process emails from JavaScript data
                page_emails = []
                for email_info in email_data:
                    try:
                        subject = email_info.get('subject', '').strip()
                        recipient = email_info.get('recipient', '').strip()
                        date_text = email_info.get('date_text', '').strip()
                        row_text = email_info.get('row_text', '').strip()
                        display_name = email_info.get('display_name', '').strip()
                        username_hint = (
                            self._extract_username_from_text(row_text)
                            or self._extract_username_from_text(subject)
                            or self._extract_username_from_text(display_name)
                        )
                        if not username_hint and recipient:
                            username_hint = self._sanitize_username(recipient.split("@")[0])
                        
                        email_date = self._parse_email_date(date_text)
                        if not email_date:
                            email_date = datetime.now() - timedelta(days=1)
                        
                        days_old = (datetime.now() - email_date).days if email_date else 0
                        
                        page_emails.append({
                            "recipient": recipient or "unknown",
                            "subject": subject or "(no subject)",
                            "date": email_date,
                            "date_text": date_text or "unknown",
                            "index": email_info['index'],
                            "days_old": days_old,
                            "page": page_num,
                            "username_hint": username_hint,
                            "thread_id": email_info.get('thread_id', '').strip(),
                            "display_name": display_name,
                            "labels": email_info.get('labels', []),  # Include labels/tags
                        })
                    except Exception as e:
                        continue
                
                print(f"   Found {len(page_emails)} emails on this page")
                
                if not page_emails:
                    print(f"   No emails found on page {page_num}, stopping.")
                    break
                
                # Initialize page counters
                page_skipped = 0
                page_attempted = 0
                
                # DRY RUN: Just show what would be processed
                if dry_run:
                    print("\n   🔍 DRY RUN - Emails on this page:\n")
                    page_skipped_dry = 0
                    for i, email in enumerate(page_emails, 1):
                        date_str = email.get('date_text', 'unknown date')
                        labels = email.get('labels', [])
                        label_str = f" [Labels: {', '.join(labels)}]" if labels else ""
                        skip_marker = ""
                        if labels and 'pretti responses' in [l.lower() for l in labels]:
                            skip_marker = " ⏭ SKIP"
                            page_skipped_dry += 1
                        print(f"      {i}. {email['recipient']}: {email['subject'][:50]} ({date_str}){label_str}{skip_marker}")
                    total_processed += len(page_emails)
                    skipped_count += page_skipped_dry
                    print(f"\n   📊 DRY RUN Page {page_num} Summary:")
                    print(f"      Would attempt: {len(page_emails) - page_skipped_dry} | Would skip (tagged): {page_skipped_dry} | Total on page: {len(page_emails)}")
                    
                    # Check if we should continue to next page
                    if max_emails and total_processed >= max_emails:
                        print(f"\n   ✓ Reached limit of {max_emails} emails")
                        break
                    
                    # Try to go to next page
                    if pagination and pagination['current_end'] >= pagination['total']:
                        print(f"\n   ✓ Reached last page")
                        break
                    
                    has_next = await self.go_to_next_page()
                    if not has_next:
                        print(f"\n   ✓ No more pages")
                        break
                    
                    page_num += 1
                    continue
                
                # REAL RUN: Process each email on this page
                for i, email in enumerate(page_emails, 1):
                    # Check if we've hit the max_emails limit
                    if max_emails and total_processed >= max_emails:
                        print(f"\n✓ Reached limit of {max_emails} emails")
                        break
                    
                    print(f"\n[Page {page_num}, Email {i}/{len(page_emails)}] Processing: {email['subject'][:50]}...")
                    
                    # Check for labels/tags on this email - skip if "pretti responses" tag is present
                    labels = email.get('labels', [])
                    if labels:
                        print(f"   🏷️  Found labels: {', '.join(labels)}")
                        if 'pretti responses' in [l.lower() for l in labels]:
                            print(f"   ⏭ Skipping email - has 'pretti responses' tag")
                            skipped_count += 1
                            page_skipped += 1
                            total_processed += 1
                            continue
                    
                    # If we get here, we're actually attempting to process this email
                    total_attempted += 1
                    page_attempted += 1
                    
                    # Make sure we're on the sent folder page before processing
                    # Skip this check during pagination as we're already in the right place
                    if not self._is_paginating and not self._is_in_sent_list_view():
                        print("   ⚠ Not in sent list view, navigating back...")
                        await self.go_to_sent_folder()
                        await asyncio.sleep(2)
                    
                    # Process email (detect level, extract username, send follow-up)
                    success, username, level = await self.process_email_fast(email, followup_templates)
                    
                    if success:
                        sent_count += 1
                        print(f"   ✓ Follow-up sent! (username: {username or 'unknown'}, level: {level})")
                    else:
                        failed_count += 1
                        print(f"   ⏭ Failed to send (error or skipped)")
                    
                    total_processed += 1
                    
                    # Small delay between emails to avoid rate limiting
                    await asyncio.sleep(1)
                
                # Print page statistics
                print(f"\n   📊 Page {page_num} Summary:")
                print(f"      Attempted: {page_attempted} | Skipped (tagged): {page_skipped} | Total on page: {len(page_emails)}")
                
                # Check if we've hit the max_emails limit
                if max_emails and total_processed >= max_emails:
                    print(f"\n✓ Reached limit of {max_emails} emails")
                    break
                
                # Check if there's a next page
                if pagination:
                    if pagination['current_end'] >= pagination['total']:
                        print(f"\n✓ Reached last page ({pagination['current_end']} of {pagination['total']})")
                        break
                
                # Try to go to next page
                print(f"\n   Moving to next page...")
                has_next = await self.go_to_next_page()
                if not has_next:
                    print(f"   ✓ No more pages available")
                    break
                
                page_num += 1
            
            print(f"\n{'='*60}")
            print(f"✓ Follow-up process complete!")
            print(f"   Sent: {sent_count} follow-up emails")
            print(f"   Failed: {failed_count} emails")
            print(f"   Skipped (tagged): {skipped_count} emails")
            print(f"   Attempted: {total_attempted} emails (excluding skipped)")
            print(f"   Total examined: {total_processed} emails across {page_num} page(s)")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reset pagination flag
            self._is_paginating = False
            
            # Only close browser/context if we launched it ourselves
            # Don't close when connected to Arc browser
            if not self.use_arc:
                if self.browser:
                    await self.browser.close()
            else:
                # When using Arc, just disconnect (don't close the browser)
                if self.browser:
                    await self.browser.close()
                print("✓ Disconnected from Arc browser (browser remains open)")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gmail Follow-up Tool")
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of days to wait before following up (default: 5)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--arc",
        action="store_true",
        help="Connect to existing Arc browser (requires Arc to be running with --remote-debugging-port=9222)"
    )
    parser.add_argument(
        "--template",
        type=str,
        help="Path to follow-up template file (default: followup_template.txt)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't actually send emails"
    )
    parser.add_argument(
        "--max-emails",
        type=int,
        default=None,
        help="Maximum number of emails to scan (default: None = all emails). The script will scroll to load more emails."
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Sender profile to use ('advaith', 'abhay', or 'ethan'). Defaults to profile in config.yaml"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config.yaml file (default: config.yaml in script directory)"
    )
    
    args = parser.parse_args()
    
    # Load all follow-up templates (level 1, 2, 3)
    base_path = Path(__file__).parent
    followup_templates = {}
    
    for level in [1, 2, 3]:
        template_path = base_path / f"followup_template_level{level}.txt"
        try:
            with open(template_path, 'r') as f:
                followup_templates[level] = f.read().strip()
                print(f"✓ Loaded follow-up template level {level}")
        except FileNotFoundError:
            print(f"⚠ Template file not found: {template_path}")
            if level == 1:
                # Fallback to default template for level 1
                followup_templates[1] = """hey {username},

following up on my email about the {app_name} paid promo opportunity!

we think you'd be a great fit and would love to work with you. let me know if you're interested!

also, your audience looks to you for guidance—{app_name} makes that guidance tangible.

-{from_name} from the {app_name} App ({link_url})
"""
    
    # Initialize and run
    profile_name = args.profile
    
    tool = GmailFollowUp(
        followup_days=args.days,
        headless=args.headless,
        use_arc=args.arc,
        profile=profile_name,
        config_path=args.config,
    )
    
    if not followup_templates:
        print("✗ Error: No follow-up templates loaded!")
        sys.exit(1)
    
    await tool.run(followup_templates, dry_run=args.dry_run, max_emails=args.max_emails)


if __name__ == "__main__":
    asyncio.run(main())
