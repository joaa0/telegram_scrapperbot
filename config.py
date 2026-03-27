"""
config.py - Configurações centrais do bot de auto-buy
Edite este arquivo antes de rodar o projeto.
"""

import os
from dataclasses import dataclass
from typing import List
from enum import Enum


# ─── Telegram ────────────────────────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "7681639208:AAH-LtCh7238PTY5SjWfMzw9N95YVufiAlI")
SOURCE_CHAT_ID: int = int(os.getenv("SOURCE_CHAT_ID", "-3634847213"))
NOTIFY_CHAT_ID: int = int(os.getenv("NOTIFY_CHAT_ID", "-1003634847213"))


# ─── Regras de Compra ─────────────────────────────────────────────────────────

@dataclass
class BuyRule:
    """Define uma regra de compra configurável."""
    name: str
    keywords: List[str]
    max_price: float
    min_discount_pct: float = 0.0


BUY_RULES: List[BuyRule] = [
    BuyRule(          # ← faltava indentação e vírgula no final
        name="ryzen 5",
        keywords=[""],
        max_price=9999,
    ),                # ← faltava essa vírgula
    BuyRule(
        name="SSD Barato",
        keywords=["ssd", "nvme", "m.2"],
        max_price=350.00,
        min_discount_pct=20.0,
    ),
    BuyRule(
        name="Placa de Vídeo",
        keywords=["placa de vídeo", "gpu", "rtx", "rx 6", "rx 7"],
        max_price=2500.00,
        min_discount_pct=15.0,
    ),
    BuyRule(
        name="Headset Gamer",
        keywords=["headset", "fone gamer", "headphone"],
        max_price=200.00,
        min_discount_pct=0.0,
    ),
    BuyRule(
    name="SSD NVMe 1TB custo-benefício",
    keywords=["ssd", "nvme", "m.2", "1tb"],
    max_price=320.00,
    min_discount_pct=25.0,
    ),
    BuyRule(
    name="Ryzen 5 custo-benefício",
    keywords=["ryzen 5 5600", "ryzen 5 5500", "am4"],
    max_price=750.00,
    min_discount_pct=20.0,
    ),
    BuyRule(
    name="Placa-mãe AM4 básica",
    keywords=["a520m", "b450", "am4", "placa mae"],
    max_price=400.00,
    min_discount_pct=20.0,
    ),
    BuyRule(
    name="Memória 16GB DDR4",
    keywords=["16gb", "2x8", "ddr4", "3200mhz", "ram"],
    max_price=280.00,
    min_discount_pct=20.0,
    ),
    BuyRule(
    name="Fonte confiável 500W+",
    keywords=["fonte", "500w", "550w", "corsair", "cooler master", "80 plus"],
    max_price=300.00,
    min_discount_pct=20.0,
    ),
    BuyRule(
    name="Teclado mecânico/magnético custo-benefício",
    keywords=[
        "teclado mecanico",
        "mechanical keyboard",
        "switch",
        "red switch",
        "blue switch",
        "brown switch",
        "teclado magnetico",
        "magnetic keyboard",
        "hall effect",
        "rapid trigger"
    ],
    max_price=350.00,
    min_discount_pct=25.0,
    ),
    BuyRule(
    name="Mouse gamer custo-benefício",
    keywords=[
        "mouse gamer",
        "gaming mouse",
        "wireless mouse",
        "sensor",
        "dpi",
        "rgb",
        "lightweight",
        "ultralight",
        "honeycomb",
        "paw3395",
        "hero sensor"
    ],
    max_price=180.00,
    min_discount_pct=25.0,
    ),
]


# ─── Modo de Operação ─────────────────────────────────────────────────────────

class BotMode(str, Enum):
    """
    SAFE → comportamento humano completo: delays longos, scroll orgânico,
           mouse em movimento, pausa antes de clicar.
           Menor risco de bloqueio. Mais lento (~30-60s por produto).

    FAST → delays mínimos, sem simulações extras.
           Alta velocidade (~5-10s por produto). Risco elevado de bloqueio.
    """
    SAFE = "safe"
    FAST = "fast"

