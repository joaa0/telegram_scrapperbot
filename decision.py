import unicodedata
from dataclasses import dataclass
from typing import List, Optional

# ----------------------
# Utils
# ----------------------

def normalize(text: str) -> str:
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def contains_word(haystack: str, needle: str) -> bool:
    """Match por palavra aproximada (evita 'ssd' em 'missdado')."""
    h = f" {normalize(haystack)} "
    n = f" {normalize(needle)} "
    return n in h


# ----------------------
# Models
# ----------------------

@dataclass
class Product:
    name: str
    price: float
    url: str
    original_price: Optional[float] = None


@dataclass
class Rule:
    keywords: List[str]
    max_price: float
    min_discount: float = 0.0  # 0.0 a 1.0
    priority: int = 0


# ----------------------
# Config
# ----------------------
import config as _config

BLACKLIST = [
    "case",
    "capa",
    "adesivo",
    "suporte",
    "dummy",
    "SATA",
]

# Converte as BuyRules do config.py para o formato Rule do DecisionEngine
BUY_RULES: List[Rule] = [
    Rule(
        keywords=r.keywords,
        max_price=r.max_price,
        min_discount=r.min_discount_pct / 100,  # config usa %, Rule usa 0.0-1.0
        priority=i,
    )
    for i, r in enumerate(reversed(_config.BUY_RULES))
]


# ----------------------
# Core
# ----------------------

class DecisionEngine:
    def __init__(self, rules: List[Rule] = None):
        self.rules = sorted(rules or BUY_RULES, key=lambda r: r.priority, reverse=True)

    def _has_blacklist(self, name: str) -> bool:
        n = normalize(name)
        return any(b in n for b in BLACKLIST)

    def _keyword_match(self, name: str, keywords: List[str]) -> int:
        score = 0
        for kw in keywords:
            if contains_word(name, kw):
                score += 1
        return score

    def _discount(self, product: Product) -> float:
        if product.original_price and product.original_price > 0:
            return max(0.0, 1 - (product.price / product.original_price))
        return 0.0

    def evaluate(self, product: Product) -> dict:
        name_norm = normalize(product.name)

        if self._has_blacklist(product.name):
            return {"buy": False, "reason": "blacklist"}

        best_decision = {"buy": False, "reason": "no_rule_matched"}

        for rule in self.rules:
            kw_score = self._keyword_match(product.name, rule.keywords)

            if kw_score == 0:
                continue

            price_ok = product.price <= rule.max_price
            discount = self._discount(product)
            discount_ok = discount >= rule.min_discount

            # Scoring
            score = 0
            score += min(kw_score, len(rule.keywords))  # peso keywords
            if price_ok:
                score += 1
            if discount_ok:
                score += 1

            # Penalização leve se não tiver desconto
            if not discount_ok:
                score -= 0.5

            # Threshold adaptativo
            threshold = 1.5

            if score >= threshold:
                return {
                    "buy": True,
                    "reason": "rule_matched",
                    "score": score,
                    "rule": rule,
                    "discount": round(discount, 3),
                }

            # guarda melhor tentativa
            if not best_decision["buy"] and score > best_decision.get("score", -1):
                best_decision = {
                    "buy": False,
                    "reason": "low_score",
                    "score": score,
                    "rule": rule,
                    "discount": round(discount, 3),
                }

        return best_decision


# ----------------------
# Example
# ----------------------

# if __name__ == "__main__":
#     engine = DecisionEngine()
#     p = Product(name="SSD NVME 1TB Promo", price=299.0, url="x", original_price=450.0)
#     print(engine.evaluate(p))
