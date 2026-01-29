#!/usr/bin/env python3
"""
Direct test of Playwright on Cloud Run - minimal reproduction case
"""
import asyncio
import os
from playwright.async_api import async_playwright

async def test_playwright():
    print("[TEST] Starting Playwright test...")
    print(f"[TEST] Environment: {os.environ.get('K_SERVICE', 'local')}")
    
    try:
        async with async_playwright() as pw:
            print("[TEST] Playwright started successfully")
            
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            print(f"[TEST] Browser launched: {browser}")
            
            page = await browser.new_page()
            print(f"[TEST] Page created, current URL: {page.url}")
            
            # Try to navigate to TikTok
            print("[TEST] Attempting to navigate to khaby.lame's TikTok...")
            try:
                response = await page.goto("https://www.tiktok.com/@khaby.lame", wait_until="domcontentloaded", timeout=20000)
                print(f"[TEST] Navigation completed! Status: {response.status if response else 'No response'}")
                print(f"[TEST] Final URL: {page.url}")
                print(f"[TEST] Page title: {await page.title()}")
            except Exception as nav_error:
                print(f"[TEST] Navigation FAILED: {nav_error}")
                print(f"[TEST] Page URL after failure: {page.url}")
            
            await browser.close()
            print("[TEST] Browser closed successfully")
            
    except Exception as e:
        print(f"[TEST] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_playwright())
