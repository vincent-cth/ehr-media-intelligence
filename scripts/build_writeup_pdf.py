from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "WRITEUP.md"
OUTPUT = ROOT / "WRITEUP.pdf"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "WriteupTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        ),
        "heading": ParagraphStyle(
            "WriteupHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12,
            textColor=colors.HexColor("#0f766e"),
            spaceBefore=4,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "WriteupBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.3,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=4,
        ),
    }


def build_pdf(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    styles = _styles()
    story = []
    paragraphs = [part.strip() for part in source.read_text(encoding="utf-8").split("\n\n") if part.strip()]
    for paragraph in paragraphs:
        if paragraph.startswith("# "):
            story.append(Paragraph(escape(paragraph[2:]), styles["title"]))
        elif paragraph.startswith("## "):
            story.append(Spacer(1, 2))
            story.append(Paragraph(escape(paragraph[3:]), styles["heading"]))
        else:
            story.append(Paragraph(escape(" ".join(paragraph.splitlines())), styles["body"]))

    document = SimpleDocTemplate(
        str(output),
        pagesize=LETTER,
        leftMargin=0.48 * inch,
        rightMargin=0.48 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
        title="EHR Media Intelligence Platform - Short Write-up",
        author="AI Full-stack Internship Candidate",
    )
    document.build(story)
    return output


if __name__ == "__main__":
    print(build_pdf())
