"""BioTwin corporate advisory PDF, Times New Roman with accessible multicolour visuals.

On Windows, uses the installed Microsoft Times New Roman font from Windows/Fonts.
No fonts are packaged or distributed. On computers without Times New Roman,
uses metric-compatible Tinos when present; otherwise PDF built-in Times Roman.
All report values come directly from the evaluated API result and are not recomputed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from math import isfinite
from pathlib import Path
from xml.sax.saxutils import escape
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, HRFlowable, PageBreak, Paragraph, Image as RLImage,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

BLACK = colors.HexColor('#202A35')
WHITE = colors.white
PURPLE = colors.HexColor('#60336F')
DEEP_NAVY = colors.HexColor('#172B4B')
CYAN = colors.HexColor('#09A8CC')
BLUE = colors.HexColor('#1478B8')
GREEN = colors.HexColor('#1EAA75')
ORANGE = colors.HexColor('#E98B30')
MAGENTA = colors.HexColor('#B74287')
SLATE = colors.HexColor('#6A7181')
PALE = colors.HexColor('#F6F8FB')
PALE_PURPLE = colors.HexColor('#F7F2F8')
PALETTE = [BLUE, GREEN, CYAN, MAGENTA, ORANGE, PURPLE, colors.HexColor('#7086AC')]
SECTION_COLORS = [PURPLE, PURPLE, BLUE, CYAN, GREEN, ORANGE, MAGENTA, BLUE, PURPLE, GREEN]

PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 38 * mm


def _typeface():
    """Register Times New Roman from the operating system; do not ship any fonts."""
    windows_dir = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
    times_candidates = [
        (windows_dir/'times.ttf', windows_dir/'timesbd.ttf', windows_dir/'timesi.ttf'),
        (Path('/usr/share/fonts/truetype/msttcorefonts/times.ttf'),
         Path('/usr/share/fonts/truetype/msttcorefonts/timesbd.ttf'),
         Path('/usr/share/fonts/truetype/msttcorefonts/timesi.ttf')),
    ]
    tinos = Path('/usr/share/fonts/truetype/croscore')
    times_candidates.append((tinos/'Tinos-Regular.ttf',tinos/'Tinos-Bold.ttf',tinos/'Tinos-Italic.ttf'))
    for regular, bold, italic in times_candidates:
        if all(p.is_file() for p in (regular,bold,italic)):
            try:
                pdfmetrics.registerFont(TTFont('BTSerif', str(regular)))
                pdfmetrics.registerFont(TTFont('BTSerifBold', str(bold)))
                pdfmetrics.registerFont(TTFont('BTSerifItalic', str(italic)))
                pdfmetrics.registerFontFamily('BTSerif',normal='BTSerif',bold='BTSerifBold',italic='BTSerifItalic',boldItalic='BTSerifBold')
                return 'BTSerif','BTSerifBold','BTSerifItalic', ('Times New Roman' if regular.name.lower() == 'times.ttf' else 'Times-compatible serif fallback')
            except Exception:
                continue
    return 'Times-Roman','Times-Bold','Times-Italic','PDF Times-Roman fallback'

FONT, FONT_BOLD, FONT_ITALIC, FONT_SOURCE = _typeface()


def t(x):
    return escape(str(x) if x is not None else 'Not available')


def num(x, decimals=0):
    try:
        return f'{float(x):,.{decimals}f}' if x is not None and isfinite(float(x)) else 'n/a'
    except (TypeError, ValueError):
        return 'n/a'


def money(x, digits=1):
    if x is None:
        return 'n/a'
    try:
        y = float(x)
        if not isfinite(y):
            return 'n/a'
    except (ValueError, TypeError):
        return 'n/a'
    sign = '-' if y < 0 else ''
    y = abs(y)
    if y >= 1_000_000:
        return f'{sign}S${y/1_000_000:,.{digits}f}m'
    if y >= 10_000:
        return f'{sign}S${y/1000:,.0f}k'
    return f'{sign}S${y:,.0f}'


def pct(x):
    return num(None if x is None else 100 * x, 1) + '%'


STYLE = {
    'coverK': ParagraphStyle('coverK', fontName=FONT_BOLD, fontSize=10, leading=14,
                             textColor=PURPLE, spaceAfter=12),
    'coverT': ParagraphStyle('coverT', fontName=FONT_BOLD, fontSize=29, leading=34,
                             textColor=PURPLE, spaceAfter=17),
    'coverS': ParagraphStyle('coverS', fontName=FONT, fontSize=12, leading=18,
                             textColor=DEEP_NAVY, spaceAfter=10),
    'sectionK': ParagraphStyle('sectionK', fontName=FONT_BOLD, fontSize=9.5, leading=12,
                               textColor=BLUE, spaceBefore=3, spaceAfter=9),
    'h1': ParagraphStyle('h1', fontName=FONT_BOLD, fontSize=22, leading=27,
                         textColor=PURPLE, spaceAfter=14),
    'h2': ParagraphStyle('h2', fontName=FONT_BOLD, fontSize=12.5, leading=16,
                         textColor=PURPLE, spaceBefore=12, spaceAfter=8),
    'body': ParagraphStyle('body', fontName=FONT, fontSize=10, leading=14.5,
                           textColor=BLACK, spaceAfter=9),
    'muted': ParagraphStyle('muted', fontName=FONT_ITALIC, fontSize=8.8, leading=12,
                            textColor=SLATE, spaceAfter=7),
    'small': ParagraphStyle('small', fontName=FONT, fontSize=8.4, leading=11,
                            textColor=BLACK),
    'smallBold': ParagraphStyle('smallBold', fontName=FONT_BOLD, fontSize=8.4, leading=11,
                                textColor=PURPLE),
    'metricV': ParagraphStyle('metricV', fontName=FONT_BOLD, fontSize=16.5, leading=20,
                              textColor=PURPLE),
    'metricL': ParagraphStyle('metricL', fontName=FONT, fontSize=8, leading=10,
                              textColor=SLATE),
    'disclaimer': ParagraphStyle('disclaimer', fontName=FONT, fontSize=8.5, leading=12,
                                 textColor=SLATE),
}


def P(text, sty='body'):
    return Paragraph(str(text), STYLE[sty])


def line():
    return HRFlowable(width='100%', thickness=1.2, color=CYAN, spaceBefore=7, spaceAfter=11)


def heading(kicker, title):
    return [P(kicker.upper(), 'sectionK'), P(title, 'h1'), line()]


def metrics(items):
    """Editorial KPI strip: pale panels, coloured top rules and purple numerals."""
    cells = []
    for title, value in items:
        cells.append([P(t(title).upper(), 'metricL'), P(t(value), 'metricV')])
    n = len(cells)
    tab = Table([cells], colWidths=[CONTENT_W / n] * n, rowHeights=58)
    commands = [
        ('BACKGROUND', (0, 0), (-1, -1), PALE),
        ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#CFD7E0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]
    for i in range(n):
        commands += [('LINEABOVE', (i, 0), (i, 0), 2.5, PALETTE[i % len(PALETTE)])]
        if i:
            commands += [('LINEBEFORE', (i, 0), (i, 0), .45, colors.HexColor('#DADEE6'))]
    tab.setStyle(TableStyle(commands))
    return tab


def table(headers, rows, widths=None, *, small=False):
    def cell(v, bold=False):
        return P(t(v), 'smallBold' if bold else 'small')
    data = [[cell(v, True) for v in headers]] + [[cell(v) for v in row] for row in rows]
    tab = Table(data, colWidths=widths or [CONTENT_W / len(headers)] * len(headers), repeatRows=1, hAlign='LEFT')
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), PALE_PURPLE),
        ('LINEABOVE', (0, 0), (-1, 0), 1.1, PURPLE),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, CYAN),
        ('LINEBELOW', (0, 1), (-1, -1), .2, colors.HexColor('#C6CED8')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 7 if not small else 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7 if not small else 4),
    ]
    for ri in range(2, len(data), 2):
        style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#FAFBFD')))
    tab.setStyle(TableStyle(style))
    return tab


class Bars(Flowable):
    """Temasek-inspired multi-colour analytical bars; sign and exact values remain visible."""
    def __init__(self, items, width=CONTENT_W, height=172, color=BLACK):
        super().__init__()
        self.items = items
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        vals = [abs(float(v or 0)) for _, v in self.items]
        mx = max(vals + [1.0])
        n = max(len(self.items), 1)
        for i, (lbl, val) in enumerate(self.items):
            y = self.height - 20 - i * (self.height - 17) / n
            val = float(val or 0)
            c.setFillColor(BLACK)
            c.setFont(FONT, 8.2)
            c.drawString(0, y, str(lbl)[:39])
            x = 181
            w = self.width - x - 65
            bar_w = max(1.4, w * abs(val) / mx)
            c.setFillColor(colors.HexColor('#EDF1F5'))
            c.roundRect(x, y-1, w, 9, 2.5, fill=1, stroke=0)
            color = (colors.HexColor('#C64D63') if val < 0 else PALETTE[i % len(PALETTE)])
            c.setFillColor(color)
            c.roundRect(x, y-1, bar_w, 9, 2.5, fill=1, stroke=0)
            c.setFillColor(color if val < 0 else PURPLE)
            c.setFont(FONT_BOLD, 8.1)
            c.drawRightString(self.width, y, num(val))


class CashCurve(Flowable):
    def __init__(self, years, width=CONTENT_W, height=165):
        super().__init__()
        self.years = years
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        vals = [float(r.get('cumulative_sgd') or 0)/1e6 for r in self.years]
        if len(vals) < 2:
            return
        lo = min(vals + [0]); hi = max(vals + [0]); delta = max(hi-lo, 1)
        left = 48; right = self.width-18; bottom = 24; top = self.height-18
        yy = lambda v: bottom+(v-lo)/delta*(top-bottom)
        xx = lambda i: left+(right-left)*i/(len(vals)-1)
        for q in [0, .25, .5, .75, 1]:
            y = bottom+q*(top-bottom); v = lo+q*delta
            c.setStrokeColor(colors.HexColor('#D6DEE6'))
            c.setLineWidth(.4); c.line(left, y, right, y)
            c.setFont(FONT, 7.4); c.setFillColor(SLATE)
            c.drawRightString(left-6, y-2, f'{v:+.1f}m')
        if lo <= 0 <= hi:
            c.setStrokeColor(ORANGE); c.setLineWidth(.9); c.setDash(4,3)
            c.line(left, yy(0), right, yy(0)); c.setDash()
        path = c.beginPath()
        path.moveTo(xx(0),yy(vals[0]))
        for i in range(1,len(vals)):
            path.lineTo(xx(i), yy(vals[i]))
        # Translucent fill beneath the curve, then strong line and markers.
        area = c.beginPath()
        area.moveTo(xx(0), bottom)
        for i,v in enumerate(vals):
            area.lineTo(xx(i),yy(v))
        area.lineTo(xx(len(vals)-1),bottom); area.close()
        c.saveState()
        try:
            c.setFillAlpha(0.12)
        except AttributeError:
            pass
        c.setFillColor(CYAN); c.drawPath(area, fill=1, stroke=0)
        c.restoreState()
        c.setStrokeColor(BLUE); c.setLineWidth(2.1)
        c.drawPath(path, fill=0, stroke=1)
        for i, v in enumerate(vals):
            if i in (0, len(vals)-1) or i % max(1,len(vals)//5) == 0:
                c.setFillColor(PURPLE if v >= 0 else ORANGE)
                c.circle(xx(i), yy(v), 2.1, fill=1, stroke=0)
        c.setFillColor(SLATE); c.setFont(FONT,7.5)
        c.drawString(left,bottom-13,'Construction')
        c.drawRightString(right,bottom-13,f'Year {len(vals)-1}')
        c.setFillColor(PURPLE); c.setFont(FONT_BOLD,8)
        c.drawRightString(right, min(self.height-4,max(10,yy(vals[-1])+7)), f'{vals[-1]:+,.1f}m')


def frame(canvas, doc, cover=False, preview_mode=False):
    """Original BioTwin identity informed by the reference's editorial hierarchy."""
    canvas.saveState()
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if cover:
        # Abstract material cycles: vector geometry, not borrowed artwork.
        band_h = 70*mm
        canvas.setFillColor(DEEP_NAVY)
        canvas.rect(0, PAGE_H-band_h, PAGE_W, band_h, fill=1, stroke=0)
        cx, cy = 150*mm, PAGE_H-35*mm
        for radius, colour, lw in [(68, PURPLE, 20), (53, BLUE, 10), (43, CYAN, 7),
                                   (35, GREEN, 4), (27, colors.HexColor('#B2DFF0'), 3)]:
            canvas.setStrokeColor(colour)
            canvas.setLineWidth(lw)
            canvas.circle(cx,cy,radius*mm/3,fill=0,stroke=1)
        canvas.setStrokeColor(colors.HexColor('#80D7ED'))
        canvas.setLineWidth(1)
        for k in range(12):
            x=32*mm + k*8.5*mm
            canvas.line(x,PAGE_H-58*mm,x+12*mm,PAGE_H-17*mm)
        canvas.setFillColor(colors.HexColor('#6CE7D0'))
        canvas.rect(19*mm, PAGE_H-71*mm, 47*mm, 2.2*mm, fill=1, stroke=0)
        canvas.setFillColor(PURPLE)
        canvas.rect(19*mm, 30*mm, 42*mm, 1.8*mm, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor('#C3CBD3'))
        canvas.setLineWidth(.6)
        canvas.line(19*mm, 28*mm, 191*mm, 28*mm)
        canvas.setFillColor(PURPLE); canvas.setFont(FONT_BOLD,9)
        canvas.drawString(19*mm, 21*mm, 'BIOTWIN   /   SINGAPORE')
        canvas.setFont(FONT,9); canvas.setFillColor(SLATE)
        canvas.drawRightString(191*mm,21*mm,'SCENARIO ASSESSMENT   /   DISCUSSION DRAFT')
    else:
        idx = (doc.page-1) % len(SECTION_COLORS)
        accent = SECTION_COLORS[idx]
        # Narrow navigation rail keeps body text and tables at original widths.
        canvas.setFillColor(PALE_PURPLE)
        canvas.rect(0,0,12*mm,PAGE_H,fill=1,stroke=0)
        canvas.setFillColor(accent)
        canvas.rect(0,PAGE_H-78*mm,3.4*mm,55*mm,fill=1,stroke=0)
        canvas.saveState()
        canvas.translate(6.4*mm,36*mm); canvas.rotate(90)
        canvas.setFillColor(PURPLE);canvas.setFont(FONT_BOLD,7.2)
        canvas.drawString(0,0,'BIOTWIN  /  PROJECT ASSESSMENT')
        canvas.restoreState()
        canvas.setFillColor(accent)
        canvas.rect(19*mm,PAGE_H-17.7*mm,29*mm,1.25*mm,fill=1,stroke=0)
        canvas.setStrokeColor(colors.HexColor('#CED6DE')); canvas.setLineWidth(.45)
        canvas.line(48*mm,PAGE_H-17.2*mm,191*mm,PAGE_H-17.2*mm)
        canvas.setFillColor(PURPLE);canvas.setFont(FONT_BOLD,8.5)
        canvas.drawString(19*mm,PAGE_H-13*mm,'BIOTWIN   /   SINGAPORE')
        canvas.setStrokeColor(colors.HexColor('#CAD1D9'));canvas.setLineWidth(.45)
        canvas.line(19*mm,17*mm,191*mm,17*mm)
        canvas.setFont(FONT,8);canvas.setFillColor(SLATE)
        canvas.drawString(19*mm,12*mm,'Indicative scenario screening  |  Independent review required')
        canvas.setFillColor(accent);canvas.setFont(FONT_BOLD,8.5)
        canvas.drawRightString(191*mm,12*mm,str(doc.page).zfill(2))
    if preview_mode:
        canvas.setFont(FONT_BOLD, 7.5)
        canvas.setFillColor(MAGENTA)
        canvas.drawRightString(191*mm, PAGE_H-20.5*mm, 'DESIGN PREVIEW - ILLUSTRATIVE VALUES')
    canvas.restoreState()


