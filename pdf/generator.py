"""
PDF generator for the OneKlinik Weekly Ops Report.
Call generate_weekly_report(data, output_path) to produce a PDF.

data schema:
{
  "week_label": str,      e.g. "Week 7  –  5–9 May 2026"
  "gen_date":   str,      e.g. "Monday, 12 May 2026"
  "departments": {
      "marketing": { "highlights": [(label, text), ...], "issues": [...], "actions": [(item, owner, due), ...], "dar": [...] },
      "finance":   { ... },
      "ga":        { ... },
      "am":        { ... },
      "hr":        { ... },
      "bd":        { ..., "pipeline": [(company, stage, owner, notes), ...] },
  },
  "projects": {
      "homecare":   [ {name, class, status, branches, tnc, todo_done, todo_pending, bottleneck, support}, ... ],
      "oneklinik":  [ ... ],
  },
  "logo_path": str   (optional, defaults to static/logo_transparent.png next to this file)
}
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Flowable
from reportlab.platypus import Image as RLImage

# ── Colours ──────────────────────────────────────────────────────────────────
BLUE      = colors.HexColor('#34b6f8')
CHARCOAL  = colors.HexColor('#545454')
LIGHT_BG  = colors.HexColor('#F7FAFE')
DIVIDER   = colors.HexColor('#E2EEF9')
WHITE     = colors.white
LIGHT_GREY= colors.HexColor('#9AA5B4')
GREEN     = colors.HexColor('#27AE60')
YELLOW    = colors.HexColor('#F2994A')
RED       = colors.HexColor('#EB5757')
BLUE_SOFT = colors.HexColor('#2F80ED')
RED_DARK  = colors.HexColor('#C0392B')
RED_BG    = colors.HexColor('#FFF0F0')

W, H = A4
ML, MR = 22*mm, 22*mm
MT, MB = 20*mm, 18*mm
CW = W - ML - MR

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGO = os.path.join(_HERE, '..', 'static', 'logo_transparent.png')


def _ps(name, **kw):
    d = dict(fontName='Helvetica', fontSize=11, textColor=CHARCOAL, leading=16)
    d.update(kw)
    return ParagraphStyle(name, **d)


ST = {
    'cover_title': _ps('ct', fontName='Helvetica-Bold', fontSize=30, leading=36, alignment=TA_CENTER),
    'cover_sub':   _ps('cs', fontSize=11, textColor=LIGHT_GREY, leading=16, alignment=TA_CENTER),
    'toc_h':       _ps('th', fontName='Helvetica-Bold', fontSize=12, leading=16, spaceAfter=10),
    'sub':         _ps('sub', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=10, spaceAfter=4),
    'body':        _ps('body', fontSize=11, leading=16, spaceAfter=2),
    'bold':        _ps('bold', fontName='Helvetica-Bold', fontSize=11, leading=16, spaceAfter=2),
    'bullet':      _ps('bul', fontSize=11, leading=16, leftIndent=14, spaceAfter=2),
    'issue':       _ps('iss', fontSize=11, textColor=YELLOW, leading=16, leftIndent=4, spaceAfter=3),
    'proj_name':   _ps('pn', fontName='Helvetica-Bold', fontSize=11, leading=14),
    'proj_cls':    _ps('pc', fontSize=9, textColor=BLUE, leading=12),
    'proj_br':     _ps('pb', fontSize=9.5, textColor=CHARCOAL, leading=12, leftIndent=8, spaceBefore=2),
    'section_lbl': _ps('sl', fontName='Helvetica-Bold', fontSize=9, textColor=BLUE, leading=11, spaceBefore=4, spaceAfter=2),
    'tnc_body':    _ps('tb', fontSize=10, leading=15, leftIndent=14, spaceAfter=2),
}


# ── Flowables ────────────────────────────────────────────────────────────────
class Anchor(Flowable):
    def __init__(self, name):
        super().__init__(); self.name = name; self.width = 0; self.height = 0

    def draw(self):
        self.canv.bookmarkPage(self.name, fit='XYZ', left=0, top=H, zoom=0)


class TOCRow(Flowable):
    def __init__(self, num, name, dest, width):
        super().__init__()
        self.num = num; self.name = name; self.dest = dest
        self.width = width; self.height = 26

    def draw(self):
        c = self.canv
        c.setFont('Helvetica-Bold', 11); c.setFillColor(BLUE); c.drawString(0, 7, self.num)
        c.setFont('Helvetica', 11); c.setFillColor(BLUE); c.drawString(30, 7, self.name)
        c.setStrokeColor(DIVIDER); c.setLineWidth(0.3); c.line(0, 0, self.width, 0)
        c.linkRect('', self.dest, Rect=(0, 0, self.width, self.height), Border='[0 0 0]', relative=1)


class HomeButton(Flowable):
    BTN_W = 72; BTN_H = 15

    def __init__(self, content_width):
        super().__init__(); self.width = content_width; self.height = self.BTN_H + 4

    def draw(self):
        c = self.canv
        x = self.width - self.BTN_W; y = 2
        c.setFillColor(LIGHT_BG); c.roundRect(x, y, self.BTN_W, self.BTN_H, 3, fill=1, stroke=0)
        c.setStrokeColor(DIVIDER); c.setLineWidth(0.5)
        c.roundRect(x, y, self.BTN_W, self.BTN_H, 3, fill=0, stroke=1)
        c.setFont('Helvetica', 7.5); c.setFillColor(CHARCOAL)
        c.drawCentredString(x + self.BTN_W / 2, y + 4, '⌂  Back to Cover')
        c.linkRect('', 'cover_page', Rect=(x, y, x + self.BTN_W, y + self.BTN_H), Border='[0 0 0]', relative=1)


class DARBox(Flowable):
    LINE_H = 15

    def __init__(self, items, width):
        super().__init__(); self.items = items; self.width = width
        self.height = 30 + len(items) * self.LINE_H + 4

    def draw(self):
        c = self.canv
        c.setFillColor(RED_BG); c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        c.setFillColor(RED); c.roundRect(0, 0, 4, self.height, 3, fill=1, stroke=0)
        c.rect(2, 0, 2, self.height, fill=1, stroke=0)
        c.setFillColor(RED_DARK); c.setFont('Helvetica-Bold', 9)
        c.drawString(14, self.height - 14, '⚠  Director\'s Action Required')
        c.setFont('Helvetica', 8.5); y = self.height - 28
        for item in self.items:
            c.setFillColor(RED_DARK); c.drawString(14, y, f'•  {item}'); y -= self.LINE_H


class DeptHeader(Flowable):
    def __init__(self, name, week, width):
        super().__init__(); self.name = name; self.week = week
        self.width = width; self.height = 40

    def draw(self):
        c = self.canv
        c.setFillColor(LIGHT_BG); c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        c.setFillColor(BLUE); c.roundRect(0, 0, 5, self.height, 3, fill=1, stroke=0)
        c.rect(3, 0, 2, self.height, fill=1, stroke=0)
        c.setFont('Helvetica-Bold', 14); c.setFillColor(CHARCOAL)
        c.drawString(16, 13, self.name)
        c.setFont('Helvetica', 9); c.setFillColor(LIGHT_GREY)
        c.drawRightString(self.width - 8, 15, self.week)


class SubHeader(Flowable):
    def __init__(self, name, width):
        super().__init__(); self.name = name; self.width = width; self.height = 28

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor('#EEF7FE'))
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        c.setFillColor(BLUE); c.roundRect(0, 0, 3, self.height, 2, fill=1, stroke=0)
        c.rect(2, 0, 1, self.height, fill=1, stroke=0)
        c.setFont('Helvetica-Bold', 11); c.setFillColor(CHARCOAL)
        c.drawString(12, 9, self.name)


class ThinLine(Flowable):
    def __init__(self, width, color=DIVIDER, thickness=0.5):
        super().__init__(); self.width = width; self.color = color
        self.thickness = thickness; self.height = 5

    def draw(self):
        c = self.canv; c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness); c.line(0, 2, self.width, 2)


# ── Page callbacks ────────────────────────────────────────────────────────────
def _cover_bg(canvas, doc):
    canvas.saveState()
    canvas.bookmarkPage('cover_page', fit='XYZ', left=0, top=H, zoom=0)
    canvas.setFillColor(BLUE); canvas.rect(0, H - 6, W, 6, fill=1, stroke=0)
    canvas.setFillColor(CHARCOAL); canvas.rect(0, 0, W, 4, fill=1, stroke=0)
    canvas.restoreState()


def _inner_page(logo_path):
    def callback(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(DIVIDER); canvas.setLineWidth(0.5)
        canvas.line(ML, H - MT + 6, W - MR, H - MT + 6)
        if os.path.exists(logo_path):
            canvas.drawImage(logo_path, W - MR - 55, H - MT + 7,
                             width=55, height=16, preserveAspectRatio=True, mask='auto')
        canvas.setStrokeColor(DIVIDER); canvas.line(ML, MB - 2, W - MR, MB - 2)
        canvas.setFont('Helvetica', 8); canvas.setFillColor(LIGHT_GREY)
        canvas.drawCentredString(W/2, MB - 13, 'OneKlinik — Weekly Ops Report  |  Confidential')
        canvas.drawRightString(W - MR, MB - 13, f'Page {doc.page}')
        canvas.restoreState()
    return callback


# ── Helpers ───────────────────────────────────────────────────────────────────
def _action_table(actions):
    col_w = [CW*0.50, CW*0.25, CW*0.25]
    hs = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=10, textColor=CHARCOAL, leading=14)
    cs = ParagraphStyle('td', fontName='Helvetica', fontSize=10, textColor=CHARCOAL, leading=14)
    rows = [[Paragraph('Item', hs), Paragraph('Owner', hs), Paragraph('Due', hs)]]
    for item, owner, due in actions:
        rows.append([Paragraph(str(item), cs), Paragraph(str(owner), cs), Paragraph(str(due), cs)])
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  LIGHT_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, colors.HexColor('#F5FBFF')]),
        ('GRID',          (0,0), (-1,-1),  0.3, DIVIDER),
        ('TOPPADDING',    (0,0), (-1,-1),  5),
        ('BOTTOMPADDING', (0,0), (-1,-1),  5),
        ('LEFTPADDING',   (0,0), (-1,-1),  8),
        ('RIGHTPADDING',  (0,0), (-1,-1),  8),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))
    return t


def _section_block(story, highlights, issues=None, actions=None, dar=None):
    story.append(Paragraph('Key Updates', ST['sub']))
    story.append(ThinLine(CW))
    story.append(Spacer(1, 6))
    for label, text in highlights:
        story.append(Paragraph(str(label), ST['bold']))
        story.append(Paragraph(f'•  {text}', ST['bullet']))
        story.append(Spacer(1, 3))
    if issues:
        story.append(Spacer(1, 4))
        story.append(Paragraph('Issues & Risks', ST['sub']))
        story.append(ThinLine(CW))
        story.append(Spacer(1, 6))
        for iss in issues:
            story.append(Paragraph(f'⚠  {iss}', ST['issue']))
    if actions:
        story.append(Spacer(1, 4))
        story.append(Paragraph('Outstanding / Action Items', ST['sub']))
        story.append(ThinLine(CW))
        story.append(Spacer(1, 6))
        story.append(_action_table(actions))
    if dar:
        story.append(Spacer(1, 10))
        story.append(DARBox(dar, CW))


# ── Section builders ──────────────────────────────────────────────────────────
def _cover(story, week_label, gen_date, logo_path):
    story.append(Spacer(1, 55))
    if os.path.exists(logo_path):
        img = RLImage(logo_path, width=115, height=30)
        img.hAlign = 'CENTER'
        story.append(img)
    story.append(Spacer(1, 22))
    story.append(Paragraph('Weekly Ops Report', ST['cover_title']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(week_label, ST['cover_sub']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f'Generated {gen_date}', ST['cover_sub']))
    story.append(Spacer(1, 36))
    story.append(ThinLine(CW, DIVIDER, 1))
    story.append(Spacer(1, 28))
    story.append(Paragraph('Contents', ST['toc_h']))

    toc = [
        ('01', 's_mktg',    'Marketing'),
        ('02', 's_finance', 'Finance'),
        ('03', 's_ga',      'General Affair'),
        ('04', 's_am',      'Account Manager'),
        ('05', 's_hr',      'Human Resources (HR)'),
        ('06', 's_bd',      'Business Development'),
        ('07', 's_proj_hc', 'Project Progress — Marketing Homecare by OneKlinik'),
        ('08', 's_proj_ok', 'Project Progress — Marketing OneKlinik'),
    ]
    for num, dest, name in toc:
        story.append(TOCRow(num, name, dest, CW))
        story.append(Spacer(1, 2))
    story.append(PageBreak())


def _dept_page(story, dept_name, week, anchor_key, highlights, issues, actions, dar=None):
    story.append(Anchor(anchor_key))
    story.append(HomeButton(CW))
    story.append(Spacer(1, 4))
    story.append(DeptHeader(dept_name, week, CW))
    story.append(Spacer(1, 12))
    _section_block(story, highlights, issues, actions, dar)
    story.append(PageBreak())


def _bd_page(story, week, highlights, issues, actions, pipeline, dar=None):
    story.append(Anchor('s_bd'))
    story.append(HomeButton(CW))
    story.append(Spacer(1, 4))
    story.append(DeptHeader('Business Development', week, CW))
    story.append(Spacer(1, 12))
    _section_block(story, highlights, issues, actions, dar)
    story.append(Spacer(1, 12))
    story.append(Paragraph('Outreach Pipeline', ST['sub']))
    story.append(ThinLine(CW))
    story.append(Spacer(1, 8))

    status_colors = {
        'Prospect': LIGHT_GREY, 'Contacted': BLUE,
        'Meeting': colors.HexColor('#9B51E0'), 'Proposal': YELLOW,
        'Negotiation': YELLOW, 'Closed Won': GREEN, 'Closed Lost': RED,
    }
    col_w = [CW*0.30, CW*0.18, CW*0.18, CW*0.34]
    hs = ParagraphStyle('ph', fontName='Helvetica-Bold', fontSize=10, textColor=CHARCOAL, leading=14)
    cs = ParagraphStyle('pd', fontName='Helvetica', fontSize=10, textColor=CHARCOAL, leading=14)
    rows = [[Paragraph(h, hs) for h in ['Company', 'Stage', 'PIC', 'Notes']]]
    for row in pipeline:
        sc = status_colors.get(row[1], LIGHT_GREY)
        ss = ParagraphStyle('st', fontName='Helvetica-Bold', fontSize=9, textColor=sc, leading=13)
        rows.append([Paragraph(str(row[0]), cs), Paragraph(str(row[1]), ss),
                     Paragraph(str(row[2]), cs), Paragraph(str(row[3]), cs)])
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  LIGHT_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, colors.HexColor('#F5FBFF')]),
        ('GRID',          (0,0), (-1,-1),  0.3, DIVIDER),
        ('TOPPADDING',    (0,0), (-1,-1),  5),
        ('BOTTOMPADDING', (0,0), (-1,-1),  5),
        ('LEFTPADDING',   (0,0), (-1,-1),  8),
        ('RIGHTPADDING',  (0,0), (-1,-1),  8),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t)
    story.append(PageBreak())


def _project_page(story, sub_title, anchor_key, week, projects):
    story.append(Anchor(anchor_key))
    story.append(HomeButton(CW))
    story.append(Spacer(1, 4))
    story.append(DeptHeader('Project Progress', week, CW))
    story.append(Spacer(1, 6))
    story.append(SubHeader(sub_title, CW))
    story.append(Spacer(1, 12))

    status_colors = {
        'New Project Active': GREEN, 'New Project In Progress': YELLOW,
        'Done': BLUE_SOFT, 'Stuck': RED, 'On Hold': LIGHT_GREY,
        'Active': GREEN, 'On Progress': YELLOW,
    }

    for p in projects:
        sc = status_colors.get(p.get('status', ''), LIGHT_GREY)
        ss = ParagraphStyle('st', fontName='Helvetica-Bold', fontSize=9, textColor=sc, leading=12)
        hdr = Table([[Paragraph(p.get('name', ''), ST['proj_name']),
                      Paragraph(p.get('class', ''), ST['proj_cls']),
                      Paragraph(p.get('status', ''), ss)]],
                    colWidths=[CW*0.42, CW*0.28, CW*0.30])
        hdr.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), LIGHT_BG),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBELOW',     (0,0), (-1,0),  0.5, DIVIDER),
        ]))
        story.append(hdr)
        if p.get('branches'):
            story.append(Paragraph(f'<font color="#9AA5B4">Branches: </font>{p["branches"]}', ST['proj_br']))
        if p.get('tnc'):
            story.append(Spacer(1, 4))
            story.append(Paragraph('TnC Program', ST['section_lbl']))
            for line in p['tnc']:
                story.append(Paragraph(f'•  {line}', ST['tnc_body']))
        if p.get('todo_done') or p.get('todo_pending'):
            story.append(Spacer(1, 4))
            story.append(Paragraph('To-Do', ST['section_lbl']))
            for item in p.get('todo_done', []):
                story.append(Paragraph(
                    f'<font color="#27AE60">✓</font>  {item}',
                    ParagraphStyle('td2', fontName='Helvetica', fontSize=10,
                                   textColor=CHARCOAL, leading=15, leftIndent=14, spaceAfter=1)))
            for item in p.get('todo_pending', []):
                story.append(Paragraph(
                    f'<font color="#F2994A">○</font>  {item}',
                    ParagraphStyle('tp2', fontName='Helvetica', fontSize=10,
                                   textColor=CHARCOAL, leading=15, leftIndent=14, spaceAfter=1)))
        if p.get('bottleneck'):
            story.append(Spacer(1, 4))
            story.append(Paragraph('Bottleneck', ST['section_lbl']))
            story.append(Paragraph(f'⚠  {p["bottleneck"]}',
                ParagraphStyle('bn', fontName='Helvetica', fontSize=10,
                               textColor=YELLOW, leading=15, leftIndent=8, spaceAfter=2)))
        if p.get('support'):
            story.append(Paragraph('Support Needed', ST['section_lbl']))
            story.append(Paragraph(f'→  {p["support"]}',
                ParagraphStyle('sn', fontName='Helvetica', fontSize=10,
                               textColor=CHARCOAL, leading=15, leftIndent=8, spaceAfter=2)))
        story.append(Spacer(1, 10))
        story.append(ThinLine(CW, DIVIDER, 0.3))
        story.append(Spacer(1, 8))
    story.append(PageBreak())


# ── Public entry point ────────────────────────────────────────────────────────
def generate_weekly_report(data: dict, output_path: str) -> str:
    """
    Generate a PDF weekly ops report.

    :param data: dict matching the schema described at the top of this module.
    :param output_path: absolute path where the PDF should be written.
    :returns: output_path on success.
    """
    logo_path = data.get("logo_path") or os.path.normpath(DEFAULT_LOGO)
    week_label = data.get("week_label", "Weekly Ops Report")
    gen_date   = data.get("gen_date", "")
    depts      = data.get("departments", {})
    projects   = data.get("projects", {})

    def dept(key):
        d = depts.get(key, {})
        return (
            d.get("highlights", [("No data", "—")]),
            d.get("issues", []),
            d.get("actions", []),
            d.get("dar"),
        )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4, leftMargin=ML, rightMargin=MR,
        topMargin=MT + 14, bottomMargin=MB + 14,
        title='Ops Weekly Report', author='OneKlinik Ops',
    )
    story = []
    _cover(story, week_label, gen_date, logo_path)

    mktg_h, mktg_i, mktg_a, mktg_d = dept("marketing")
    _dept_page(story, 'Marketing', week_label, 's_mktg', mktg_h, mktg_i, mktg_a, mktg_d)

    fin_h, fin_i, fin_a, fin_d = dept("finance")
    _dept_page(story, 'Finance', week_label, 's_finance', fin_h, fin_i, fin_a, fin_d)

    ga_h, ga_i, ga_a, ga_d = dept("ga")
    _dept_page(story, 'General Affair', week_label, 's_ga', ga_h, ga_i, ga_a, ga_d)

    am_h, am_i, am_a, am_d = dept("am")
    _dept_page(story, 'Account Manager', week_label, 's_am', am_h, am_i, am_a, am_d)

    hr_h, hr_i, hr_a, hr_d = dept("hr")
    _dept_page(story, 'Human Resources (HR)', week_label, 's_hr', hr_h, hr_i, hr_a, hr_d)

    bd = depts.get("bd", {})
    _bd_page(story, week_label,
             bd.get("highlights", [("No data", "—")]),
             bd.get("issues", []),
             bd.get("actions", []),
             bd.get("pipeline", []),
             bd.get("dar"))

    hc_projects = projects.get("homecare", [])
    if hc_projects:
        _project_page(story, 'Marketing Homecare by OneKlinik', 's_proj_hc', week_label, hc_projects)

    ok_projects = projects.get("oneklinik", [])
    if ok_projects:
        _project_page(story, 'Marketing OneKlinik', 's_proj_ok', week_label, ok_projects)

    doc.build(story, onFirstPage=_cover_bg, onLaterPages=_inner_page(logo_path))
    return output_path
