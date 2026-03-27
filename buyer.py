import asyncio
import random
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page

class Buyer:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _find_buy_button(self, page: Page):
        selectors = [
            "[data-testid*='buy']",
            "button[id*='buy']",
            "button[name*='buy']",
            "button[aria-label*='buy']",
            "button:has-text('Comprar')",
            "button:has-text('Buy')"
        ]

        for sel in selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                return loc.first
        return None

    async def _confirm_purchase(self, page: Page, original_url: str) -> bool:
        signals = [
            page.url != original_url,
            await page.locator("[href*='cart']").count() > 0,
            await page.locator("text=carrinho").count() > 0,
            await page.locator("[data-testid*='cart']").count() > 0
        ]
        return any(signals)

    async def buy(self, url: str) -> Dict[str, Any]:
        async with self._lock:  # evita compras duplicadas simultâneas
            context = await self.browser.new_context()
            page: Page = await context.new_page()

            try:
                page.set_default_timeout(5000)

                await page.goto(url, wait_until="commit", timeout=10000)

                button = await self._find_buy_button(page)
                if not button:
                    return {"status": "fail", "reason": "no_button"}

                await button.click()
                await asyncio.sleep(random.uniform(0.2, 0.6))

                if await self._confirm_purchase(page, url):
                    return {"status": "success", "url": page.url}

                return {"status": "fail", "reason": "not_confirmed"}

            except Exception as e:
                return {"status": "error", "error": str(e)}

            finally:
                if not page.is_closed():
                    await page.close()
                await context.close()
