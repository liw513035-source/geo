import copy
import re
from dataclasses import asdict, dataclass

from app.extract import Document, window_facts

P0_CIT = {"CIT-01", "CIT-02", "CIT-11"}


@dataclass
class Issue:
    id: str
    severity: str
    dimension: str
    message: str
    evidence: str

    def dump(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    score: int
    dimensions: dict
    issues: list[dict]
    window: dict
    schema_json: dict
    page_type: str


def score_document(doc: Document) -> ScoreResult:
    facts = window_facts(doc)
    citability, cit_issues = _citability(doc, facts)
    entity, ent_issues = _entity(doc)
    structure, str_issues = _structure(doc)
    schema_score, sch_issues = _schema_score(doc)
    technical, tec_issues = _technical(doc)
    total = round(
        citability * 0.35
        + entity * 0.25
        + structure * 0.20
        + schema_score * 0.10
        + technical * 0.10
    )
    total = max(0, min(100, total))
    issues = [*cit_issues, *ent_issues, *str_issues, *sch_issues, *tec_issues]
    excerpt_id = "CIT-11" if doc.page_type in {"category", "store"} else "CIT-01"
    issues.append(
        Issue(excerpt_id if not any(item.id == excerpt_id for item in issues) else "WIN-30", "info", "citability", "前 30% 窗口摘录", facts.excerpt)
    )
    # Always keep a stable WIN-30 record for history.
    if issues[-1].id != "WIN-30":
        issues.append(Issue("WIN-30", "info", "citability", "前 30% 窗口摘录", facts.excerpt))
    return ScoreResult(
        score=total,
        dimensions={
            "citability": citability,
            "entity": entity,
            "structure": structure,
            "schema": schema_score,
            "technical": technical,
        },
        issues=[item.dump() for item in issues],
        window={
            "excerpt": facts.excerpt,
            "has_name": facts.has_name,
            "has_price": facts.has_price,
            "has_spec": facts.has_spec,
            "has_quotable_sentence": facts.has_quotable_sentence,
        },
        schema_json=build_schema(doc),
        page_type=doc.page_type,
    )


def public_issues(issues: list[dict]) -> list[dict]:
    return [item for item in issues if item.get("severity") in {"P0", "P1"}]


def build_schema(doc: Document) -> dict:
    original = _original_product(doc)
    if original:
        data = copy.deepcopy(original)
    else:
        data = {"@context": "https://schema.org", "@type": "Product"}
    if not _text(data.get("name")) and doc.product_name:
        data["name"] = doc.product_name
    if not data.get("brand") and doc.brand:
        data["brand"] = doc.brand
    offers = data.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    has_price = isinstance(offers, dict) and offers.get("price") not in (None, "")
    if not has_price and doc.price is not None and doc.currency:
        data["offers"] = {
            "@type": "Offer",
            "price": format(doc.price, "f"),
            "priceCurrency": doc.currency,
        }
    rating = data.get("aggregateRating")
    has_rating = isinstance(rating, dict) and rating.get("ratingValue") not in (None, "")
    if not has_rating and doc.rating is not None:
        payload = {"@type": "AggregateRating", "ratingValue": format(doc.rating, "f")}
        if doc.review_count is not None:
            payload["reviewCount"] = doc.review_count
        data["aggregateRating"] = payload
    if "@context" not in data:
        data["@context"] = "https://schema.org"
    return data


def _citability(doc: Document, facts) -> tuple[int, list[Issue]]:
    if doc.page_type in {"category", "store"}:
        checks = [
            ("CIT-11", 50, facts.has_name, "前 30% 窗口缺少商品名", "P0"),
            ("CIT-12", 50, facts.has_price, "前 30% 窗口缺少价格", "P1"),
        ]
    else:
        checks = [
            ("CIT-01", 25, facts.has_name, "前 30% 窗口缺少商品名", "P0"),
            ("CIT-02", 25, facts.has_price, "前 30% 窗口缺少价格或货币", "P0"),
            ("CIT-03", 25, facts.has_spec, "前 30% 窗口缺少带单位的规格", "P1"),
            ("CIT-04", 25, facts.has_quotable_sentence, "前 30% 窗口缺少可独立引用的句子", "P1"),
        ]
    return _sum(checks, "citability", facts.excerpt)


def _entity(doc: Document) -> tuple[int, list[Issue]]:
    if doc.page_type in {"category", "store"}:
        count = len(doc.product_links)
        named = round(count / 3 * 40) if count < 3 else 40
        priced = 30 if any(link.price is not None for link in doc.product_links) else 0
        titled = 15 if (doc.store_name or doc.h1 or doc.title) else 0
        branded = 15 if (doc.brand or doc.store_name) else 0
        checks = [
            ("ENT-11", named, count >= 3, "缺少至少 3 个带链接的商品名", "P1", f"{count} 个商品链接"),
            ("ENT-12", 30 if priced else 0, priced == 30, "代表性商品缺少价格", "P1", ""),
            ("ENT-13", titled, titled == 15, "缺少分类名或店铺名", "P1", doc.store_name or ""),
            ("ENT-14", branded, branded == 15, "缺少品牌或店铺名", "P1", doc.brand or doc.store_name or ""),
        ]
        score = named + priced + titled + branded
        issues = []
        for rule_id, points, ok, message, severity, evidence in checks:
            if not ok:
                issues.append(Issue(rule_id, severity, "entity", message, evidence))
            elif rule_id == "ENT-11" and points != 40:
                issues.append(Issue(rule_id, "P1", "entity", message, evidence))
        return score, issues
    checks = [
        ("ENT-01", 20, doc.price is not None, "未提取到价格"),
        ("ENT-02", 20, bool(doc.specs), "未提取到规格"),
        ("ENT-03", 20, bool(doc.stock), "未提取到库存"),
        ("ENT-04", 20, bool(doc.brand), "未提取到品牌"),
        ("ENT-05", 20, bool(doc.shipping), "未提取到物流信息"),
    ]
    return _sum([(item[0], item[1], item[2], item[3], "P1") for item in checks], "entity", "")


def _structure(doc: Document) -> tuple[int, list[Issue]]:
    title_ok = _shares(doc.title, doc.product_name) or _shares(doc.title, doc.store_name)
    title_ok = title_ok or any(_shares(item, doc.product_name) or _shares(item, doc.store_name) for item in doc.h1)
    checks = [
        ("STR-01", 20, len(doc.h1) == 1, "可见区域不是恰好一个 H1"),
        ("STR-02", 20, doc.h2_count + doc.h3_count > 0, "缺少 H2 或 H3"),
        ("STR-03", 20, doc.has_list or doc.has_table, "缺少列表或表格"),
        ("STR-04", 20, doc.has_faq, "缺少 FAQ"),
        ("STR-05", 20, title_ok, "标题与商品名或店铺名缺少连续相同文字"),
    ]
    return _sum([(item[0], item[1], item[2], item[3], "P1") for item in checks], "structure", doc.title)


def _schema_score(doc: Document) -> tuple[int, list[Issue]]:
    product = _original_product(doc)
    has_name = bool(product and _text(product.get("name")))
    offer = _offer(product)
    offer_ok = False
    if doc.price is None:
        offer_ok = True
    elif offer and offer.get("price") not in (None, "") and offer.get("priceCurrency"):
        offer_ok = _same_price(offer.get("price"), doc.price)
    rating_ok = doc.rating is None
    if doc.rating is not None and product:
        rating = product.get("aggregateRating")
        rating_ok = isinstance(rating, dict) and rating.get("ratingValue") not in (None, "")
    checks = [
        ("SCH-01", 40, has_name, "页面没有带名称的 Product JSON-LD"),
        ("SCH-02", 30, offer_ok, "Offer 价格缺失或与页面价格不一致"),
        ("SCH-03", 30, rating_ok, "页面有评分但 JSON-LD 缺少 ratingValue"),
    ]
    return _sum([(item[0], item[1], item[2], item[3], "P1") for item in checks], "schema", "")


def _technical(doc: Document) -> tuple[int, list[Issue]]:
    visible_ok = len(doc.visible_text) >= 200
    empty = len(doc.visible_text) == 0
    in_visible = True
    if doc.product_name and doc.product_name not in doc.visible_text:
        in_visible = False
    if doc.price is not None and not re.search(re.escape(format(doc.price.normalize(), "f").rstrip("0").rstrip(".")) if False else _price_pattern(doc), doc.visible_text):
        in_visible = False
    checks = [
        ("TEC-01", 40, doc.status_code == 200, "HTTP 状态不是 200", "P1"),
        ("TEC-02", 30, visible_ok, "可见正文过短" if not empty else "可见正文为空", "P0" if empty else "P1"),
        ("TEC-03", 15, not doc.truncated, "响应被截断", "P1"),
        ("TEC-04", 15, in_visible, "商品名或价格只出现在脚本中", "P1"),
    ]
    score = 0
    issues = []
    for rule_id, points, ok, message, severity in checks:
        if ok:
            score += points
        else:
            issues.append(Issue(rule_id, severity, "technical", message, doc.visible_text[:80]))
    return score, issues


def _price_pattern(doc: Document) -> str:
    if doc.price is None:
        return r"$^"
    plain = format(doc.price, "f")
    if "." in plain:
        plain = plain.rstrip("0").rstrip(".")
    return re.escape(plain)


def _sum(checks, dimension: str, evidence: str) -> tuple[int, list[Issue]]:
    score = 0
    issues = []
    for rule_id, points, ok, message, severity in checks:
        if ok:
            score += points
        else:
            issues.append(Issue(rule_id, severity, dimension, message, evidence[:180] if evidence else ""))
    return score, issues


def _original_product(doc: Document) -> dict | None:
    named = [item for item in doc.products if _text(item.get("name"))]
    if named:
        return named[0]
    return doc.products[0] if doc.products else None


def _offer(product: dict | None) -> dict | None:
    if not product:
        return None
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    return offers if isinstance(offers, dict) else None


def _same_price(left, right) -> bool:
    try:
        return round(float(left), 2) == round(float(right), 2)
    except (TypeError, ValueError):
        return False


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _shares(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    a = re.sub(r"\s+", "", left)
    b = re.sub(r"\s+", "", right)
    if len(a) < 2 or len(b) < 2:
        return False
    grams = {a[i : i + 2] for i in range(len(a) - 1)}
    return any(b[i : i + 2] in grams for i in range(len(b) - 1))
