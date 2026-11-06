import html
import io
import re
from decimal import Decimal
from lxml import html as dom
import bleach
from bleach.css_sanitizer import CSSSanitizer
import pymupdf
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TAGS = [
    "p",
    "div",
    "br",
    "h1",
    "h2",
    "h3",
    "h4",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ol",
    "ul",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "span",
    "blockquote",
]


def safe_html(content):
    # Preserve legacy plain-text drafts, while accepting only the editor's HTML subset.
    if not re.search(
        r"</?(?:p|div|h[1-4]|table|ul|ol|br|span|strong|b|i|u)\b", content, re.I
    ):
        content = "<p>" + html.escape(content).replace("\n", "<br>") + "</p>"
    return bleach.clean(
        content,
        tags=TAGS,
        attributes={
            "*": ["style", "class"],
            "td": ["colspan", "rowspan"],
            "th": ["colspan", "rowspan"],
        },
        css_sanitizer=CSSSanitizer(
            allowed_css_properties=[
                "text-align",
                "font-weight",
                "font-style",
                "text-decoration",
                "page-break-after",
                "break-after",
            ]
        ),
        strip=True,
    )


def pdf(content, title=""):
    content = safe_html(content)
    story = pymupdf.Story(
        "<html><body>" + content + "</body></html>",
        user_css="body{font-family:serif;font-size:12pt;line-height:1.6}h1{font-size:20pt}h2{font-size:16pt}table{width:100%;border-collapse:collapse}td,th{border:1px solid #777;padding:6pt}.page-break{page-break-after:always}",
    )
    stream = io.BytesIO()
    writer = pymupdf.DocumentWriter(stream)
    try:
        for _ in range(150):
            device = writer.begin_page(pymupdf.paper_rect("a4"))
            more, _ = story.place(pymupdf.Rect(54, 54, 541, 784))
            story.draw(device)
            writer.end_page()
            if not more:
                break
        else:
            raise ValueError("Document exceeds 150 pages")
    finally:
        writer.close()
    doc = pymupdf.open(stream=stream.getvalue(), filetype="pdf")
    for page in doc:
        page.insert_text((54, 815), f"{page.number + 1} / {len(doc)}", fontsize=9)
    return doc.tobytes(garbage=4, deflate=True)


def docx(content):
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = section.bottom_margin = section.left_margin = (
        section.right_margin
    ) = Inches(0.75)
    style = document.styles["Normal"]
    style.font.name = "Nirmala UI"
    style.font.size = Pt(12)
    style.paragraph_format.space_after = Pt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    section.footer.paragraphs[0]._p.append(field)

    def inline(element, paragraph, bold=False, italic=False, underline=False):
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        bold = bold or tag in ("b", "strong", "th")
        italic = italic or tag in ("i", "em")
        underline = underline or tag == "u"
        if element.text:
            run = paragraph.add_run(element.text)
            run.bold = bold
            run.italic = italic
            run.underline = underline
        for child in element:
            if child.tag == "br":
                paragraph.add_run().add_break()
            else:
                inline(child, paragraph, bold, italic, underline)
            if child.tail:
                run = paragraph.add_run(child.tail)
                run.bold = bold
                run.italic = italic
                run.underline = underline

    def block(element):
        tag = element.tag
        if tag == "table":
            rows = element.xpath(".//tr")
            width = max((len(row.xpath("./td|./th")) for row in rows), default=1)
            table = document.add_table(rows=0, cols=width)
            table.style = "Table Grid"
            for row in rows:
                cells = table.add_row().cells
                for i, cell in enumerate(row.xpath("./td|./th")):
                    inline(cell, cells[i].paragraphs[0])
        elif tag in ("ul", "ol"):
            for item in element:
                paragraph = document.add_paragraph(
                    style="List Number" if tag == "ol" else "List Bullet"
                )
                inline(item, paragraph)
        elif tag in ("div",) and any(
            child.tag in ("p", "div", "table", "ol", "ul") for child in element
        ):
            for child in element:
                block(child)
        else:
            paragraph = document.add_paragraph(
                style="Heading " + tag[1] if tag in ("h1", "h2", "h3", "h4") else None
            )
            inline(element, paragraph)
            alignment = re.search(
                r"text-align:\s*(left|center|right|justify)", element.get("style", "")
            )
            if alignment:
                paragraph.alignment = {
                    "left": WD_ALIGN_PARAGRAPH.LEFT,
                    "center": WD_ALIGN_PARAGRAPH.CENTER,
                    "right": WD_ALIGN_PARAGRAPH.RIGHT,
                    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                }[alignment[1]]
        if "page-break" in element.get(
            "class", ""
        ) or "page-break-after: always" in element.get("style", ""):
            document.add_page_break()

    root = dom.fragment_fromstring(safe_html(content), create_parent="div")
    for element in root:
        block(element)
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()
