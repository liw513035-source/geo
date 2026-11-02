import json
from pathlib import Path

from fpdf import FPDF

FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def to_markdown(row: dict) -> str:
    dimensions = row["dimensions"]
    issues = [item for item in row["issues"] if item.get("severity") in {"P0", "P1"}]
    suggestions = json.loads(row["suggestions"]) if isinstance(row["suggestions"], str) else row["suggestions"]
    lines = [
        f"# VertiGEO 评分报告",
        "",
        f"- URL：{row['url']}",
        f"- 时间：{row['created_at']}",
        f"- 总分：{row['score']}",
        "",
        "## 维度",
        "",
        f"- 可引用性：{dimensions.get('citability')}",
        f"- 实体完整性：{dimensions.get('entity')}",
        f"- 结构清晰度：{dimensions.get('structure')}",
        f"- Schema：{dimensions.get('schema')}",
        f"- 技术可访问性：{dimensions.get('technical')}",
        "",
        "## 问题",
        "",
    ]
    if not issues:
        lines.append("没有扣分项。")
    for item in issues:
        lines.append(f"- [{item['severity']}] {item['id']} {item['message']}")
    lines.extend(["", "## 建议", ""])
    if suggestions and suggestions.get("status") == "ok":
        lines.append(suggestions.get("description") or "")
        for faq in suggestions.get("faq") or []:
            lines.extend(["", f"### {faq['q']}", "", faq["a"]])
        lines.extend(["", "## 问题式标题", ""])
        for title in suggestions.get("question_titles") or []:
            lines.append(f"- {title}")
    else:
        lines.append("建议暂时无法生成。")
    lines.extend(["", "## Schema", "", "```json", json.dumps(row["schema_json"], ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def to_pdf(markdown: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("yh", "", str(FONT))
    pdf.set_font("yh", size=11)
    for line in markdown.splitlines():
        if line.startswith("```"):
            continue
        pdf.multi_cell(pdf.epw, 7, line if line else " ")
    return bytes(pdf.output())
