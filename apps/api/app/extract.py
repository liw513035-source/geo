import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

CART_RE = re.compile(r"加入购物车|立即购买|add to cart|buy now", re.I)
PRICE_RE = re.compile(
    r"(?:(?:CNY|RMB|USD|EUR|¥|￥|\$|€)\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:元|CNY|RMB|USD|EUR))",
    re.I,
)
UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ml|mL|kg|cm|mm|mAh|GB|TB|W|V|L|寸|英寸|克|毫升|升|g|m)\b",
    re.I,
)
STOCK_RE = re.compile(r"现货|有货|缺货|售罄|预售|无货|库存\s*[:：]?\s*\S+")
SHIP_RE = re.compile(r"包邮|免运费|运费|快递|物流|配送|顺丰|圆通|中通|申通|韵达|京东物流")
BRAND_RE = re.compile(r"品牌\s*[:：]\s*([^\s,，。；;]{1,40})")
CURRENCY_HINT = re.compile(r"元|CNY|RMB|¥|￥|USD|\$|EUR|€", re.I)


@dataclass
class ProductLink:
    name: str
    href: str
    price: Decimal | None = None
    currency: str | None = None


@dataclass
class Document:
    page_type: str
    title: str
    h1: list[str]
    h2_count: int
    h3_count: int
    product_name: str | None
    brand: str | None
    store_name: str | None
    price: Decimal | None
    currency: str | None
    stock: str | None
    specs: list[str]
    rating: Decimal | None
    review_count: int | None
    shipping: str | None
    has_list: bool
    has_table: bool
    has_faq: bool
    visible_text: str
    window: str
    products: list[dict]
    product_links: list[ProductLink]
    status_code: int = 200
    truncated: bool = False
    raw_html: str = ""


@dataclass
class WindowFacts:
    excerpt: str
    has_name: bool
    has_price: bool
    has_spec: bool
    has_quotable_sentence: bool


def parse_html(html: str, status_code: int = 200, truncated: bool = False) -> Document:
    soup = BeautifulSoup(html, "html.parser")
    products = _products(soup)
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    window = visible[: max(1, math.floor(len(visible) * 0.3))] if visible else ""
    title = _meta(soup, "title") or ""
    h1 = [re.sub(r"\s+", " ", node.get_text(" ", strip=True)) for node in soup.find_all("h1")]
    h1 = [item for item in h1 if item]
    product_name = _first_name(products) or _meta_attr(soup, "og:title") or (h1[0] if h1 else None) or (title or None)
    brand = _first_brand(products) or _meta_attr(soup, "product:brand") or _match_group(BRAND_RE, visible)
    store_match = re.search(r"店铺\s*[:：]\s*([^\s,，。]{1,40})", visible)
    store_name = _meta_attr(soup, "og:site_name") or (store_match.group(1) if store_match else None)
    price, currency = _first_offer(products)
    if price is None:
        price, currency = _price_in_text(visible)
    stock_match = STOCK_RE.search(visible)
    ship_match = SHIP_RE.search(visible)
    specs = UNIT_RE.findall(visible)
    rating, reviews = _rating(products)
    links = _product_links(soup)
    has_cart = bool(CART_RE.search(visible))
    has_product = any(_is_type(item, "Product") for item in products)
    page_type = _page_type(
        has_product=has_product,
        has_price=price is not None or bool(PRICE_RE.search(visible)),
        has_cart=has_cart,
        links=links,
        store_name=store_name,
        soup=soup,
    )
    return Document(
        page_type=page_type,
        title=title,
        h1=h1,
        h2_count=len(soup.find_all("h2")),
        h3_count=len(soup.find_all("h3")),
        product_name=product_name,
        brand=brand,
        store_name=store_name,
        price=price,
        currency=currency,
        stock=stock_match.group(0) if stock_match else None,
        specs=specs,
        rating=rating,
        review_count=reviews,
        shipping=ship_match.group(0) if ship_match else None,
        has_list=bool(soup.find(["ul", "ol"])),
        has_table=bool(soup.find("table")),
        has_faq=_has_faq(soup),
        visible_text=visible,
        window=window,
        products=products,
        product_links=links,
        status_code=status_code,
        truncated=truncated,
        raw_html=html,
    )


def window_facts(doc: Document) -> WindowFacts:
    names = [doc.product_name or ""]
    names.extend(link.name for link in doc.product_links)
    folded = re.sub(r"\s+", "", doc.window)
    has_name = any(name and re.sub(r"\s+", "", name) in folded for name in names)
    has_price = bool(PRICE_RE.search(doc.window) and CURRENCY_HINT.search(doc.window))
    return WindowFacts(
        excerpt=doc.window[:500],
        has_name=has_name,
        has_price=has_price,
        has_spec=bool(UNIT_RE.search(doc.window)),
        has_quotable_sentence=_quotable(doc.window),
    )


