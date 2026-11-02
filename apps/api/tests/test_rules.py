from pathlib import Path

import pytest

from app.errors import AppError
from app.extract import parse_html
from app.fetch import ResponseLike, assert_public_url, fetch
from app.score import score_document

ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "pages"


def _score(name: str):
    html = (ROOT / name).read_text(encoding="utf-8")
    return score_document(parse_html(html))


def test_private_targets_are_rejected_before_request():
    for url in ("http://127.0.0.1/", "http://169.254.169.254/", "http://10.1.1.1/", "http://user:pass@shop.example/"):
        with pytest.raises(AppError) as caught:
            assert_public_url(url)
        assert caught.value.code in {"FORBIDDEN_TARGET", "INVALID_URL"}


def test_redirect_to_metadata_is_not_requested(monkeypatch):
    calls = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        ip = "169.254.169.254" if host == "169.254.169.254" else "93.184.216.34"
        return [(2, 1, 6, "", (ip, port))]

    monkeypatch.setattr("app.fetch.socket.getaddrinfo", fake_getaddrinfo)

    def opener(url: str) -> ResponseLike:
        calls.append(url)
        return ResponseLike(302, {"location": "http://169.254.169.254/latest"})

    with pytest.raises(AppError) as caught:
        fetch("http://example.com/item", opener=opener)
    assert caught.value.code == "FORBIDDEN_TARGET"
    assert calls == ["http://example.com/item"]


def test_complete_product_score_is_stable():
    first = _score("product-complete.html")
    second = _score("product-complete.html")
    assert first.score == second.score
    assert [item["id"] for item in first.issues] == [item["id"] for item in second.issues]
    assert first.page_type == "product"
    assert first.schema_json["@type"] == "Product"
    assert first.schema_json["name"] == "Acme 保温杯"
    assert "CIT-02" not in {item["id"] for item in first.issues if item["severity"] == "P0"}


def test_missing_price_is_p0():
    scored = _score("product-missing-price.html")
    severe = {item["id"] for item in scored.issues if item["severity"] == "P0"}
    assert "CIT-02" in severe


def test_category_page():
    scored = _score("category.html")
    assert scored.page_type == "category"
    assert scored.dimensions["citability"] > 0


def test_non_html_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "app.fetch.socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )

    def opener(url: str) -> ResponseLike:
        return ResponseLike(200, {"content-type": "application/json"}, b"{}")

    with pytest.raises(AppError) as caught:
        fetch("http://example.com/data", opener=opener)
    assert caught.value.code == "FETCH_FAILED"