import asyncio
import random
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

class ProductScraper:
    def __init__(self, max_contexts: int = 3):
        self.max_contexts = max_contexts
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context_pool: asyncio.Queue[BrowserContext] = asyncio.Queue(maxsize=max_contexts)

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

        for _ in range(self.max_contexts):
            ctx = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo"
            )
            await self.context_pool.put(ctx)

    async def close(self):
        while not self.context_pool.empty():
            ctx = await self.context_pool.get()
            await ctx.close()

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _extract_price(self, page: Page) -> Optional[float]:
        selectors = [
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "[data-a-color='price']"
        ]

        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                try:
                    return float(
                        text.replace("R$", "")
                        .replace(".", "")
                        .replace(",", ".")
                        .strip()
                    )
                except:
                    continue
        return None

    async def scrape(self, url: str) -> Dict[str, Any]:
        context = await self.context_pool.get()
        page: Page = await context.new_page()

        try:
            page.set_default_timeout(5000)

            await page.goto(url, wait_until="commit", timeout=10000)

            # leve interação humana
            await page.mouse.wheel(0, random.randint(200, 500))
            await asyncio.sleep(random.uniform(0.1, 0.3))

            title = await page.title()
            price = await self._extract_price(page)

            return {
                "title": title,
                "price": price,
                "url": url,
                "blocked": False
            }

        except Exception as e:
            return {"blocked": True, "error": str(e), "url": url}

        finally:
            if not page.is_closed():
                await page.close()
            await self.context_pool.put(context)
