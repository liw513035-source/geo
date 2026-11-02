import json
from urllib import error, request

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.extract import Document
from app.score import ScoreResult

PROMPT = """你是电商页面文案编辑。只根据给定材料写中文 JSON，不要编造材料里没有的价格、库存和评分。
只返回 JSON，对象包含：
description：80到300字的自包含商品描述
faq：1到4条，每条有 q 和 a
question_titles：1到3条问题式标题
"""


def generate(doc: Document, scored: ScoreResult, configs: list[dict], url: str) -> tuple[dict, dict | None]:
    enabled = [item for item in configs if item.get("enabled")]
    if not enabled:
        return _unavailable("no_model"), None
    last_reason = "model_error"
    for config in sorted(enabled, key=lambda item: item["priority"]):
        try:
            api_key = _decrypt(config["api_key_encrypted"])
        except InvalidToken:
            last_reason = "model_error"
            continue
        try:
            payload, usage = _call(config, api_key, doc, scored, url)
        except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            last_reason = "model_error"
            continue
        parsed = _validate(payload)
        if parsed is None:
            last_reason = "invalid_output"
            continue
        parsed["status"] = "ok"
        parsed["reason"] = None
        return parsed, usage
    return _unavailable(last_reason), None


def _decrypt(token: str) -> str:
    return Fernet(settings.geo_master_key.encode()).decrypt(token.encode()).decode()


def encrypt_secret(secret: str) -> str:
    return Fernet(settings.geo_master_key.encode()).encrypt(secret.encode()).decode()


def _call(config: dict, api_key: str, doc: Document, scored: ScoreResult, page_url: str) -> tuple[dict, dict]:
    material = {
        "url": page_url,
        "page_type": doc.page_type,
        "name": doc.product_name,
        "brand": doc.brand,
        "price": str(doc.price) if doc.price is not None else None,
        "currency": doc.currency,
        "stock": doc.stock,
        "specs": doc.specs[:8],
        "shipping": doc.shipping,
        "score": scored.score,
        "issue_ids": [item["id"] for item in scored.issues if item["severity"] in {"P0", "P1"}],
        "window": doc.window[:4000],
    }
    body = json.dumps(
        {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(material, ensure_ascii=False)},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": 1200,
        }
    ).encode()
    base = "https://api.deepseek.com" if config["provider"] == "deepseek" else "https://api.openai.com/v1"
    url = base.rstrip("/") + "/chat/completions"
    req = request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode())
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)
    return _load_json(content), {"model": config["model"], "tokens": tokens}


def _load_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def _validate(data: dict) -> dict | None:
    description = data.get("description")
    faq = data.get("faq")
    titles = data.get("question_titles")
    if not isinstance(description, str) or not 1 <= len(description) <= 1200:
        return None
    if not isinstance(faq, list) or not 1 <= len(faq) <= 6:
        return None
    clean_faq = []
    for item in faq:
        if not isinstance(item, dict):
            return None
        question = item.get("q")
        answer = item.get("a")
        if not isinstance(question, str) or not isinstance(answer, str):
            return None
        if not 1 <= len(question) <= 300 or not 1 <= len(answer) <= 300:
            return None
        clean_faq.append({"q": question, "a": answer})
    if not isinstance(titles, list) or not 1 <= len(titles) <= 5:
        return None
    clean_titles = []
    for title in titles:
        if not isinstance(title, str) or not 1 <= len(title) <= 80:
            return None
        clean_titles.append(title)
    return {"description": description, "faq": clean_faq, "question_titles": clean_titles}


def _unavailable(reason: str) -> dict:
    return {
        "status": "unavailable",
        "description": "",
        "faq": [],
        "question_titles": [],
        "reason": reason,
    }


def public_suggestions(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "reason"}
