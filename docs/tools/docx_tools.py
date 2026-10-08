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


# --------------------------------------------------------------------------------------
# DocEditor: for the structured thesis (Teza_Licenta.docx) and paper (Paper_Skin_Concern.docx).
# Inserts new sections in the middle of a chapter, renumbers later headings (and the static
# table-of-contents lines) and clones the formatting of existing paragraphs.
# --------------------------------------------------------------------------------------
import copy  # noqa: E402
import re  # noqa: E402

from docx.oxml.ns import qn  # noqa: E402
from docx.text.paragraph import Paragraph  # noqa: E402


class DocEditor:
    def __init__(self, path: str):
        self.path = path
        self.doc = Document(path)
        ps = self.doc.paragraphs
        self.body_tpl = next(p for p in ps if p.style.name == "Normal" and len(p.text) > 200
                             and p._p.pPr is not None and p._p.pPr.find(qn("w:jc")) is not None)
        self.code_rpr = next(r._r.rPr for p in ps for r in p.runs
                             if r._r.rPr is not None and r._r.rPr.find(qn("w:rFonts")) is not None
                             and r._r.rPr.find(qn("w:rFonts")).get(qn("w:ascii")) == "Courier New"
                             and "/" not in r.text and "." not in r.text)

    # -- lookup ------------------------------------------------------------------------
    def heading(self, text: str) -> Paragraph:
        return next(p for p in self.doc.paragraphs
                    if p.style.name.startswith("Heading") and p.text.strip() == text)

    def has_heading(self, text: str) -> bool:
        return any(p.style.name.startswith("Heading") and p.text.strip() == text for p in self.doc.paragraphs)

    def toc_entries(self, text: str) -> list[Paragraph]:
        return [p for p in self.doc.paragraphs if p.style.name.lower().startswith("toc")
                and p.text.split("\t")[0].strip() == text]

    # -- building ----------------------------------------------------------------------
    def _new_after(self, anchor_p, style: str | None = None) -> Paragraph:
        new = copy.deepcopy(anchor_p._p)
        for child in list(new):
            if child.tag != qn("w:pPr"):
                new.remove(child)
        anchor_p._p.addnext(new)
        par = Paragraph(new, anchor_p._parent)
        if style:
            par.style = self.doc.styles[style]
        return par

    def body_paragraph_before(self, anchor: Paragraph, text: str) -> Paragraph:
        """Insert a body paragraph before `anchor`; `code` spans become Courier New runs."""
        new = copy.deepcopy(self.body_tpl._p)
        for child in list(new):
            if child.tag != qn("w:pPr"):
                new.remove(child)
        anchor._p.addprevious(new)
        par = Paragraph(new, anchor._parent)
        for i, chunk in enumerate(re.split(r"`([^`]+)`", text)):
            if not chunk:
                continue
            run = par.add_run(chunk)
            if i % 2 == 1:
                run._r.insert(0, copy.deepcopy(self.code_rpr))
        return par

    def heading_before(self, anchor: Paragraph, text: str, level: int) -> Paragraph:
        par = anchor.insert_paragraph_before(text, style=f"Heading {level}")
        return par

    def add_toc_entry_before(self, toc_entry: Paragraph, text: str, page: str) -> None:
        new = copy.deepcopy(toc_entry._p)
        toc_entry._p.addprevious(new)
        par = Paragraph(new, toc_entry._parent)
        ts = par._p.findall(".//" + qn("w:t"))
        ts[0].text, ts[-1].text = text, page

    # -- renumbering -------------------------------------------------------------------
    def rename_heading(self, old: str, new: str) -> None:
        """Rename a heading and its table-of-contents line(s)."""
        h = self.heading(old)
        self._set_text(h, new)
        for e in self.toc_entries(old):
            ts = e._p.findall(".//" + qn("w:t"))
            ts[0].text = new

    def replace_in_paragraph(self, startswith: str, old: str, new: str) -> None:
        p = next(p for p in self.doc.paragraphs if p.text.startswith(startswith))
        for r in p.runs:
            if old in r.text:
                r.text = r.text.replace(old, new)
                return
        raise ValueError(f"'{old}' not found in paragraph starting '{startswith}'")

    @staticmethod
    def _set_text(par: Paragraph, text: str) -> None:
        runs = par.runs
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)

    def save(self) -> None:
        self.doc.save(self.path)
