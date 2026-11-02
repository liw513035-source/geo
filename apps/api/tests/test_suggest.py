from app.extract import parse_html
from app.score import score_document
from app.suggest import generate

HTML = "<html><head><title>杯子</title></head><body><h1>杯子</h1><p>杯子售价 10 元。</p></body></html>"


def test_no_model_keeps_score_and_hides_reason_from_public_shape():
    document = parse_html(HTML)
    scored = score_document(document)
    suggestions, usage = generate(document, scored, [], "https://shop.example/p/1")
    assert suggestions["status"] == "unavailable"
    assert suggestions["reason"] == "no_model"
    assert usage is None
    assert scored.score >= 0
