"""Extração de preço e heurística de 'valor bom' (opção A).

Funções puras, sem estado: recebem texto e regras, retornam (bool, motivo).
Mantém a lógica de parsing isolada e testável.
"""
import re

_NUM = r"(\d{1,3}(?:[.\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"

_INSTALLMENT = re.compile(r"\d+\s*x\s*(?:de\s*)?r?\$?\s*", re.IGNORECASE)

_DE_POR = re.compile(
    r"\bde\s*r?\$?\s*" + _NUM + r"\s*(?:reais)?\s*por\s*r?\$?\s*" + _NUM + r"\s*(?:reais)?",
    re.IGNORECASE,
)

_PRICE_TOKEN = re.compile(
    r"(?:r\$\s*|por\s+r?\$?\s*)" + _NUM + r"\s*(?:reais)?\b"
    r"|r\$\s*" + _NUM,
    re.IGNORECASE,
)


def _to_float(s):
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        # Ambíguo: ponto pode ser decimal (2.69) ou milhar (2.699).
        # Em preços em R$, se o ponto é seguido de exatamente 3 dígitos,
        # tratar como separador de milhar (formato BR).
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_de_por(text):
    if not text:
        return []
    pairs = []
    for m in _DE_POR.finditer(text):
        x = _to_float(m.group(1))
        y = _to_float(m.group(2))
        if x is not None and y is not None and x > 0 and y > 0:
            pairs.append((x, y))
    return pairs


def _strip_installments(text):
    return _INSTALLMENT.sub("", text)


def extract_single_prices(text):
    if not text:
        return []
    cleaned = _strip_installments(text)
    prices = []
    for m in _PRICE_TOKEN.finditer(cleaned):
        g = m.group(1) or m.group(2)
        if g is None:
            continue
        val = _to_float(g)
        if val is not None and val > 0:
            prices.append(val)
    return prices


def check_price_good(text, discount_min=60, price_max=20):
    if not text:
        return False, None

    pairs = extract_de_por(text)
    best_discount = 0.0
    best_pair = None
    for x, y in pairs:
        if x > y:
            disc = (x - y) / x * 100.0
            if disc > best_discount:
                best_discount = disc
                best_pair = (x, y)
    if best_pair is not None and best_discount >= discount_min:
        return True, "desconto_{}%".format(int(round(best_discount)))

    singles = extract_single_prices(text)
    if singles:
        menor = min(singles)
        if menor <= price_max:
            if float(menor).is_integer():
                return True, "preco_{}".format(int(menor))
            return True, "preco_{}".format(menor)

    return False, None
