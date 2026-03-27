"""
parser.py - Extração e normalização de URLs a partir de mensagens do Telegram.
"""

import re
import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# Regex que captura URLs http/https em texto puro
_URL_PATTERN = re.compile(
    r"https?://"                  # esquema obrigatório
    r"(?:[-\w.]|(?:%[\da-fA-F]{2}))+"  # domínio
    r"(?:/[^\s<>\"']*)?",         # caminho opcional
    re.IGNORECASE,
)

# Domínios de encurtadores — não queremos rastrear o encurtador, mas sim o destino
_SHORTENERS = {
    "bit.ly", "t.co", "tinyurl.com", "ow.ly", "short.io",
    "amzn.to", "goo.gl", "rb.gy", "is.gd", "buff.ly",
}


def extract_url(text: str) -> Optional[str]:
    """
    Extrai a primeira URL válida de um texto.

    Retorna None se nenhuma URL for encontrada ou se a URL for de um
    serviço de encurtamento (eles serão resolvidos pelo scraper).

    Args:
        text: Conteúdo da mensagem do Telegram.

    Returns:
        URL normalizada ou None.
    """
    if not text:
        return None

    matches = _URL_PATTERN.findall(text)
    if not matches:
        logger.debug("Nenhuma URL encontrada na mensagem.")
        return None

    url = _normalize_url(matches[0])
    logger.debug("URL extraída: %s", url)
    return url


def _normalize_url(url: str) -> str:
    """
    Normaliza uma URL removendo parâmetros de rastreamento comuns
    (utm_source, utm_medium, fbclid, etc.) para facilitar deduplicação.

    Args:
        url: URL bruta.

    Returns:
        URL limpa.
    """
    try:
        parsed = urlparse(url)
        # Remove query params de rastreamento
        if parsed.query:
            clean_params = _strip_tracking_params(parsed.query)
            parsed = parsed._replace(query=clean_params)
        return urlunparse(parsed)
    except Exception:
        return url


def _strip_tracking_params(query: str) -> str:
    """Remove parâmetros de rastreamento conhecidos da query string."""
    tracking = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "fbclid", "gclid", "ref", "tag", "aff",
        "affiliate", "source",
    }
    parts = []
    for part in query.split("&"):
        key = part.split("=")[0].lower()
        if key not in tracking:
            parts.append(part)
    return "&".join(parts)


def is_shortener(url: str) -> bool:
    """
    Retorna True se a URL pertencer a um encurtador conhecido.
    Nesse caso, o scraper deve seguir o redirect antes de analisar.

    Args:
        url: URL a verificar.

    Returns:
        True se for encurtador.
    """
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return domain in _SHORTENERS
    except Exception:
        return False