def _page_type(*, has_product, has_price, has_cart, links, store_name, soup) -> str:
    if has_product or (has_price and has_cart):
        return "product"
    if len(links) >= 3:
        return "category"
    nav_links = soup.select("nav a, header a")
    if store_name and (links or len(nav_links) >= 1):
        return "store"
    return "unknown"


def _product_links(soup: BeautifulSoup) -> list[ProductLink]:
    best: list[ProductLink] = []
    for container in soup.find_all(["ul", "ol"]):
        found: list[ProductLink] = []
        for item in container.find_all("li", recursive=False):
            anchor = item.find("a", href=True)
            name = anchor.get_text(" ", strip=True) if anchor else ""
            if not anchor or not name:
                continue
            text = item.get_text(" ", strip=True)
            price, currency = _price_in_text(text)
            found.append(ProductLink(name=name, href=anchor["href"], price=price, currency=currency))
        if len(found) > len(best):
            best = found
    return best


def _has_faq(soup: BeautifulSoup) -> bool:
    if soup.find("details") or soup.find("dl"):
        return True
    for node in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = node.get_text(" ", strip=True)
        if re.search(r"FAQ|常见问题", text, re.I):
            return True
    return False


def _products(soup: BeautifulSoup) -> list[dict]:
    found: list[dict] = []
    for script in soup.find_all("script"):
        kind = " ".join(script.get("type") or []).lower() if isinstance(script.get("type"), list) else (script.get("type") or "")
        if "ld+json" not in str(kind).lower():
            continue
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        found.extend(_walk_products(data))
    return found


def _walk_products(data) -> list[dict]:
    if isinstance(data, list):
        items: list[dict] = []
        for entry in data:
            items.extend(_walk_products(entry))
        return items
    if not isinstance(data, dict):
        return []
    items = []
    if _is_type(data, "Product"):
        items.append(data)
    graph = data.get("@graph")
    if isinstance(graph, list):
        items.extend(_walk_products(graph))
    return items


def _is_type(node: dict, expected: str) -> bool:
    kind = node.get("@type")
    if isinstance(kind, list):
        return expected in kind
    return kind == expected


def _first_name(products: list[dict]) -> str | None:
    for product in products:
        name = product.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _first_brand(products: list[dict]) -> str | None:
    for product in products:
        brand = product.get("brand")
        if isinstance(brand, str) and brand.strip():
            return brand.strip()
        if isinstance(brand, dict):
            name = brand.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _first_offer(products: list[dict]) -> tuple[Decimal | None, str | None]:
    for product in products:
        offers = product.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            continue
        price = _decimal(offers.get("price"))
        currency = offers.get("priceCurrency")
        if price is not None:
            return price, str(currency).upper() if currency else None
    return None, None


def _rating(products: list[dict]) -> tuple[Decimal | None, int | None]:
    for product in products:
        rating = product.get("aggregateRating")
        if not isinstance(rating, dict):
            continue
        value = _decimal(rating.get("ratingValue"))
        count = rating.get("reviewCount") or rating.get("ratingCount")
        try:
            reviews = int(count) if count is not None else None
        except (TypeError, ValueError):
            reviews = None
        if value is not None:
            return value, reviews
    return None, None


def _price_in_text(text: str) -> tuple[Decimal | None, str | None]:
    match = PRICE_RE.search(text)
    if not match:
        return None, None
    number = match.group(1) or match.group(2)
    token = match.group(0)
    currency = "CNY"
    if re.search(r"USD|\$", token, re.I):
        currency = "USD"
    elif re.search(r"EUR|€", token, re.I):
        currency = "EUR"
    return _decimal(number), currency


def _decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None


def _quotable(window: str) -> bool:
    for sentence in re.split(r"[。！？!?\n]", window):
        sentence = sentence.strip()
        if not 20 <= len(sentence) <= 180:
            continue
        if re.search(r"\d", sentence) or re.search(r"价格|规格|品牌|库存|物流", sentence):
            return True
    return False


def _meta(soup: BeautifulSoup, name: str) -> str:
    node = soup.find(name)
    return node.get_text(" ", strip=True) if node else ""


def _meta_attr(soup: BeautifulSoup, key: str) -> str | None:
    node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if not node:
        return None
    content = node.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _match_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None
