#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "reportlab>=4.2,<5",
# ]
# ///

# How to run
# 1. Install uv if it is not installed.
# 2. Run: uv run scripts/Build-AiWorkerGuidePdf.py
# 3. Optional: uv run scripts/Build-AiWorkerGuidePdf.py input.md output.pdf

from __future__ import annotations

import html
import re
import sys
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "AI_WORKER_COMPLETE_GUIDE.md"
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "AI_WORKER_COMPLETE_GUIDE.pdf"
FONT_REGULAR = Path("C:/Windows/Fonts/malgun.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/malgunbd.ttf")


def register_fonts() -> None:
    """Register a Windows Korean font so Hangul is embedded in the PDF."""
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise FileNotFoundError("Malgun Gothic fonts were not found")
    pdfmetrics.registerFont(TTFont("Malgun", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Malgun-Bold", str(FONT_BOLD)))


def inline_markup(value: str) -> str:
    """Convert the small Markdown subset used by the guide into safe XML."""
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", escaped)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Malgun-Bold">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    return escaped


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    """Create a Korean-safe paragraph."""
    return Paragraph(inline_markup(text), style)


def table_rows(lines: list[str]) -> list[list[str]]:
    """Parse a contiguous Markdown table and remove its separator row."""
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    width = max((len(row) for row in rows), default=1)
    return [row + [""] * (width - len(row)) for row in rows]


def build_table(rows: list[list[str]], body: ParagraphStyle) -> Table:
    """Build a readable table that can split across PDF pages."""
    column_count = max(len(row) for row in rows)
    cell_style = ParagraphStyle(
        "TableCell",
        parent=body,
        fontName="Malgun",
        fontSize=7.2,
        leading=9.2,
        spaceAfter=0,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=cell_style,
        fontName="Malgun-Bold",
        textColor=colors.HexColor("#102A43"),
    )
    data = [
        [Paragraph(inline_markup(cell), header_style if index == 0 else cell_style) for cell in row]
        for index, row in enumerate(rows)
    ]
    usable_width = A4[0] - 30 * mm
    table = Table(data, colWidths=[usable_width / column_count] * column_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2F8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#102A43")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C7D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def parse_markdown(markdown: str) -> list[object]:
    """Convert the guide's Markdown into ReportLab flowables."""
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "GuideBody", parent=styles["BodyText"], fontName="Malgun", fontSize=9.2,
        leading=14, spaceAfter=6, wordWrap="CJK", alignment=TA_LEFT,
    )
    quote = ParagraphStyle(
        "GuideQuote", parent=body, leftIndent=14, rightIndent=8,
        borderColor=colors.HexColor("#8AA5BF"), borderWidth=0.7,
        borderPadding=6, backColor=colors.HexColor("#F4F8FB"),
    )
    bullet = ParagraphStyle("GuideBullet", parent=body, leftIndent=14, firstLineIndent=-9)
    h1 = ParagraphStyle("GuideH1", parent=body, fontName="Malgun-Bold", fontSize=18, leading=23,
                        textColor=colors.HexColor("#102A43"), spaceBefore=14, spaceAfter=8,
                        keepWithNext=True)
    h2 = ParagraphStyle("GuideH2", parent=body, fontName="Malgun-Bold", fontSize=14, leading=19,
                        textColor=colors.HexColor("#1F4E79"), spaceBefore=12, spaceAfter=6,
                        keepWithNext=True)
    h3 = ParagraphStyle("GuideH3", parent=body, fontName="Malgun-Bold", fontSize=11.5, leading=16,
                        textColor=colors.HexColor("#2F6690"), spaceBefore=9, spaceAfter=4,
                        keepWithNext=True)
    h4 = ParagraphStyle("GuideH4", parent=body, fontName="Malgun-Bold", fontSize=10.5, leading=15,
                        spaceBefore=7, spaceAfter=3, keepWithNext=True)
    code = ParagraphStyle("GuideCode", parent=body, fontName="Malgun", fontSize=6.7, leading=8.7,
                          leftIndent=6, rightIndent=6, backColor=colors.HexColor("#F3F5F7"),
                          borderColor=colors.HexColor("#D7DEE7"), borderWidth=0.5,
                          borderPadding=5, wordWrap="CJK")
    story: list[object] = []
    lines = markdown.splitlines()
    index = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            story.append(paragraph(" ".join(line.strip() for line in paragraph_lines), body))
            paragraph_lines.clear()

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush_paragraph()
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            wrapped = "\n".join(
                "\n".join(textwrap.wrap(row, width=120, replace_whitespace=False) or [""])
                for row in block
            )
            story.append(Preformatted(wrapped, code))
            story.append(Spacer(1, 3))
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            style = {1: h1, 2: h2, 3: h3, 4: h4}[level]
            story.append(paragraph(heading.group(2), style))
            index += 1
            continue
        if line.strip() == "---":
            flush_paragraph()
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#B8C7D9")))
            story.append(Spacer(1, 4))
            index += 1
            continue
        if line.startswith("|") and "|" in line:
            flush_paragraph()
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            story.append(build_table(table_rows(block), body))
            story.append(Spacer(1, 6))
            continue
        if line.startswith("> "):
            flush_paragraph()
            story.append(paragraph(line[2:], quote))
            index += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_paragraph()
            item = re.sub(r"^\s*[-*]\s+", "", line)
            story.append(Paragraph(f"<bullet>&bull;</bullet>{inline_markup(item)}", bullet))
            index += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_paragraph()
            item = re.sub(r"^\s*\d+\.\s+", "", line)
            story.append(Paragraph(f"<bullet>&bull;</bullet>{inline_markup(item)}", bullet))
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
        else:
            paragraph_lines.append(line)
        index += 1
    flush_paragraph()
    return story


def draw_footer(canvas: Canvas, document: SimpleDocTemplate) -> None:
    """Draw a restrained footer on every page."""
    canvas.saveState()
    canvas.setFont("Malgun", 7.5)
    canvas.setFillColor(colors.HexColor("#607D8B"))
    canvas.drawString(15 * mm, 9 * mm, "EYES:ON U AI Worker 전체 안내서")
    canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{document.page}")
    canvas.restoreState()


def make_pdf(input_path: Path, output_path: Path) -> None:
    """Render the Markdown guide into an embedded-font PDF."""
    register_fonts()
    markdown = input_path.read_text(encoding="utf-8")
    document = SimpleDocTemplate(
        str(output_path), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=16 * mm, title="EYES:ON U AI Worker 전체 안내서",
        author="Codex",
    )
    cover_title = ParagraphStyle(
        "CoverTitle", fontName="Malgun-Bold", fontSize=25, leading=34,
        textColor=colors.HexColor("#102A43"), alignment=TA_CENTER, spaceAfter=14,
    )
    cover_subtitle = ParagraphStyle(
        "CoverSubtitle", fontName="Malgun", fontSize=11, leading=18,
        textColor=colors.HexColor("#486581"), alignment=TA_CENTER,
    )
    cover = [
        Spacer(1, 35 * mm),
        Paragraph("EYES:ON U", cover_title),
        Paragraph("AI Worker 전체 제작·연결·학습 안내서", cover_title),
        Spacer(1, 10 * mm),
        Paragraph("중학교 2학년도 이해할 수 있도록 설명한 현재 상태 보고서", cover_subtitle),
        Spacer(1, 8 * mm),
        Paragraph("작성 기준일: 2026-08-06", cover_subtitle),
        Spacer(1, 25 * mm),
        Table(
            [[Paragraph(inline_markup("현재 기본 후보 엔진"), cover_subtitle),
              Paragraph(inline_markup("YOLO11x + ByteTrack + CLIP ViT-L/14"), cover_subtitle)],
             [Paragraph(inline_markup("기준 사진이 있을 때"), cover_subtitle),
              Paragraph(inline_markup("SOLIDER Swin-Base ReID 추가"), cover_subtitle)],
             [Paragraph(inline_markup("자동 신원 확정"), cover_subtitle),
              Paragraph(inline_markup("아직 production 승인하지 않음"), cover_subtitle)]],
            colWidths=[55 * mm, 105 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8FB")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#8AA5BF")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C7D9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]),
        ),
        PageBreak(),
    ]
    story = cover + parse_markdown(markdown)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)


def main() -> int:
    """Read the guide and create the requested PDF."""
    input_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_OUTPUT
    make_pdf(input_path, output_path)
    print(f"created {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
