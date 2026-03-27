"""
crawler.py - Crawler de promoções usando Playwright para sites com JS.

Fontes:
  - MercadoLivre (API publica - sem Playwright)
  - KaBuM        (Playwright - renderiza JS)
  - Buscape      (Playwright - renderiza JS)
  - Zoom         (Playwright - renderiza JS)
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp
from aiogram import Bot
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

import config
from decision import DecisionEngine, Product

_decision_engine = DecisionEngine()
logger = logging.getLogger(__name__)

CRAWL_INTERVAL: int = 300
HTTP_TIMEOUT: int = 20
PW_TIMEOUT: int = 20_000  # ms

_posted_urls: set[str] = set()
_bot: Optional[Bot] = None
_chat_id: int = 0

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def setup_crawler(bot: Bot, chat_id: int) -> None:
    global _bot, _chat_id
    _bot = bot
    _chat_id = chat_id
    logger.info("Crawler configurado -> postando em chat_id=%s", chat_id)


@dataclass
class Deal:
    title: str
    price: float
    url: str
    source: str
    image_url: str = ""
    old_price: float = 0.0


# ─── Loop principal ───────────────────────────────────────────────────────────

async def crawler_loop() -> None:
    logger.info("Crawler iniciado - intervalo: %ds por rodada", CRAWL_INTERVAL)
    while True:
        t0 = time.monotonic()
        logger.info("Iniciando rodada de crawling...")

        # MercadoLivre roda separado (usa aiohttp, nao Playwright)
        ml_task = asyncio.create_task(_crawl_mercadolivre())

        # Os outros tres usam Playwright — compartilham um browser
        pw_task = asyncio.create_task(_crawl_with_playwright())

        results = await asyncio.gather(ml_task, pw_task, return_exceptions=True)

        total = 0
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Erro em tarefa do crawler: %s", r)
            elif isinstance(r, int):
                total += r

        logger.info(
            "Rodada concluida em %.1fs | postado: %d | proxima em %ds",
            time.monotonic() - t0, total, CRAWL_INTERVAL,
        )
        await asyncio.sleep(CRAWL_INTERVAL)


async def _crawl_with_playwright() -> int:
    """
    Abre um unico browser Playwright e crawla KaBuM, Buscape e Zoom em sequencia.
    Compartilhar o browser economiza memoria e tempo de inicializacao.
    """
    total = 0
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 800},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            # Bloqueia recursos pesados para acelerar
            await context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("media", "font", "image")
                else route.continue_(),
            )

            for crawler_fn in [_pw_kabum, _pw_buscape]:
                page = None
                try:
                    page = await context.new_page()
                    # Timeout de 60s por site — impede que um site trave o processo todo
                    deals = await asyncio.wait_for(crawler_fn(page), timeout=60)
                    posted = await _filter_and_post(deals)
                    total += posted
                    if posted:
                        logger.info("[%s] %d oferta(s) postada(s)", crawler_fn.__name__, posted)
                except asyncio.TimeoutError:
                    logger.warning("[%s] Timeout de 60s — pulando", crawler_fn.__name__)
                except Exception as exc:
                    logger.warning("[%s] %s", crawler_fn.__name__, exc)
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception:
                            pass

            await browser.close()
    except Exception as exc:
        logger.warning("[Playwright] Falha geral: %s", exc)
    return total


# ─── Crawlers Playwright ──────────────────────────────────────────────────────

async def _pw_kabum(page: Page) -> list[Deal]:
    """KaBuM - extrai produtos da pagina de ofertas do dia via JS renderizado."""
    deals = []
    try:
        await page.goto("https://www.kabum.com.br/ofertas-do-dia", timeout=PW_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=PW_TIMEOUT)

        # Extrai dados do __NEXT_DATA__ que agora esta completo apos JS rodar
        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if next_data:
            props = next_data.get("props", {}).get("pageProps", {})
            products = props.get("products", []) or props.get("data", []) or []
            for p in products[:20]:
                if not isinstance(p, dict):
                    continue
                price = _to_float(p.get("preco_venda") or p.get("price") or p.get("vlr_oferta"))
                title = p.get("nome") or p.get("name") or p.get("ds_nome", "")
                if not price or not title:
                    continue
                link = p.get("link") or p.get("url") or ""
                if link and not link.startswith("http"):
                    link = f"https://www.kabum.com.br{link}"
                deals.append(Deal(
                    title=title, price=price,
                    old_price=_to_float(p.get("preco_normal") or p.get("old_price")) or 0.0,
                    url=link or "https://www.kabum.com.br/ofertas-do-dia",
                    source="KaBuM",
                    image_url=p.get("img") or p.get("image", ""),
                ))

        # Fallback: extrai direto do DOM se __NEXT_DATA__ nao tiver os produtos
        if not deals:
            items = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[class*="productCard"], [class*="product-card"], article');
                    return Array.from(cards).slice(0, 20).map(card => ({
                        title: card.querySelector('span[class*="nameCard"], h2, h3')?.innerText?.trim() || '',
                        price: card.querySelector('span[class*="priceCard"], [class*="price"]')?.innerText?.trim() || '',
                        link: card.querySelector('a')?.href || '',
                    }));
                }
            """)
            for item in items:
                price = _to_float(item.get("price", ""))
                title = item.get("title", "")
                if price and title:
                    deals.append(Deal(
                        title=title, price=price,
                        url=item.get("link") or "https://www.kabum.com.br/ofertas-do-dia",
                        source="KaBuM",
                    ))

        logger.info("[KaBuM] %d produtos encontrados", len(deals))
    except PWTimeout:
        logger.warning("[KaBuM] Timeout")
    except Exception as exc:
        logger.warning("[KaBuM] %s", exc)
    return deals


