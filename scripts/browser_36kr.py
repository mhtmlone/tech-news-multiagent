"""
Script to use Playwright to access 36kr.com and extract news articles.
"""
import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from playwright.async_api import async_playwright


async def fetch_36kr_newsflashes():
    """Use Playwright to fetch newsflashes from 36kr"""
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # Create a new context with a realistic user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # Create a new page
        page = await context.new_page()
        
        # Try to access the newsflashes page
        print("Navigating to https://36kr.com/newsflashes...")
        
        try:
            # Navigate to the page with a timeout
            await page.goto("https://36kr.com/newsflashes", wait_until="networkidle", timeout=60000)
            
            # Wait for content to load
            await page.wait_for_timeout(5000)
            
            # Check if we hit a CAPTCHA
            page_content = await page.content()
            
            if "captcha" in page_content.lower() or "验证" in page_content:
                print("CAPTCHA detected! Trying to handle it...")
                # Wait longer to see if CAPTCHA can be passed
                await page.wait_for_timeout(10000)
                page_content = await page.content()
            
            # Try to extract news items
            print("Extracting news items...")
            
            # Get the page title
            title = await page.title()
            print(f"Page title: {title}")
            
            # Try to find news items using various selectors
            news_items = []
            
            # Try different selectors for 36kr news items
            selectors = [
                ".newsflash-item",
                ".news-item",
                ".item",
                "[class*='news']",
                "[class*='flash']",
                "article",
                ".list-item",
                "li"
            ]
            
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        for i, elem in enumerate(elements[:20]):  # Limit to first 20
                            try:
                                text = await elem.inner_text()
                                if text and len(text.strip()) > 20:  # Filter out empty or very short items
                                    # Try to get link
                                    link_elem = await elem.query_selector("a")
                                    link = await link_elem.get_attribute("href") if link_elem else None
                                    
                                    news_items.append({
                                        "text": text.strip()[:500],  # Limit text length
                                        "link": link
                                    })
                            except Exception as e:
                                continue
                        if news_items:
                            break
                except Exception as e:
                    continue
            
            # If no items found with selectors, try to get all text
            if not news_items:
                print("No news items found with selectors. Getting page text...")
                body = await page.query_selector("body")
                if body:
                    all_text = await body.inner_text()
                    print("Page content preview:")
                    print(all_text[:2000])
            
            await browser.close()
            return news_items
            
        except Exception as e:
            print(f"Error during page navigation: {e}")
            await browser.close()
            raise


async def fetch_36kr_feed():
    """Use Playwright to fetch RSS feed from 36kr"""
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # Create a new context with a realistic user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # Create a new page
        page = await context.new_page()
        
        # Try to access the RSS feed
        print("Navigating to https://36kr.com/feed...")
        
        try:
            await page.goto("https://36kr.com/feed", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)
            
            # Get page content
            content = await page.content()
            
            print("Page content preview:")
            print(content[:2000])
            
            await browser.close()
            return content
            
        except Exception as e:
            print(f"Error: {e}")
            await browser.close()
            raise


async def main():
    """Main function to run the Playwright browser"""
    print("=" * 60)
    print("Using Playwright to fetch 36kr news...")
    print("=" * 60)
    
    try:
        # Try the newsflashes page
        print("\nFetching from https://36kr.com/newsflashes...")
        result = await fetch_36kr_newsflashes()
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        
        if result:
            print(f"Found {len(result)} news items:")
            for i, item in enumerate(result[:10], 1):
                print(f"\n{i}. {item['text'][:200]}...")
                if item['link']:
                    print(f"   Link: {item['link']}")
        else:
            print("No news items found.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