# Altere para BotMode.FAST se quiser priorizar velocidade
OPERATION_MODE: BotMode = BotMode.SAFE


# ─── Delays (segundos) ────────────────────────────────────────────────────────
# Cada ação sorteia um valor aleatório entre MIN e MAX para imitar humano.

@dataclass
class DelayConfig:
    page_load_min: float        # aguardar após página carregar
    page_load_max: float
    before_click_min: float     # pausa antes de clicar em qualquer elemento
    before_click_max: float
    between_actions_min: float  # entre etapas do fluxo de compra
    between_actions_max: float
    retry_min: float            # espera entre tentativas de retry
    retry_max: float
    scroll_pause_min: float     # pausa entre cada passo de scroll
    scroll_pause_max: float
    typing_delay_min: float     # delay entre teclas ao digitar (ms)
    typing_delay_max: float


DELAYS: dict[BotMode, DelayConfig] = {
    BotMode.SAFE: DelayConfig(
        page_load_min=2.0,        page_load_max=5.0,
        before_click_min=0.8,     before_click_max=2.5,
        between_actions_min=1.5,  between_actions_max=4.0,
        retry_min=10.0,           retry_max=25.0,
        scroll_pause_min=0.4,     scroll_pause_max=1.2,
        typing_delay_min=60,      typing_delay_max=180,
    ),
    BotMode.FAST: DelayConfig(
        page_load_min=0.3,        page_load_max=0.8,
        before_click_min=0.05,    before_click_max=0.2,
        between_actions_min=0.2,  between_actions_max=0.5,
        retry_min=3.0,            retry_max=7.0,
        scroll_pause_min=0.05,    scroll_pause_max=0.15,
        typing_delay_min=20,      typing_delay_max=60,
    ),
}


# ─── User-Agents e Viewports ──────────────────────────────────────────────────
# Um UA e um viewport são escolhidos aleatoriamente a cada nova sessão.

USER_AGENTS: List[str] = [
    # Chrome 124 Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 123 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Firefox 125 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Edge 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

VIEWPORTS: List[dict] = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 800},
]


# ─── Scraper ──────────────────────────────────────────────────────────────────

SCRAPER_TIMEOUT_MS: int = 20_000
SCRAPER_MAX_RETRIES: int = 3

# Arquivo de sessão: cookies + localStorage persistidos entre execuções
SESSION_FILE: str = "session.json"

# Se True, abre janela visível para login manual na primeira execução.
# Faça login no site, depois pressione ENTER no terminal.
# A sessão é salva e nas próximas execuções roda em headless automaticamente.
HEADFUL_LOGIN_MODE: bool = os.getenv("LOGIN_MODE", "false").lower() == "true"


# ─── Detecção de bloqueio ─────────────────────────────────────────────────────

# HTTP status codes que indicam rate-limit ou bloqueio
BLOCK_STATUS_CODES: List[int] = [403, 429, 503]

# Palavras/frases que, encontradas no HTML, indicam CAPTCHA ou verificação
CAPTCHA_KEYWORDS: List[str] = [
    "captcha", "recaptcha", "hcaptcha",
    "robot", "robô",
    "verificação de segurança", "security check",
    "unusual traffic", "tráfego incomum",
    "prove you're human", "prove que você é humano",
    "access denied", "acesso negado",
    "cloudflare", "cf-challenge", "just a moment",
    "bot detected", "automated access",
]

# Arquivo onde URLs bloqueadas são salvas (formato JSONL, uma por linha)
BLOCKED_URLS_FILE: str = "blocked_urls.jsonl"

# Cooldown (segundos) após qualquer bloqueio detectado antes da próxima URL
COOLDOWN_AFTER_BLOCK: float = 60.0


# ─── Cache / Anti-duplicata ───────────────────────────────────────────────────

CACHE_MAX_SIZE: int = 500


# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"



AUTOBUY_ENABLED: bool = False  # mude para True para ativar compras
