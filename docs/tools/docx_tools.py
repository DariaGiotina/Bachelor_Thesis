"""Append-only helpers for the thesis and paper .docx drafts.

New sections are inserted before the reference list heading, so the references
stay at the end; references are appended only if their URL is not listed yet.
Existing content (including manual edits made in Word) is never rewritten.
"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

REF_HEADINGS = {"Bibliografie", "References"}


class DocAppender:
    def __init__(self, path: str, ref_heading: str):
        self.path = path
        self.doc = Document(path)
        self.ref_heading = ref_heading
        self.anchor = next((p for p in self.doc.paragraphs if p.text.strip() in REF_HEADINGS), None)
        if self.anchor is None:
            self.anchor = self.doc.add_heading(ref_heading, level=1)

    def has_heading(self, text: str) -> bool:
        return any(p.text.strip() == text and p.style.name.startswith("Heading") for p in self.doc.paragraphs)

    def heading(self, text: str, level: int = 2):
        return self.anchor.insert_paragraph_before(text, style=f"Heading {level}")

    def para(self, text: str):
        p = self.anchor.insert_paragraph_before(text)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Cm(1.25)
        return p

    def bullet(self, text: str):
        return self.anchor.insert_paragraph_before(text, style="List Bullet")

    def table(self, rows: list[list[str]], caption: str | None = None):
        if caption:
            c = self.anchor.insert_paragraph_before(caption)
            c.runs[0].italic = True
        t = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                t.cell(i, j).text = str(v)
                if i == 0:
                    t.cell(i, j).paragraphs[0].runs[0].bold = True
        self.anchor._p.addprevious(t._tbl)
        return t

    def reference(self, text: str, url: str):
        """Append '[n] text. url' to the reference list unless the URL is already there."""
        refs = self._refs()
        if any(url in p.text for p in refs):
            return
        p = self.doc.add_paragraph(f"[{len(refs) + 1}] {text}. {url}")
        p.paragraph_format.first_line_indent = Cm(0)

    def ref_number(self, url: str) -> int:
        for i, p in enumerate(self._refs(), 1):
            if url in p.text:
                return i
        raise KeyError(url)

    def _refs(self):
        ps = self.doc.paragraphs
        start = next(i for i, p in enumerate(ps) if p._p is self.anchor._p)
        return [p for p in ps[start + 1:] if p.text.strip().startswith("[")]

    def save(self):
        self.doc.save(self.path)
