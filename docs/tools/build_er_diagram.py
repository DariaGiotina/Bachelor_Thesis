"""Build docs/diagrams/skincare_eer.drawio (EER model, Chen notation, plus the relational mapping).

Page 1 is the conceptual Entity-Relationship model with one EER component (the disjoint, total
specialization of PHOTO). Page 2 is the logical relational schema mapped from it.
The layout is placed by hand (coordinates below). Re-running this script overwrites the file,
so make manual edits in draw.io only after the model is final.

Usage: python docs/tools/build_er_diagram.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[1] / "diagrams" / "skincare_eer.drawio"

FONT = "fontFamily=Helvetica;fontSize=13;"
C_ENT = "fillColor=#dae8fc;strokeColor=#6c8ebf;"
C_REL = "fillColor=#fff2cc;strokeColor=#d6b656;"
C_ATT = "fillColor=#ffffff;strokeColor=#666666;"
C_SPEC = "fillColor=#f8cecc;strokeColor=#b85450;"
LINE = "endArrow=none;html=1;rounded=0;strokeColor=#555555;"


class Page:
    def __init__(self, name: str, pid: str):
        self.name, self.pid = name, pid
        self.cells: list[str] = []
        self.pos: dict[str, tuple[float, float, float, float]] = {}
        self.n = 0

    def _id(self) -> str:
        self.n += 1
        return f"{self.pid}-{self.n}"

    def vertex(self, cid, value, style, x, y, w, h):
        """(x, y) is the centre of the shape."""
        self.pos[cid] = (x, y, w, h)
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(value, {chr(34): "&quot;"})}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x - w / 2:.0f}" y="{y - h / 2:.0f}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def edge(self, src, dst, style=LINE, label="", lx=0.0, ly=0.0, points=None):
        cid = self._id()
        pts = ""
        if points:
            pts = '<Array as="points">' + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points) + "</Array>"
        lab = escape(label)
        self.cells.append(
            f'<mxCell id="{cid}" value="{lab}" style="{FONT}fontStyle=1;labelBackgroundColor=#ffffff;{style}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">'
            f'<mxGeometry x="{lx}" y="{ly}" relative="1" as="geometry">{pts}</mxGeometry></mxCell>')
        return cid

    def xml(self) -> str:
        body = "".join(self.cells)
        return (f'<diagram id="{self.pid}" name="{self.name}"><mxGraphModel dx="1600" dy="1000" grid="1" '
                f'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                f'pageWidth="4200" pageHeight="2800" math="0" shadow="0"><root><mxCell id="0"/>'
                f'<mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram>')


# ------------------------------------------------------------------------------------------------
# Page 1: EER model (Chen notation)
# ------------------------------------------------------------------------------------------------
def eer_page() -> Page:
    p = Page("EER model", "eer")

    def entity(name, x, y, weak=False):
        st = f"rounded=0;whiteSpace=wrap;html=1;{C_ENT}{FONT}fontStyle=1;"
        if weak:
            st = f"shape=ext;double=1;margin=4;rounded=0;whiteSpace=wrap;html=1;{C_ENT}{FONT}fontStyle=1;"
        return p.vertex(name, name, st, x, y, 180, 56)

    def rel(cid, label, x, y, identifying=False):
        st = f"shape=rhombus;perimeter=rhombusPerimeter;whiteSpace=wrap;html=1;{C_REL}{FONT}fontStyle=1;"
        if identifying:
            st += "double=1;"
        return p.vertex(cid, label, st, x, y, 170, 84)

    def attr(owner, name, dx, dy, kind="", parent_edge=True):
        """kind: key | partial | multi | derived | '' ; offsets are relative to the owner centre."""
        ox, oy, _, _ = p.pos[owner]
        text = name
        st = f"ellipse;whiteSpace=wrap;html=1;{C_ATT}{FONT}"
        if kind == "key":
            text = f"<u>{name}</u>"
        elif kind == "partial":
            text = f'<span style="border-bottom:1.5px dashed #000">{name}</span>'
        elif kind == "multi":
            st = f"ellipse;shape=doubleEllipse;margin=3;whiteSpace=wrap;html=1;{C_ATT}{FONT}"
        elif kind == "derived":
            st += "dashed=1;dashPattern=6 4;"
        w = max(96, 9 * len(name) + 34)
        cid = p.vertex(f"{owner}.{name}", text, st, ox + dx, oy + dy, w, 40)
        if parent_edge:
            p.edge(owner, cid)
        return cid

    def link(r, ent, card, total=False, lx=0.62):
        """Relationship-to-entity line; total participation = double line."""
        st = LINE
        if total:
            st = "shape=link;endArrow=none;html=1;rounded=0;strokeColor=#555555;width=4;"
        p.edge(r, ent, st, card, lx, 0)

    # --- title and legend ---------------------------------------------------------------------
    p.vertex("title", "<b>AI-Assisted Skincare Companion App: Enhanced Entity-Relationship (EER) model</b>"
             "<br><font style='font-size:13px'>Chen notation. Cardinality ratios 1, N, M; a double line marks total "
             "participation.</font>",
             f"text;html=1;align=left;verticalAlign=middle;{FONT}fontSize=22;", 900, 60, 1500, 70)

    # --- core entities ----------------------------------------------------------------------------
    entity("USER", 1500, 560)
    entity("CONSENT", 380, 300)
    entity("REFRESH_TOKEN", 380, 560)
    entity("REMINDER", 380, 820)
    entity("SKIN_ANALYSIS", 900, 1250)
    entity("QUESTION", 200, 1150)
    entity("FACE_ZONE", 200, 1500)
    entity("SKIN_CONCERN", 420, 1950)
    entity("ROUTINE", 2080, 1250)
    entity("ROUTINE_STEP", 2080, 1780, weak=True)
    entity("PRODUCT", 3050, 1780)
    entity("INGREDIENT", 2700, 1250)
    entity("DAILY_LOG", 3250, 560)
    entity("PHOTO", 2350, 2200)
    entity("ANALYSIS_PHOTO", 1500, 2480)
    entity("PROGRESS_PHOTO", 3300, 2480)

    # --- relationships -----------------------------------------------------------------------------
    rel("r_gives", "GIVES", 900, 380)
    rel("r_holds", "HOLDS", 900, 560)
    rel("r_sets", "SETS", 900, 740)
    rel("r_keeps", "KEEPS", 2380, 560)
    rel("r_performs", "PERFORMS", 1180, 900)
    rel("r_follows", "FOLLOWS", 1820, 900)
    rel("r_based", "BASED_ON", 1490, 1250)
    rel("r_answers", "ANSWERS", 560, 1150)
    rel("r_assesses", "ASSESSES", 540, 1420)
    rel("r_predicts", "PREDICTS", 680, 1640)
    rel("r_depicts", "DEPICTS", 1230, 1880)
    rel("r_consists", "CONSISTS_OF", 2080, 1510, identifying=True)
    rel("r_uses", "USES", 2560, 1780)
    rel("r_contains", "CONTAINS", 2880, 1510)
    rel("r_records", "RECORDS_USE", 3150, 1180)
    rel("r_documents", "DOCUMENTS", 3600, 1560)

    link("r_gives", "USER", "1"); link("r_gives", "CONSENT", "N", True)
    link("r_holds", "USER", "1"); link("r_holds", "REFRESH_TOKEN", "N", True)
    link("r_sets", "USER", "1"); link("r_sets", "REMINDER", "N", True)
    link("r_keeps", "USER", "1"); link("r_keeps", "DAILY_LOG", "N", True)
    link("r_performs", "USER", "1"); link("r_performs", "SKIN_ANALYSIS", "N", True)
    link("r_follows", "USER", "1"); link("r_follows", "ROUTINE", "N", True)
    link("r_based", "SKIN_ANALYSIS", "1"); link("r_based", "ROUTINE", "N")
    link("r_answers", "SKIN_ANALYSIS", "M"); link("r_answers", "QUESTION", "N")
    link("r_assesses", "SKIN_ANALYSIS", "M"); link("r_assesses", "FACE_ZONE", "N")
    link("r_predicts", "SKIN_ANALYSIS", "M", True); link("r_predicts", "SKIN_CONCERN", "N")
    link("r_depicts", "SKIN_ANALYSIS", "1", True); link("r_depicts", "ANALYSIS_PHOTO", "N", True)
    link("r_consists", "ROUTINE", "1", True); link("r_consists", "ROUTINE_STEP", "N", True)
    link("r_uses", "ROUTINE_STEP", "N"); link("r_uses", "PRODUCT", "1")
    link("r_contains", "PRODUCT", "M", True); link("r_contains", "INGREDIENT", "N")
    link("r_records", "DAILY_LOG", "M"); link("r_records", "PRODUCT", "N")
    link("r_documents", "DAILY_LOG", "1"); link("r_documents", "PROGRESS_PHOTO", "1", True)

    # --- EER: disjoint, total specialization of PHOTO -----------------------------------------------
    p.vertex("spec", "d", f"ellipse;whiteSpace=wrap;html=1;aspect=fixed;{C_SPEC}{FONT}fontSize=18;fontStyle=1;",
             2350, 2370, 50, 50)
    p.edge("PHOTO", "spec", "shape=link;endArrow=none;html=1;rounded=0;strokeColor=#b85450;width=4;")
    sub = "endArrow=none;html=1;rounded=0;strokeColor=#b85450;fontSize=26;fontColor=#b85450;"
    p.edge("spec", "ANALYSIS_PHOTO", sub, "⊂", -0.2, 0)
    p.edge("spec", "PROGRESS_PHOTO", sub, "⊃", -0.2, 0)
    p.vertex("spec_note", "<i>Specialization of PHOTO<br>disjoint (d), total (double line)</i>",
             f"text;html=1;align=left;{FONT}fontSize=12;fontColor=#b85450;", 2560, 2330, 260, 44)

    # --- attributes ---------------------------------------------------------------------------------
    attr("USER", "user_id", -100, -230, "key")
    attr("USER", "email", 60, -260)
    attr("USER", "password_hash", 240, -220)
    fn = attr("USER", "full_name", 380, -120)
    attr(fn, "first_name", 120, -90)
    attr(fn, "last_name", 200, 0)
    dob = attr("USER", "date_of_birth", -230, -140)
    attr(dob, "age_range", -130, -90, "derived")
    attr("USER", "language", 500, 80)
    attr("USER", "created_at", 300, 80)
    sp = attr("USER", "skin_profile", 0, 150)
    attr(sp, "skin_type", -150, 80)
    attr(sp, "main_concern", -20, 125)
    attr(sp, "climate", 140, 150)

    attr("CONSENT", "consent_id", -150, -110, "key")
    attr("CONSENT", "consent_type", 40, -130)
    attr("CONSENT", "policy_version", 230, -95)
    attr("CONSENT", "granted_at", -200, 90)
    attr("CONSENT", "withdrawn_at", 20, 110)

    attr("REFRESH_TOKEN", "token_id", -230, -60, "key")
    attr("REFRESH_TOKEN", "token_hash", -260, 10)
    attr("REFRESH_TOKEN", "family_id", -230, 75)
    attr("REFRESH_TOKEN", "expires_at", 200, -75)
    attr("REFRESH_TOKEN", "revoked", 230, 75)

    attr("REMINDER", "reminder_id", -170, 100, "key")
    attr("REMINDER", "period", 30, 120)
    attr("REMINDER", "time_of_day", 230, 95)
    attr("REMINDER", "enabled", -230, 25)

    attr("SKIN_ANALYSIS", "analysis_id", -110, -140, "key")
    attr("SKIN_ANALYSIS", "created_at", 330, -60)
    attr("SKIN_ANALYSIS", "is_uncertain", 300, -140)
    attr("SKIN_ANALYSIS", "overall_confidence", 330, 90)
    attr("SKIN_ANALYSIS", "model_version", 190, 170)

    attr("QUESTION", "question_id", -110, -100, "key")
    attr("QUESTION", "field_key", 110, -100)
    attr("QUESTION", "text", -130, 100)
    attr("QUESTION", "answer_type", 40, 120)
    attr("QUESTION", "options", 210, 80, "multi")
    attr("r_answers", "answer_value", -60, -120)
    attr("r_answers", "is_missing", 140, -110)

    attr("FACE_ZONE", "zone_code", -60, -110, "key")
    attr("FACE_ZONE", "zone_name", 0, 110)
    attr("r_assesses", "finding", 40, -105)
    attr("r_assesses", "severity", -170, -90)

    attr("SKIN_CONCERN", "concern_code", -200, -100, "key")
    attr("SKIN_CONCERN", "name", -230, 50)
    attr("SKIN_CONCERN", "description", 0, 110)
    attr("r_predicts", "probability", -200, -40)
    attr("r_predicts", "rank", -150, 75)

    attr("PHOTO", "photo_id", -250, -90, "key")
    attr("PHOTO", "object_key", -20, -110)
    attr("PHOTO", "content_type", 220, -95)
    attr("PHOTO", "captured_at", -270, 30)
    attr("ANALYSIS_PHOTO", "shot_type", -190, 90)
    attr("ANALYSIS_PHOTO", "heatmap_key", 20, 110)
    attr("PROGRESS_PHOTO", "caption", 200, 80)

    attr("ROUTINE", "routine_id", -150, -110, "key")
    attr("ROUTINE", "period", 210, -110)
    attr("ROUTINE", "complexity_level", 260, -30)
    attr("ROUTINE", "created_at", -230, 100)
    attr("ROUTINE", "total_duration", 230, 70, "derived")

    attr("ROUTINE_STEP", "step_no", -240, -60, "partial")
    attr("ROUTINE_STEP", "category", -250, 50)
    attr("ROUTINE_STEP", "instruction", -100, 120)
    attr("ROUTINE_STEP", "duration_sec", 120, 120)

    attr("PRODUCT", "product_id", 270, -40, "key")
    attr("PRODUCT", "barcode", 270, 40)
    attr("PRODUCT", "name", 230, 110)
    attr("PRODUCT", "brand", 90, 145)
    attr("PRODUCT", "source", -60, 150)
    attr("PRODUCT", "category", -210, 115)
    attr("PRODUCT", "size", 250, -110)
    attr("PRODUCT", "safety_score", -230, 50, "derived")
    attr("r_records", "period", 140, -90)
    attr("r_records", "used_at", 190, 10)

    attr("INGREDIENT", "ingredient_id", -170, -110, "key")
    attr("INGREDIENT", "inci_name", 40, -130)
    attr("INGREDIENT", "plain_meaning", 260, -90)
    attr("INGREDIENT", "score", -230, 90)
    attr("INGREDIENT", "functions", -40, 120, "multi")
    attr("INGREDIENT", "flags", 150, 110, "multi")
    attr("r_contains", "position", 170, 40)

    attr("DAILY_LOG", "log_id", -200, -100, "key")
    attr("DAILY_LOG", "log_date", 10, -120)
    attr("DAILY_LOG", "notes", 220, -90)

    # --- legend ------------------------------------------------------------------------------------
    lx, ly = 150, 2140
    p.vertex("legend_box", "", "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#999999;arcSize=4;",
             lx + 230, ly + 250, 640, 560)
    p.vertex("legend_t", "<b>Legend</b>", f"text;html=1;align=left;{FONT}fontSize=16;", lx + 10, ly + 0, 160, 30)
    items = [
        ("ent", "ENTITY", f"rounded=0;whiteSpace=wrap;html=1;{C_ENT}{FONT}fontStyle=1;", 130, 40, "Strong entity"),
        ("went", "WEAK", f"shape=ext;double=1;margin=4;whiteSpace=wrap;html=1;{C_ENT}{FONT}fontStyle=1;", 130, 40,
         "Weak entity"),
        ("rel", "REL", f"shape=rhombus;perimeter=rhombusPerimeter;whiteSpace=wrap;html=1;{C_REL}{FONT}fontStyle=1;",
         120, 56, "Relationship"),
        ("irel", "ID_REL", f"shape=rhombus;perimeter=rhombusPerimeter;double=1;whiteSpace=wrap;html=1;{C_REL}{FONT}"
         "fontStyle=1;", 120, 56, "Identifying relationship"),
        ("key", "<u>key</u>", f"ellipse;whiteSpace=wrap;html=1;{C_ATT}{FONT}", 120, 36, "Key attribute"),
        ("pkey", '<span style="border-bottom:1.5px dashed #000">partial key</span>',
         f"ellipse;whiteSpace=wrap;html=1;{C_ATT}{FONT}", 120, 36, "Partial key of a weak entity"),
        ("mv", "multivalued", f"ellipse;shape=doubleEllipse;margin=3;whiteSpace=wrap;html=1;{C_ATT}{FONT}", 120, 36,
         "Multivalued attribute"),
        ("dv", "derived", f"ellipse;whiteSpace=wrap;html=1;dashed=1;dashPattern=6 4;{C_ATT}{FONT}", 120, 36,
         "Derived attribute (computed, not stored)"),
    ]
    for i, (k, v, st, w, h, desc) in enumerate(items):
        col, row = i % 2, i // 2
        cx, cy = lx + 80 + col * 320, ly + 70 + row * 95
        p.vertex(f"lg_{k}", v, st, cx, cy, w, h)
        p.vertex(f"lg_{k}_d", desc, f"text;html=1;align=left;whiteSpace=wrap;{FONT}fontSize=12;", cx + 150, cy, 160, 44)
    p.vertex("lg_comp", "Composite attribute: an attribute with its own sub-attributes (full_name, skin_profile).<br>"
             "Double line: total participation (every instance takes part).<br>"
             "Circle <b>d</b>: disjoint specialization; the subset sign (⊂ or ⊃) on each line opens toward the superclass.",
             f"text;html=1;align=left;whiteSpace=wrap;{FONT}fontSize=12;", lx + 240, ly + 455, 600, 80)
    return p


# ------------------------------------------------------------------------------------------------
# Page 2: relational schema mapped from the EER model
# ------------------------------------------------------------------------------------------------
# Each column: (key marker, name, type). Key markers: PK, FK, PK,FK, UQ or "".
TABLES = {
    "USER": [("PK", "user_id", "UUID"), ("UQ", "email", "VARCHAR(254)"), ("", "password_hash", "VARCHAR(255)"),
             ("", "first_name", "VARCHAR(80)"), ("", "last_name", "VARCHAR(80)"), ("", "date_of_birth", "DATE"),
             ("", "skin_type", "VARCHAR(20)"), ("", "main_concern", "VARCHAR(40)"), ("", "climate", "VARCHAR(30)"),
             ("", "language", "CHAR(2)"), ("", "created_at", "TIMESTAMP")],
    "CONSENT": [("PK", "consent_id", "UUID"), ("FK", "user_id", "UUID"), ("", "consent_type", "VARCHAR(40)"),
                ("", "policy_version", "VARCHAR(20)"), ("", "granted_at", "TIMESTAMP"),
                ("", "withdrawn_at", "TIMESTAMP NULL")],
    "REFRESH_TOKEN": [("PK", "token_id", "UUID"), ("FK", "user_id", "UUID"), ("UQ", "token_hash", "CHAR(64)"),
                      ("", "family_id", "UUID"), ("", "expires_at", "TIMESTAMP"), ("", "revoked", "BOOLEAN")],
    "REMINDER": [("PK", "reminder_id", "UUID"), ("FK", "user_id", "UUID"), ("", "period", "AM | PM"),
                 ("", "time_of_day", "TIME"), ("", "enabled", "BOOLEAN")],
    "SKIN_ANALYSIS": [("PK", "analysis_id", "UUID"), ("FK", "user_id", "UUID"), ("", "created_at", "TIMESTAMP"),
                      ("", "model_version", "VARCHAR(40)"), ("", "overall_confidence", "DECIMAL(4,3)"),
                      ("", "is_uncertain", "BOOLEAN")],
    "QUESTION": [("PK", "question_id", "SMALLINT"), ("UQ", "field_key", "VARCHAR(40)"), ("", "text", "VARCHAR(255)"),
                 ("", "answer_type", "VARCHAR(20)")],
    "QUESTION_OPTION": [("PK,FK", "question_id", "SMALLINT"), ("PK", "option_value", "VARCHAR(60)")],
    "ANSWER": [("PK,FK", "analysis_id", "UUID"), ("PK,FK", "question_id", "SMALLINT"),
               ("", "answer_value", "VARCHAR(255) NULL"), ("", "is_missing", "BOOLEAN")],
    "FACE_ZONE": [("PK", "zone_code", "VARCHAR(20)"), ("", "zone_name", "VARCHAR(40)")],
    "ZONE_ASSESSMENT": [("PK,FK", "analysis_id", "UUID"), ("PK,FK", "zone_code", "VARCHAR(20)"),
                        ("", "finding", "VARCHAR(80)"), ("", "severity", "VARCHAR(20)")],
    "SKIN_CONCERN": [("PK", "concern_code", "VARCHAR(30)"), ("", "name", "VARCHAR(60)"),
                     ("", "description", "TEXT")],
    "PREDICTION": [("PK,FK", "analysis_id", "UUID"), ("PK,FK", "concern_code", "VARCHAR(30)"),
                   ("", "probability", "DECIMAL(4,3)"), ("", "rank", "SMALLINT")],
    "PHOTO": [("PK", "photo_id", "UUID"), ("UQ", "object_key", "VARCHAR(255)"), ("", "content_type", "VARCHAR(40)"),
              ("", "captured_at", "TIMESTAMP"), ("", "photo_kind", "ANALYSIS | PROGRESS")],
    "ANALYSIS_PHOTO": [("PK,FK", "photo_id", "UUID"), ("FK", "analysis_id", "UUID"), ("", "shot_type", "VARCHAR(20)"),
                       ("", "heatmap_key", "VARCHAR(255) NULL")],
    "PROGRESS_PHOTO": [("PK,FK", "photo_id", "UUID"), ("FK,UQ", "log_id", "UUID"), ("", "caption", "VARCHAR(140)")],
    "DAILY_LOG": [("PK", "log_id", "UUID"), ("FK", "user_id", "UUID"), ("", "log_date", "DATE"),
                  ("", "notes", "TEXT NULL"), ("UQ", "(user_id, log_date)", "")],
    "PRODUCT_USE": [("PK,FK", "log_id", "UUID"), ("PK,FK", "product_id", "UUID"), ("PK", "period", "AM | PM"),
                    ("", "used_at", "TIMESTAMP")],
    "ROUTINE": [("PK", "routine_id", "UUID"), ("FK", "user_id", "UUID"), ("FK", "analysis_id", "UUID NULL"),
                ("", "period", "AM | PM"), ("", "complexity_level", "VARCHAR(12)"), ("", "created_at", "TIMESTAMP")],
    "ROUTINE_STEP": [("PK,FK", "routine_id", "UUID"), ("PK", "step_no", "SMALLINT"),
                     ("FK", "product_id", "UUID NULL"), ("", "category", "VARCHAR(30)"),
                     ("", "instruction", "VARCHAR(255)"), ("", "duration_sec", "SMALLINT")],
    "PRODUCT": [("PK", "product_id", "UUID"), ("UQ", "barcode", "VARCHAR(14) NULL"), ("", "name", "VARCHAR(160)"),
                ("", "brand", "VARCHAR(80)"), ("", "category", "VARCHAR(40)"), ("", "size", "VARCHAR(20)"),
                ("", "source", "VARCHAR(40)")],
    "PRODUCT_INGREDIENT": [("PK,FK", "product_id", "UUID"), ("PK,FK", "ingredient_id", "UUID"),
                           ("", "position", "SMALLINT")],
    "INGREDIENT": [("PK", "ingredient_id", "UUID"), ("UQ", "inci_name", "VARCHAR(160)"),
                   ("", "plain_meaning", "VARCHAR(255)"), ("", "score", "SMALLINT")],
    "INGREDIENT_FUNCTION": [("PK,FK", "ingredient_id", "UUID"), ("PK", "function", "VARCHAR(30)")],
    "INGREDIENT_FLAG": [("PK,FK", "ingredient_id", "UUID"), ("PK", "flag", "VARCHAR(30)")],
}

# top-left corner of each table
COL = [40, 420, 800, 1180, 1560, 1940, 2320, 2700]
TABLE_POS = {
    "QUESTION_OPTION": (COL[0], 680), "QUESTION": (COL[1], 680), "FACE_ZONE": (COL[1], 900),
    "CONSENT": (COL[2], 140), "REFRESH_TOKEN": (COL[2], 310), "REMINDER": (COL[2], 480),
    "ANSWER": (COL[2], 680), "ZONE_ASSESSMENT": (COL[2], 900),
    "USER": (COL[3], 140), "SKIN_ANALYSIS": (COL[3], 440), "PREDICTION": (COL[3], 680), "SKIN_CONCERN": (COL[3], 880),
    "DAILY_LOG": (COL[4], 140), "PROGRESS_PHOTO": (COL[4], 330), "ANALYSIS_PHOTO": (COL[4], 500),
    "ROUTINE": (COL[4], 760),
    "PRODUCT_USE": (COL[5], 140), "PHOTO": (COL[5], 400), "ROUTINE_STEP": (COL[5], 760),
    "PRODUCT": (COL[6], 140), "INGREDIENT_FLAG": (COL[6], 560),
    "PRODUCT_INGREDIENT": (COL[7], 140), "INGREDIENT": (COL[7], 330), "INGREDIENT_FUNCTION": (COL[7], 560),
}

# (child, parent, child-side end, parent-side end): crow's-foot markers
FKS = [
    ("CONSENT", "USER", "ERmany", "ERmandOne"), ("REFRESH_TOKEN", "USER", "ERmany", "ERmandOne"),
    ("REMINDER", "USER", "ERmany", "ERmandOne"), ("SKIN_ANALYSIS", "USER", "ERmany", "ERmandOne", "v"),
    ("DAILY_LOG", "USER", "ERmany", "ERmandOne"), ("ROUTINE", "USER", "ERmany", "ERmandOne"),
    ("QUESTION_OPTION", "QUESTION", "ERoneToMany", "ERmandOne"), ("ANSWER", "QUESTION", "ERmany", "ERmandOne"),
    ("ANSWER", "SKIN_ANALYSIS", "ERmany", "ERmandOne"),
    ("ZONE_ASSESSMENT", "FACE_ZONE", "ERmany", "ERmandOne"),
    ("ZONE_ASSESSMENT", "SKIN_ANALYSIS", "ERmany", "ERmandOne"),
    ("PREDICTION", "SKIN_ANALYSIS", "ERoneToMany", "ERmandOne", "v"),
    ("PREDICTION", "SKIN_CONCERN", "ERmany", "ERmandOne", "vu"),
    ("ANALYSIS_PHOTO", "SKIN_ANALYSIS", "ERoneToMany", "ERmandOne"),
    ("ANALYSIS_PHOTO", "PHOTO", "ERzeroToOne", "ERmandOne"),
    ("PROGRESS_PHOTO", "PHOTO", "ERzeroToOne", "ERmandOne"),
    ("PROGRESS_PHOTO", "DAILY_LOG", "ERzeroToOne", "ERmandOne", "v"),
    ("PRODUCT_USE", "DAILY_LOG", "ERmany", "ERmandOne"), ("PRODUCT_USE", "PRODUCT", "ERmany", "ERmandOne"),
    ("ROUTINE", "SKIN_ANALYSIS", "ERmany", "ERzeroToOne"), ("ROUTINE_STEP", "ROUTINE", "ERoneToMany", "ERmandOne"),
    ("ROUTINE_STEP", "PRODUCT", "ERmany", "ERzeroToOne"),
    ("PRODUCT_INGREDIENT", "PRODUCT", "ERoneToMany", "ERmandOne"),
    ("PRODUCT_INGREDIENT", "INGREDIENT", "ERmany", "ERmandOne", "vu"),
    ("INGREDIENT_FUNCTION", "INGREDIENT", "ERmany", "ERmandOne", "v"),
    ("INGREDIENT_FLAG", "INGREDIENT", "ERmany", "ERmandOne"),
]

TW, ROW_H, HEAD_H = 340, 17, 30


def table_label(name, cols):
    rows = "".join(
        f'<tr><td style="width:46px;padding:1px 5px;font-weight:bold;color:#6c8ebf">{k}</td>'
        f'<td style="padding:1px 4px">{"<u>" + c + "</u>" if "PK" in k else c}</td>'
        f'<td style="padding:1px 5px;color:#777777;text-align:right">{t}</td></tr>' for k, c, t in cols)
    return (f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
            f'<tr><td colspan="3" style="background:#dae8fc;font-weight:bold;text-align:center;font-size:13px;'
            f'padding:6px;border-bottom:1px solid #6c8ebf">{name}</td></tr>{rows}</table>')


def relational_page() -> Page:
    p = Page("Relational schema", "rel")
    p.vertex("rtitle", "<b>Relational schema mapped from the EER model</b><br><font style='font-size:13px'>PK primary "
             "key (underlined), FK foreign key, UQ unique. Crow's-foot ends: bar = exactly one, circle = optional, "
             "fork = many.</font>", f"text;html=1;align=left;verticalAlign=middle;{FONT}fontSize=22;",
             780, 60, 1400, 70)
    st = ("verticalAlign=top;align=left;overflow=fill;html=1;whiteSpace=wrap;rounded=0;fillColor=#ffffff;"
          "strokeColor=#6c8ebf;spacing=0;")
    for name, cols in TABLES.items():
        x, y = TABLE_POS[name]
        h = HEAD_H + ROW_H * len(cols) + 8
        p.vertex(f"t_{name}", table_label(name, cols), st, x + TW / 2, y + h / 2, TW, h)
    for child, parent, cend, pend, *vert in FKS:
        route = "edgeStyle=entityRelationEdgeStyle;"
        if vert == ["v"]:  # child table below its parent: connect top edge to bottom edge
            route = "edgeStyle=orthogonalEdgeStyle;exitX=0.5;exitY=0;entryX=0.5;entryY=1;"
        elif vert == ["vu"]:  # child table above its parent
            route = "edgeStyle=orthogonalEdgeStyle;exitX=0.5;exitY=1;entryX=0.5;entryY=0;"
        style = (f"{route}html=1;rounded=0;strokeColor=#555555;startArrow={cend};"
                 f"endArrow={pend};startFill=0;endFill=0;startSize=12;endSize=12;")
        p.edge(f"t_{child}", f"t_{parent}", style)
    p.vertex("rnote", "<b>Mapping rules applied</b><br>"
             "1. Each strong entity becomes a table; its key becomes the primary key.<br>"
             "2. Composite attributes (full_name, skin_profile) are flattened into simple columns.<br>"
             "3. Derived attributes (age_range, total_duration, safety_score) are computed, not stored.<br>"
             "4. 1:N relationships: foreign key on the N side (e.g. SKIN_ANALYSIS.user_id).<br>"
             "5. M:N relationships become junction tables that carry the relationship attributes "
             "(ANSWER, ZONE_ASSESSMENT, PREDICTION, PRODUCT_USE, PRODUCT_INGREDIENT).<br>"
             "6. Multivalued attributes become their own tables (QUESTION_OPTION, INGREDIENT_FUNCTION, "
             "INGREDIENT_FLAG).<br>"
             "7. Weak entity ROUTINE_STEP: primary key = owner key routine_id + partial key step_no.<br>"
             "8. Specialization of PHOTO (disjoint, total): one table per class; each subclass reuses the "
             "superclass key (photo_id is both PK and FK) and photo_kind records the subclass.<br>"
             "9. 1:1 DOCUMENTS: unique foreign key PROGRESS_PHOTO.log_id.",
             f"text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;{FONT}fontSize=12;"
             "fillColor=#f5f5f5;strokeColor=#999999;spacing=10;", 2340, 1060, 1000, 190)
    return p


def main():
    pages = [eer_page(), relational_page()]
    xml = '<mxfile host="Electron" type="device">' + "".join(pg.xml() for pg in pages) + "</mxfile>"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(xml, encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