async def _pw_buscape(page: Page) -> list[Deal]:
    """Buscape - extrai ofertas da pagina principal via DOM."""
    deals = []
    try:
        await page.goto("https://www.buscape.com.br/ofertas", timeout=PW_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=PW_TIMEOUT)

        # Tenta __NEXT_DATA__ primeiro
        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if next_data:
            props = next_data.get("props", {}).get("pageProps", {})
            # Buscape pode ter os dados em varias chaves
            products = (
                props.get("offers", []) or
                props.get("products", []) or
                props.get("items", []) or
                []
            )
            for p in products[:20]:
                if not isinstance(p, dict):
                    continue
                price = _to_float(
                    p.get("price") or p.get("bestPrice") or
                    p.get("salePrice") or p.get("currentPrice")
                )
                title = p.get("name") or p.get("title") or p.get("productName", "")
                if not price or not title:
                    continue
                offer_url = p.get("url") or p.get("link") or p.get("offerUrl", "")
                if offer_url and not offer_url.startswith("http"):
                    offer_url = f"https://www.buscape.com.br{offer_url}"
                deals.append(Deal(
                    title=title, price=price,
                    old_price=_to_float(p.get("listPrice") or p.get("originalPrice")) or 0.0,
                    url=offer_url or "https://www.buscape.com.br/ofertas",
                    source="Buscape",
                    image_url=p.get("thumbnail") or p.get("image", ""),
                ))

        # Fallback DOM
        if not deals:
            items = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[class*="ProductCard"], [class*="offer-card"], [data-testid*="product"]');
                    return Array.from(cards).slice(0, 20).map(card => ({
                        title: card.querySelector('h2, h3, [class*="title"], [class*="name"]')?.innerText?.trim() || '',
                        price: card.querySelector('[class*="price"], [class*="Price"]')?.innerText?.trim() || '',
                        link: card.querySelector('a')?.href || '',
                    }));
                }
            """)
            for item in items:
                price = _to_float(item.get("price", ""))
                title = item.get("title", "")
                if price and title:
                    deals.append(Deal(
                        title=title, price=price,
                        url=item.get("link") or "https://www.buscape.com.br/ofertas",
                        source="Buscape",
                    ))

        logger.info("[Buscape] %d produtos encontrados", len(deals))
    except PWTimeout:
        logger.warning("[Buscape] Timeout")
    except Exception as exc:
        logger.warning("[Buscape] %s", exc)
    return deals


async def _pw_zoom(page: Page) -> list[Deal]:
    """Zoom - extrai ofertas com maior desconto via DOM."""
    deals = []
    try:
        await page.goto("https://www.zoom.com.br/ofertas", timeout=PW_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=PW_TIMEOUT)

        # Tenta __NEXT_DATA__ primeiro
        next_data = await page.evaluate("""
            () => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }
        """)

        if next_data:
            props = next_data.get("props", {}).get("pageProps", {})
            products = (
                props.get("products", []) or
                props.get("offers", []) or
                props.get("items", []) or
                []
            )
            for p in products[:20]:
                if not isinstance(p, dict):
                    continue
                price = _to_float(
                    p.get("price") or p.get("bestPrice") or p.get("minPrice")
                )
                title = p.get("name") or p.get("title", "")
                if not price or not title:
                    continue
                offer_url = p.get("url") or p.get("link") or p.get("productUrl", "")
                if offer_url and not offer_url.startswith("http"):
                    offer_url = f"https://www.zoom.com.br{offer_url}"
                deals.append(Deal(
                    title=title, price=price,
                    old_price=_to_float(p.get("listPrice") or p.get("originalPrice")) or 0.0,
                    url=offer_url or "https://www.zoom.com.br/ofertas",
                    source="Zoom",
                    image_url=p.get("thumbnail") or p.get("image", ""),
                ))

        # Fallback DOM
        if not deals:
            items = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[class*="ProductCard"], [class*="product-card"], [class*="offer"]');
                    return Array.from(cards).slice(0, 20).map(card => ({
                        title: card.querySelector('h2, h3, [class*="title"], [class*="name"]')?.innerText?.trim() || '',
                        price: card.querySelector('[class*="price"], [class*="Price"]')?.innerText?.trim() || '',
                        link: card.querySelector('a')?.href || '',
                    }));
                }
            """)
            for item in items:
                price = _to_float(item.get("price", ""))
                title = item.get("title", "")
                if price and title:
                    deals.append(Deal(
                        title=title, price=price,
                        url=item.get("link") or "https://www.zoom.com.br/ofertas",
                        source="Zoom",
                    ))

        logger.info("[Zoom] %d produtos encontrados", len(deals))
    except PWTimeout:
        logger.warning("[Zoom] Timeout")
    except Exception as exc:
        logger.warning("[Zoom] %s", exc)
    return deals