def make_report(result: dict, *, sector_comparison: list[dict] | None = None,
                site_view_png: bytes | None = None,
                site_profiles: list[dict] | None = None,
                map_source: str = 'browser', preview_mode: bool = False) -> bytes:
    """Render exactly the evaluated scenario; retain full-colour WebGL map and true figures."""
    # This report never changes economic results. If the commercial finance audit
    # extension is installed, refuse inconsistent financial rows before exporting.
    try:
        from .finance_audit import audit_financial_result
    except ImportError:
        audit_financial_result = None
    if audit_financial_result is not None:
        audit_financial_result(result)
    if not site_view_png or (map_source != 'browser' and not preview_mode):
        raise ValueError('A genuine 3D map capture from the BioTwin Results view is required for this PDF.')
    r=result;m=r['metrics'];sc=r['scenario']; bau=r.get('bau') or {};years=r.get('years') or []
    layout=r.get('layout') or [];location=', '.join(z.get('name','') for z in layout) or 'Selected candidate sites'
    basis=sc.get('feedstock_basis','vegetation_proxy')
    is_sector=basis=='six_sector_scenario'
    names=', '.join(z.get('label','') for z in layout)
    dated=datetime.now(timezone.utc).strftime('%d %B %Y')
    pdf=BytesIO()
    doc=SimpleDocTemplate(pdf, pagesize=A4, rightMargin=19*mm,leftMargin=19*mm,
                          topMargin=24*mm,bottomMargin=21*mm, title='BioTwin | Scenario Assessment',
                          author='BioTwin Singapore Research Team', pageCompression=1)
    story=[]

    # COVER
    story += [Spacer(1, 56*mm),P('BIOTWIN    |    SINGAPORE','coverK'),
              P('Horticultural waste<br/>to biochar','coverT'),
              P('Scenario assessment and investment screening','coverS'),Spacer(1,13*mm),
              P('DEMONSTRATION / TECHNICAL DISCUSSION DRAFT','coverK'),
              P('Selected configuration: '+t(location),'coverS'),
              P('Modelled plant: '+t(names),'coverS'),
              P('Prepared '+dated,'coverS'),
              PageBreak()]

    # PAGE 2
    story += heading('01 / The investment question','Executive summary')
    story.append(P('This report evaluates a candidate Singapore horticultural waste-to-biochar configuration using the BioTwin screening model. '
                   'It presents the chosen sites, operating scale, cash-flow forecast and climate comparison against the modelled existing waste use.'))
    story.append(Spacer(1,4*mm))
    story.append(metrics([('Annual input',num(m.get('processed_t'))+' t'),('Initial investment',money(m.get('capex_sgd'))),
                          ('15-year NPV' if m.get('analysis_years') == 15 else 'Project NPV',money(m.get('npv_sgd')))]))
    story.append(Spacer(1,5*mm))
    story.append(metrics([('Levelised cost',money(m.get('levelised_cost_sgd_per_t'))+'/t'),
                          ('Break-even gate fee',money(m.get('break_even_gate_fee_sgd_per_t'))+'/t'),
                          ('Net climate vs baseline',num(m.get('net_climate_t'))+' tCO2e/y')]))
    story.append(P('Decision implications','h2'))
    for i,f in enumerate((r.get('findings') or [])[:4],1):
        story.append(P(f'<b>{i:02d}  {t(f.get("title", "Finding"))}.</b> {t(f.get("text",""))}'))
    story += [P('Interpretation boundary','h2'),P('The site positions are candidate planning anchors, not approved or available parcels. Plant and waste costs include vendor and published inputs plus assumptions. '
                  'Any credit quantity is an indicative calculation, not issued or guaranteed credits.'),PageBreak()]

    # PAGE 3
    story += heading('02 / Proposed configuration','Facilities and logistics')
    story.append(P(f'<b>Deployment:</b> {t(location)}. <b>Facility types:</b> {t(names)}. The model allocates material from planning-area origins to meet facility capacity subject to estimated accessibility.'))
    story.append(table(['Candidate site','Plant','Capacity t/y','Throughput t/y'],
                       [[z.get('name',''), z.get('label',''), num(z.get('capacity_t')),num(z.get('throughput_t'))] for z in layout],
                       [67*mm,47*mm,29*mm,29*mm]))
    story.append(Spacer(1,6*mm))
    story.append(metrics([('Average journey',num(m.get('mean_haul_km'),1)+' km'),
                          ('Annual woody input',num(m.get('processed_t'))+' t'),
                          ('Estimated staff',num(m.get('staff')))]))
    story.append(P('Feedstock basis','h2'))
    story.append(P(('Six PWC sector shares from a supplied Word document are used as a <b>synthetic alternative allocation</b>. '
                    'The six totals sum to the observed NEA national 232,000-tonne figure, but have not been verified against operator collection data.'
                    if is_sector else
                    'The spatial distribution is derived by allocating the observed NEA national total over the 55 planning areas using tree inventory and land-cover proxies. '
                    'This is a modelled distribution, not measured planning-area collections.')))
    story.append(P('Road information is sourced from the app\'s cached routing matrix, subject to route availability and travel-time assumptions. '
                   'Real route availability, haulier rates, permits and site tenancy require separate due diligence.','muted'))
    story += [PageBreak()]

    # NEW PAGE 4 - USER-SELECTED 3D MAP + GEOGRAPHY / VERIFIED DEMOGRAPHIC CONTEXT
    story += heading('03 / Site geography','Selected area and surrounding catchment')
    if site_view_png:
        try:
            visual = RLImage(BytesIO(site_view_png))
            iw,ih = visual.imageWidth,visual.imageHeight
            visual.drawWidth=CONTENT_W
            visual.drawHeight=min(98*mm,CONTENT_W*ih/max(iw,1))
            if visual.drawHeight < 52*mm:
                visual.drawHeight=52*mm
            story.append(HRFlowable(width='100%', thickness=2.0, color=CYAN, spaceBefore=2, spaceAfter=4))
            story.append(visual)
            story.append(HRFlowable(width='100%', thickness=1.0, color=GREEN, spaceBefore=4, spaceAfter=5))
            story.append(Spacer(1,1*mm))
            if preview_mode:
                story.append(P('Figure 1. Illustrative design fixture to preview the colour map frame. The production report uses a capture of the actual interactive BioTwin 3D map. Not geographic evidence or a site survey.', 'muted'))
            elif map_source=='browser':
                story.append(P('Figure 1. Full-colour capture of the selected 3D map in BioTwin Results. '
                               'Planning area extrusions encode estimated feedstock, and facility markers identify the modelled candidate sites. '
                               'Map data: OpenStreetMap contributors; spatial inputs: BioTwin. Not an aerial photograph or a site survey.', 'muted'))
            else:
                story.append(P('Figure 1. Model-generated isometric site visualization; column height represents estimated feedstock '
                               'and is not physical building, vegetation or terrain elevation. Not a satellite image or site survey.','muted'))
        except Exception:
            story.append(P('Site map image could not be embedded. The site description and source details below remain valid.','muted'))
    else:
        story.append(P('No site screenshot was available in this evaluation.','muted'))
    profile_rows=(site_profiles or [])[:2]  # compact executive site context; preserve nine-page format
    story.append(P('Local spatial context' + (' (first two sites)' if len(site_profiles or []) > 2 else ''), 'h2'))
    if profile_rows:
        story.append(table(['Candidate site','Planning area','Managed trees','Tree cover','Built land'],
                           [[x.get('site_name',''),x.get('planning_area',''),num(x.get('tree_count')),
                             num(x.get('tree_cover_pct'),1)+'%' if x.get('tree_cover_pct') is not None else 'n/a',
                             num(x.get('built_cover_pct'),1)+'%' if x.get('built_cover_pct') is not None else 'n/a']
                            for x in profile_rows],
                           [50*mm,44*mm,26*mm,26*mm,26*mm],small=True))
        story.append(Spacer(1,2*mm))
        story.append(P('Population and households','h2'))
        story.append(metrics([('Singapore residents, 2025','4.20m'),('Resident households, 2025','1.487m')]))
        story.append(Spacer(1,2*mm))
        story.append(P('National context only (Singapore Department of Statistics, Population Trends 2025 and General Household Survey 2025). '
                       'These figures are not local site populations and do not enter the facility model.','muted'))
        observed=[x for x in profile_rows if x.get('resident_population') is not None]
        if observed:
            story.append(table(['Planning area','Resident population','Resident households','Reference year'],
                         [[x['planning_area'],num(x['resident_population']),num(x.get('resident_households')),
                           str(x['population_year'])] for x in observed],
                         [57*mm,42*mm,43*mm,30*mm],small=True))
            story.append(P('Resident statistics are supplied from the optional demographic register. They describe the '
                           'planning area rather than the population exposed to an individual facility. Source details are provided in the register.','muted'))
        else:
            story.append(P('No verified planning-area resident population or household figures were supplied with this model. '
                           'An official demographic CSV can be added without changing the engineering results. '
                           'Source to obtain: Singapore Department of Statistics, geographic distribution tables (June 2025).','muted'))
    else:
        story.append(P('Candidate planning area context is unavailable for this output.','muted'))
    story.append(P('Scope limitation: environmental exposure, nearby sensitive receptors, site permissions and '
                   'local planning constraints require a dedicated site survey. Vegetation and population distributions '
                   'cannot independently establish the suitability of a plant.','muted'))
    story.append(PageBreak())

    # PAGE 5
    story += heading('04 / Investment economics','The business case')
    story.append(metrics([('Net present value',money(m.get('npv_sgd'))),
                          ('Payback','Year '+str(m['payback_year']) if m.get('payback_year') else 'No payback'),
                          ('Internal rate of return',pct(m.get('irr')) if m.get('irr') is not None else 'Not achieved')]))
    story += [P('Levelised cost composition (S$ per wet tonne)','h2'),
              Bars(sorted((r.get('cost_per_t') or {}).items(), key=lambda x: -float(x[1] or 0))[:7]),
              P('Annual cash generation is affected by commissioned capacity, wages, nominal price escalation and the assumed carbon credit price path. '
                'The year-zero capital investment is included once in the project NPV.','muted'),
              P('Cumulative nominal project cash flow (S$ million)','h2'), CashCurve(years),
              P('The break-even gate fee is a modelled threshold, not a confirmed market fee. Benchmark: '+money(r.get('gate_fee_cap_sgd'))+'/t for the referenced incineration benchmark.','muted'),
              PageBreak()]

    # PAGE 5
    story += heading('05 / Climate outcome','Carbon accounting')
    stored=m.get('stored_co2_t');credit=m.get('credits_t');baseline=bau.get('avoided_t');net=m.get('net_climate_t')
    story += [metrics([('Gross stored CO2',num(stored)+' t/y'),('Potential registry basis',num(credit)+' t/y'),
                       ('Net vs existing use',num(net)+' t/y')]),Spacer(1,5*mm),
              P('Components of the climate comparison (tCO2e per year)','h2'),
              Bars([('Durable carbon stored',stored or 0),('Modelled credit quantity',credit or 0),
                    ('Baseline avoided emissions',baseline or 0),('Net change',net or 0)],height=164),
              P('Interpretation','h2'),
              P('Gross carbon storage, potential credit quantities, and net impact against existing waste use are separate measures. '
                'Carbon credits are not confirmed issued or saleable and must not be assumed to be equivalent to net climate impact. '
                'Creditable quantities require verified feedstock origin, lifecycle inventory, durable biochar end use and a relevant registry methodology.'),
              P('The existing-use comparator assumes the same woody waste continues to an energy recovery pathway. '
                'This counterfactual must be verified with local waste operators before external investment claims.','muted'),
              PageBreak()]

    # PAGE 7
    story += heading('06 / Project finance','Annual cash-flow schedule')
    selected=years
    story.append(P('Indicative nominal cash flows, including construction year and the app\'s operating assumptions. All amounts in S$ thousands.'))
    story.append(table(['Year','Tonnes','Revenue (S$k)','OPEX (S$k)','Other net (S$k)','Cash flow (S$k)'],
                       [[int(x.get('calendar_year') or 0), num(x.get('tonnes')),
                         num((float(x.get('biochar_sales_sgd') or 0)+float(x.get('gate_fees_sgd') or 0)+float(x.get('credit_sales_sgd') or 0))/1000),
                         num(sum(float(x.get(f) or 0) for f in ['staff_sgd','maintenance_sgd','land_sgd','electricity_sgd','trucking_sgd','certification_sgd'])/1000),
                         num((float(x.get('grant_sgd') or 0)-float(x.get('illustrative_tax_sgd') or 0)-float(x.get('capital_sgd') or 0))/1000),
                         num(float(x.get('cash_flow_sgd') or 0)/1000)] for x in selected],
                       [23*mm,23*mm,32*mm,32*mm,31*mm,31*mm],small=True))
    story += [P('Cash flow = revenue - cash OPEX + grants - cash taxes - capital expenditure. The construction investment is deducted once; noncash depreciation is not a cash expense.','muted'),PageBreak()]

    # PAGE 8 - FINAL CONCLUSION: scenario-specific, with no evidence register or sector table.
    story += heading('07 / Conclusion', 'Decision assessment and recommendation')
    npv_value = m.get('npv_sgd')
    net_value = m.get('net_climate_t')
    fee_value = m.get('break_even_gate_fee_sgd_per_t')
    try:
        npv_value = float(npv_value)
        valid_npv = isfinite(npv_value)
    except (TypeError, ValueError):
        valid_npv = False
    try:
        net_value = float(net_value)
        valid_net = isfinite(net_value)
    except (TypeError, ValueError):
        valid_net = False

    story.append(P('Final screening outcome', 'h2'))
    story.append(metrics([('Project NPV', money(m.get('npv_sgd'))),
                          ('Break-even gate fee', money(fee_value) + '/t'),
                          ('Net climate difference', num(m.get('net_climate_t')) + ' tCO2e/y')]))
    story.append(Spacer(1, 5*mm))

    if valid_npv and npv_value < 0:
        investment_verdict = ('Under the assumptions selected for this evaluation, the configuration has a negative net '
                              'present value. It does not demonstrate a financially viable investment at the tested prices, '
                              'costs and throughput. A lower relative system cost is not, by itself, evidence of investability.')
        investment_label = 'Financial assessment: investment not justified on current inputs'
    elif valid_npv and npv_value >= 0:
        investment_verdict = ('Under the selected scenario inputs, the project has a non-negative net present value. '
                              'This indicates a potentially attractive modelled case, not a confirmed bankable project: '
                              'capital, product offtake, credit revenues and operating contracts are not independently secured.')
        investment_label = 'Financial assessment: potentially attractive scenario'
    else:
        investment_verdict = ('The financial outcome cannot be determined from the supplied results. '
                              'The project should not be represented as financially feasible until the model output is complete.')
        investment_label = 'Financial assessment: outcome unavailable'
    story.append(P(t(investment_label), 'h2'))
    story.append(P(t(investment_verdict)))

    story.append(P('Operational implications', 'h2'))
    story.append(P('The assessed configuration locates ' + t(names or 'the selected plant configuration') +
                   ' at ' + t(location) + ', with annual processed feedstock of <b>' +
                   num(m.get('processed_t')) + ' tonnes</b> and modelled average feedstock transport of <b>' +
                   num(m.get('mean_haul_km'), 1) + ' km</b>. These are planning outputs for candidate locations, '
                   'not completed engineering designs, planning approvals or supplier commitments.'))

    story.append(P('Carbon interpretation', 'h2'))
    if valid_net and net_value < 0:
        carbon_verdict = ('Relative to the selected existing-use baseline, the model indicates a negative net '
                          'climate difference. Gross biochar carbon storage does not establish an incremental '
                          'climate benefit when the displaced waste management pathway is considered.')
    elif valid_net and net_value > 0:
        carbon_verdict = ('The model indicates a positive net climate difference relative to the assumed '
                          'existing-use baseline. This is conditional on measured process emissions, '
                          'the actual fate of the waste and the durability of the resulting biochar.')
    elif valid_net:
        carbon_verdict = ('The model estimates no incremental net climate advantage under the selected baseline.')
    else:
        carbon_verdict = ('A defensible net climate comparison is not available for this scenario.')
    story.append(P(t(carbon_verdict)))
    story.append(P('Potential credit quantities describe a separate registry screening basis; they are not '
                   'issued credits or a substitute for comparative lifecycle analysis.', 'muted'))

    story.append(P('Overall conclusion', 'h2'))
    story.append(P('BioTwin provides a repeatable preliminary decision framework that links geographically '
                   'allocated feedstock, candidate facility locations, transport routing, cash-flow economics '
                   'and carbon accounting. The present analysis is a <b>scenario screening assessment</b>, '
                   'not a construction recommendation or a validated investment appraisal.'))
    story.append(P('The findings are best used to compare alternatives and identify commercially consequential '
                   'uncertainties. Any proposal advanced beyond screening requires independent verification '
                   'of waste supply, available sites, vendor costs, product demand and the existing waste-use baseline.',
                   'muted'))

    doc.build(story,onFirstPage=lambda c,d:frame(c,d,True,preview_mode),onLaterPages=lambda c,d:frame(c,d,False,preview_mode))
    return pdf.getvalue()
