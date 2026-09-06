from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "WRITEUP.md"
OUTPUT = ROOT / "WRITEUP.pdf"

NAVY = colors.HexColor("#0B1F33")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748B")
TEAL = colors.HexColor("#0F766E")
TEAL_LIGHT = colors.HexColor("#CCFBF1")
BLUE_LIGHT = colors.HexColor("#E0F2FE")
PAGE = colors.HexColor("#F8FAFC")
WHITE = colors.white
LINE = colors.HexColor("#CBD5E1")
GREEN = colors.HexColor("#047857")

BODY = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=8.35,
    leading=11.1,
    textColor=SLATE,
    spaceAfter=5,
)
SECTION = ParagraphStyle(
    "Section",
    fontName="Helvetica-Bold",
    fontSize=9.2,
    leading=11,
    textColor=NAVY,
    spaceAfter=4,
)
BULLET = ParagraphStyle(
    "Bullet",
    parent=BODY,
    leftIndent=12,
    firstLineIndent=-10,
    bulletIndent=0,
    spaceAfter=3,
)


def parse_source(path: Path) -> tuple[str, str, list[tuple[str, list[str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = lines[0].removeprefix("# ").strip()
    subtitle = next(line.strip() for line in lines[1:] if line.strip())
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    blocks: list[str] = []
    for line in lines[2:]:
        if line.startswith("## "):
            if heading:
                sections.append((heading, blocks))
            heading = line[3:].strip()
            blocks = []
        elif line.strip():
            blocks.append(line.strip())
    if heading:
        sections.append((heading, blocks))
    return title, subtitle, sections


def draw_paragraph(
    pdf: canvas.Canvas,
    text: str,
    style: ParagraphStyle,
    x: float,
    top: float,
    width: float,
) -> float:
    paragraph = Paragraph(escape(text), style)
    _, height = paragraph.wrap(width, 10 * inch)
    paragraph.drawOn(pdf, x, top - height)
    return top - height


def draw_section(
    pdf: canvas.Canvas,
    heading: str,
    blocks: list[str],
    x: float,
    top: float,
    width: float,
    highlighted: bool = False,
) -> float:
    number, _, label = heading.partition(" ")
    if highlighted:
        heading_flowable = Paragraph(escape(label.upper()), SECTION)
        _, heading_height = heading_flowable.wrap(width - 27, 10 * inch)
        content_height = heading_height + 5
        for block in blocks:
            text = f"• {block[2:]}" if block.startswith("- ") else block
            style = BULLET if block.startswith("- ") else BODY
            flowable = Paragraph(escape(text), style)
            _, block_height = flowable.wrap(width, 10 * inch)
            content_height += block_height + 3
        pdf.setFillColor(colors.HexColor("#ECFDF5"))
        pdf.roundRect(x - 10, top - content_height - 5, width + 20, content_height + 14, 9, fill=1, stroke=0)

    pdf.setFillColor(TEAL)
    pdf.roundRect(x, top - 10, 20, 14, 4, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawCentredString(x + 10, top - 5.8, number)
    top = draw_paragraph(pdf, label.upper(), SECTION, x + 27, top + 2, width - 27)
    top -= 5

    for block in blocks:
        if block.startswith("- "):
            top = draw_paragraph(pdf, f"• {block[2:]}", BULLET, x, top, width)
        else:
            top = draw_paragraph(pdf, block, BODY, x, top, width)
        top -= 3
    return top - 10


def draw_header(pdf: canvas.Canvas, title: str, subtitle: str) -> None:
    width, height = LETTER
    pdf.setFillColor(PAGE)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 154, width, 154, fill=1, stroke=0)
    pdf.setFillColor(TEAL)
    pdf.rect(0, height - 6, width, 6, fill=1, stroke=0)

    pdf.setFillColor(TEAL_LIGHT)
    pdf.roundRect(36, height - 43, 145, 18, 9, fill=1, stroke=0)
    pdf.setFillColor(TEAL)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawCentredString(108.5, height - 37, "AI FULL-STACK ASSESSMENT")

    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawString(36, height - 77, title)
    pdf.setFillColor(colors.HexColor("#CBD5E1"))
    pdf.setFont("Helvetica", 9.6)
    pdf.drawString(36, height - 98, subtitle)

    stages = ["INGEST", "CLEAN", "FHIR R4", "SUMMARIZE", "SEARCH"]
    x = 36.0
    for index, stage in enumerate(stages):
        stage_width = max(58, stringWidth(stage, "Helvetica-Bold", 7) + 20)
        pdf.setFillColor(colors.HexColor("#173A57"))
        pdf.roundRect(x, height - 134, stage_width, 22, 7, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#BAE6FD"))
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawCentredString(x + stage_width / 2, height - 126.5, stage)
        x += stage_width
        if index < len(stages) - 1:
            pdf.setStrokeColor(colors.HexColor("#5EEAD4"))
            pdf.setLineWidth(1.2)
            pdf.line(x + 4, height - 123, x + 13, height - 123)
            pdf.line(x + 10, height - 126, x + 13, height - 123)
            pdf.line(x + 10, height - 120, x + 13, height - 123)
            x += 18


def draw_metrics(pdf: canvas.Canvas) -> None:
    metrics = [
        ("60", "UNIQUE RECORDS"),
        ("20/20", "FHIR BUNDLES VALID"),
        ("15", "AUTOMATED TESTS"),
        ("~0.006s", "50-RECORD SEARCH"),
    ]
    x = 36.0
    top = 652.0
    card_width = 129.0
    for value, label in metrics:
        pdf.setFillColor(colors.HexColor("#DCE3EA"))
        pdf.roundRect(x + 1.5, top - 51.5, card_width, 49, 8, fill=1, stroke=0)
        pdf.setFillColor(WHITE)
        pdf.roundRect(x, top - 50, card_width, 49, 8, fill=1, stroke=0)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(x + 12, top - 23, value)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(x + 12, top - 39, label)
        x += card_width + 8


def draw_footer(pdf: canvas.Canvas) -> None:
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.6)
    pdf.line(36, 38, 576, 38)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.8)
    pdf.drawString(36, 25, "github.com/vincent-cth/ehr-media-intelligence")
    disclaimer = "SYNTHETIC DATA ONLY  |  AI OUTPUT IS NOT A CLINICAL DECISION"
    pdf.setFont("Helvetica-Bold", 6.4)
    pdf.drawRightString(576, 25, disclaimer)


def draw_principles(pdf: canvas.Canvas) -> None:
    pdf.setFillColor(NAVY)
    pdf.roundRect(36, 72, 540, 108, 11, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#5EEAD4"))
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawString(52, 160, "BUILT FOR REVIEWABILITY")

    principles = [
        ("01", "TRACEABLE", "AI output remains paired with source records and cleaning events."),
        ("02", "FAIL TRANSPARENTLY", "FHIR errors, confidence, and fallback status stay visible."),
        ("03", "REPRODUCIBLE", "One command rebuilds data, Bundles, summaries, and the index."),
    ]
    x_positions = [52, 226, 400]
    for x, (number, title, detail) in zip(x_positions, principles):
        pdf.setFillColor(TEAL)
        pdf.circle(x + 10, 134, 10, fill=1, stroke=0)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawCentredString(x + 10, 131.7, number)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(x + 27, 131.5, title)
        principle_style = ParagraphStyle(
            f"Principle{number}",
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=colors.HexColor("#CBD5E1"),
        )
        paragraph = Paragraph(escape(detail), principle_style)
        _, paragraph_height = paragraph.wrap(148, 40)
        paragraph.drawOn(pdf, x, 91 + (28 - paragraph_height))


def build_pdf(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    title, subtitle, sections = parse_source(source)
    if len(sections) != 6:
        raise ValueError("WRITEUP.md must contain exactly six numbered sections")

    pdf = canvas.Canvas(str(output), pagesize=LETTER)
    pdf.setTitle(title)
    pdf.setAuthor("AI Full-stack Internship Candidate")
    pdf.setSubject("EHR Media Intelligence Platform assessment write-up")
    draw_header(pdf, title, subtitle)
    draw_metrics(pdf)

    left_x, right_x = 36.0, 318.0
    column_width = 258.0
    left_top = right_top = 580.0
    for heading, blocks in sections[:3]:
        left_top = draw_section(pdf, heading, blocks, left_x, left_top, column_width)
    for index, (heading, blocks) in enumerate(sections[3:]):
        right_top = draw_section(
            pdf,
            heading,
            blocks,
            right_x,
            right_top,
            column_width,
            highlighted=index == 1,
        )

    if min(left_top, right_top) < 190:
        raise ValueError("Write-up content overflows the one-page layout")
    draw_principles(pdf)
    draw_footer(pdf)
    pdf.showPage()
    pdf.save()
    return output


if __name__ == "__main__":
    print(build_pdf())