# ─── MercadoLivre (aiohttp - API estavel) ────────────────────────────────────

async def _crawl_mercadolivre() -> int:
    """API publica do ML - nao precisa de Playwright."""
    categories = [
        "MLB1648",  # Informatica
        "MLB1051",  # Celulares
        "MLB1000",  # Eletronicos
        "MLB1246",  # Video Games
    ]
    deals = []
    try:
        async with aiohttp.ClientSession() as s:
            for cat_id in categories:
                url = (
                    f"https://api.mercadolibre.com/sites/MLB/search"
                    f"?category={cat_id}&sort=price_asc"
                    f"&promotion_type=deal_of_the_day&limit=10"
                )
                async with s.get(url, timeout=HTTP_TIMEOUT) as r:
                    if r.status != 200:
                        continue
                    data = await r.json(content_type=None)
                    for item in data.get("results", []):
                        price = _to_float(item.get("price"))
                        title = item.get("title", "")
                        if not price or not title:
                            continue
                        deals.append(Deal(
                            title=title, price=price,
                            old_price=_to_float(item.get("original_price")) or 0.0,
                            url=item.get("permalink", "https://www.mercadolivre.com.br"),
                            source="MercadoLivre",
                            image_url=item.get("thumbnail", ""),
                        ))
                await asyncio.sleep(0.5)
    except Exception as exc:
        logger.warning("[MercadoLivre] %s", exc)
    return await _filter_and_post(deals)


# ─── Filtragem e postagem ─────────────────────────────────────────────────────

async def _filter_and_post(deals: list[Deal]) -> int:
    posted = 0
    for deal in deals:
        if not deal.title or not deal.price:
            continue
        if deal.url in _posted_urls:
            continue
        product = Product(
            name=deal.title,
            price=deal.price,
            url=deal.url,
            original_price=deal.old_price if deal.old_price else None,
        )
        decision = _decision_engine.evaluate(product)
        if not decision.get("buy"):
            continue
        _posted_urls.add(deal.url)
        rule_name = " + ".join(decision["rule"].keywords)
        await _post_deal(deal, rule_name)
        posted += 1
        await asyncio.sleep(1.5)
    return posted


async def _post_deal(deal: Deal, rule_name: str) -> None:
    if not _bot or not _chat_id:
        logger.warning("Bot/chat_id nao configurado - pulando postagem.")
        return

    discount_text = ""
    if deal.old_price and deal.old_price > deal.price:
        pct = ((deal.old_price - deal.price) / deal.old_price) * 100
        discount_text = f"De: R$ {deal.old_price:.2f} -> {pct:.0f}% off\n"

    text = (
        f"[{deal.source}] {rule_name}\n\n"
        f"{deal.title}\n\n"
        f"{discount_text}"
        f"Por: R$ {deal.price:.2f}\n\n"
        f"{deal.url}"
    )

    try:
        await _bot.send_message(
            chat_id=_chat_id,
            text=text,
            disable_web_page_preview=False,
        )
        logger.info("[%s] '%s' R$ %.2f", deal.source, deal.title[:50], deal.price)
    except Exception as exc:
        logger.error("Erro ao postar: %s", exc)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace("R$", "").strip()
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        return float(value)
    except (ValueError, TypeError):
        return None
