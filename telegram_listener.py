import asyncio
import config
from aiogram import Router
from parser import extract_url
from decision import DecisionEngine, Product
from buyer import Buyer

router = Router()

queue = asyncio.Queue()
seen_urls = set()
semaphore = asyncio.Semaphore(3)

decision_engine = DecisionEngine()
buyer = Buyer()


@router.message()
async def handle_message(message):
    url = extract_url(message.text or "")
    if not url:
        return
    if url not in seen_urls:
        seen_urls.add(url)
        await queue.put(url)


async def worker():
    while True:
        url = await queue.get()
        try:
            async with semaphore:
                await asyncio.wait_for(process_url(url), timeout=25)
        except asyncio.TimeoutError:
            print(f"[TIMEOUT] {url}")
        except Exception as e:
            print(f"[ERROR] {url} -> {e}")
        finally:
            queue.task_done()


async def process_url(url: str):
    from scraper import ProductScraper
    async with ProductScraper() as scraper:
        result = await scraper.get_product(url)

    if not result or result.blocked:
        print(f"[SCRAPER FAIL] {url}")
        return

    product = result.product
    if not product or not product.price:
        return

    decision_product = Product(
        name=product.name,
        price=product.price,
        url=product.final_url,
    )

    decision = decision_engine.evaluate(decision_product)
    if not decision.get("buy"):
        print(f"[SKIP] {url} -> {decision.get('reason')}")
        return

    if not config.AUTOBUY_ENABLED:
        print(f"[AUTO-BUY DESATIVADO] Produto elegivel: {product.name} por R$ {product.price:.2f}")
        return

    print(f"[BUYING] {url}")


async def start_workers(n=3):
    tasks = []
    for _ in range(n):
        tasks.append(asyncio.create_task(worker()))
    return tasks
