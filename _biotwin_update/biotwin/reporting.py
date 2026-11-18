"""BioTwin scenario-specific consultancy PDF, black-and-white with Times New Roman.

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
from reportlab.platypus import (Flowable, HRFlowable, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

BLACK = colors.black
WHITE = colors.white
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
                             textColor=BLACK, spaceAfter=12),
    'coverT': ParagraphStyle('coverT', fontName=FONT_BOLD, fontSize=29, leading=34,
                             textColor=BLACK, spaceAfter=17),
    'coverS': ParagraphStyle('coverS', fontName=FONT, fontSize=12, leading=18,
                             textColor=BLACK, spaceAfter=10),
    'sectionK': ParagraphStyle('sectionK', fontName=FONT_BOLD, fontSize=9.5, leading=12,
                               textColor=BLACK, spaceBefore=3, spaceAfter=9),
    'h1': ParagraphStyle('h1', fontName=FONT_BOLD, fontSize=22, leading=27,
                         textColor=BLACK, spaceAfter=14),
    'h2': ParagraphStyle('h2', fontName=FONT_BOLD, fontSize=12.5, leading=16,
                         textColor=BLACK, spaceBefore=12, spaceAfter=8),
    'body': ParagraphStyle('body', fontName=FONT, fontSize=10, leading=14.5,
                           textColor=BLACK, spaceAfter=9),
    'muted': ParagraphStyle('muted', fontName=FONT_ITALIC, fontSize=8.8, leading=12,
                            textColor=BLACK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName=FONT, fontSize=8.4, leading=11,
                            textColor=BLACK),
    'smallBold': ParagraphStyle('smallBold', fontName=FONT_BOLD, fontSize=8.4, leading=11,
                                textColor=BLACK),
    'metricV': ParagraphStyle('metricV', fontName=FONT_BOLD, fontSize=16.5, leading=20,
                              textColor=BLACK),
    'metricL': ParagraphStyle('metricL', fontName=FONT, fontSize=8, leading=10,
                              textColor=BLACK),
    'disclaimer': ParagraphStyle('disclaimer', fontName=FONT, fontSize=8.5, leading=12,
                                 textColor=BLACK),
}


def P(text, sty='body'):
    return Paragraph(str(text), STYLE[sty])


def line():
    return HRFlowable(width='100%', thickness=0.65, color=BLACK, spaceBefore=7, spaceAfter=11)


def heading(kicker, title):
    return [P(kicker.upper(), 'sectionK'), P(title, 'h1'), line()]


def metrics(items):
    cells = []
    for title, value in items:
        cells.append([P(t(title).upper(), 'metricL'), P(t(value), 'metricV')])
    tab = Table([cells], colWidths=[CONTENT_W / len(cells)] * len(cells), rowHeights=58)
    tab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), WHITE),
        ('BOX', (0, 0), (-1, -1), .5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), .35, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
    ]))
    return tab


def table(headers, rows, widths=None, *, small=False):
    def cell(v, bold=False):
        return P(t(v), 'smallBold' if bold else 'small')
    data = [[cell(v, True) for v in headers]] + [[cell(v) for v in row] for row in rows]
    tab = Table(data, colWidths=widths or [CONTENT_W / len(headers)] * len(headers), repeatRows=1, hAlign='LEFT')
    tab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), WHITE),
        ('LINEABOVE', (0, 0), (-1, 0), .7, BLACK),
        ('LINEBELOW', (0, 0), (-1, 0), .7, BLACK),
        ('LINEBELOW', (0, 1), (-1, -1), .2, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 7 if not small else 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7 if not small else 4),
    ]))
    return tab


class Bars(Flowable):
    """Print-friendly black ink chart with outlined negative values."""
    def __init__(self, items, width=CONTENT_W, height=172, color=BLACK):
        super().__init__()
        self.items=items; self.width=width; self.height=height
    def draw(self):
        c = self.canv
        vals = [abs(float(v or 0)) for _, v in self.items]
        mx = max(vals + [1.0])
        for i, (lbl, val) in enumerate(self.items):
            y = self.height-20-i*(self.height-17)/max(len(self.items),1)
            c.setFont(FONT,8.5);c.setFillColor(BLACK);c.drawString(0,y,str(lbl)[:46])
            x = 179;w = self.width-x-61
            bar_w = max(1.5,w*abs(float(val or 0))/mx)
            c.setStrokeColor(BLACK);c.setLineWidth(.45)
            c.rect(x,y-1,w,9,fill=0,stroke=1)
            if float(val or 0)>=0:
                c.setFillColor(BLACK);c.rect(x,y-1,bar_w,9,fill=1,stroke=0)
            else:
                c.setStrokeColor(BLACK);c.setLineWidth(1)
                c.rect(x,y-1,bar_w,9,fill=0,stroke=1)
                for xx in range(0,int(bar_w),6):
                    c.line(x+xx,y-1,x+min(xx+9,bar_w),y+8)
            c.setFillColor(BLACK);c.setFont(FONT_BOLD,8.2);c.drawRightString(self.width,y,num(val))


class CashCurve(Flowable):
    def __init__(self, years, width=CONTENT_W, height=165):
        super().__init__(); self.years=years;self.width=width;self.height=height
    def draw(self):
        c=self.canv;vals=[float(r.get('cumulative_sgd') or 0)/1e6 for r in self.years]
        if len(vals)<2:return
        lo=min(vals+[0]);hi=max(vals+[0]);delta=max(hi-lo,1)
        left=48;right=self.width-16;bottom=24;top=self.height-18
        yy=lambda v:bottom+(v-lo)/delta*(top-bottom)
        c.setStrokeColor(BLACK);c.setLineWidth(.23)
        for q in [0,.5,1]:
            y=bottom+q*(top-bottom);v=lo+q*delta
            c.line(left,y,right,y);c.setFont(FONT,7.5);c.setFillColor(BLACK);c.drawRightString(left-6,y-2,f'{v:+.1f}m')
        if lo<=0<=hi:
            c.setStrokeColor(BLACK);c.setLineWidth(.65);c.setDash(3,3)
            c.line(left,yy(0),right,yy(0));c.setDash()
        c.setStrokeColor(BLACK);c.setLineWidth(1.9)
        for i in range(len(vals)-1):
            x1=left+(right-left)*i/(len(vals)-1)
            x2=left+(right-left)*(i+1)/(len(vals)-1)
            c.line(x1,yy(vals[i]),x2,yy(vals[i+1]))
        c.setFillColor(BLACK);c.setFont(FONT,7.5)
        c.drawString(left,bottom-13,'Build');c.drawRightString(right,bottom-13,f'Year {len(vals)-1}')
        c.circle(right,yy(vals[-1]),2.5,fill=1,stroke=0)


def frame(canvas, doc, cover=False):
    canvas.saveState()
    canvas.setFillColor(WHITE)
    canvas.rect(0,0,PAGE_W,PAGE_H,fill=1,stroke=0)
    canvas.setFillColor(BLACK);canvas.setStrokeColor(BLACK)
    if cover:
        canvas.setLineWidth(1.25)
        canvas.line(19*mm,PAGE_H-25*mm,191*mm,PAGE_H-25*mm)
        canvas.setLineWidth(.55)
        canvas.line(19*mm,31*mm,191*mm,31*mm)
        canvas.setFont(FONT_BOLD,9)
        canvas.drawString(19*mm,22*mm,'BIOTWIN  |  SINGAPORE')
        canvas.setFont(FONT,9)
        canvas.drawRightString(191*mm,22*mm,'SCENARIO ASSESSMENT  |  DISCUSSION DRAFT')
    else:
        canvas.setLineWidth(.65)
        canvas.line(19*mm,PAGE_H-17*mm,191*mm,PAGE_H-17*mm)
        canvas.setFont(FONT_BOLD,9)
        canvas.drawString(19*mm,PAGE_H-13*mm,'BIOTWIN  |  SCENARIO ASSESSMENT')
        canvas.setLineWidth(.45)
        canvas.line(19*mm,17*mm,191*mm,17*mm)
        canvas.setFont(FONT,8)
        canvas.drawString(19*mm,12*mm,'Illustrative decision support  |  Independent feasibility review required')
        canvas.drawRightString(191*mm,12*mm,str(doc.page).zfill(2))
    canvas.restoreState()


def make_report(result: dict, *, sector_comparison: list[dict] | None = None) -> bytes:
    """Build a PDF from the *current evaluated scenario* without changing model results."""
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
              P('Prepared '+dated+'  |  2025 feedstock baseline','coverS'),
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

    # PAGE 4
    story += heading('03 / Investment economics','The business case')
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
    story += heading('04 / Climate outcome','Carbon accounting')
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

    # PAGE 6
    story += heading('05 / 2025 spatial scenarios','Six-sector allocation cross-check')
    if sector_comparison:
        story.append(P('The document provides six Public Waste Collection sector shares. These allocations are <b>synthetic estimates</b>, '
                       'although the national total is based on published statistics. The table compares them with BioTwin\'s vegetation proxy allocation.'))
        story.append(table(['Public Waste Collector sector','Word proxy (t)','Tree proxy (t)','Difference (t)'],
                           [[x['pwc_sector'],num(x['synthetic_t']),num(x['original_proxy_t']),
                             num(x['difference_t'])] for x in sector_comparison],
                           [70*mm,31*mm,31*mm,40*mm],small=True))
        story.append(Spacer(1,6*mm))
        story.append(Bars([(x['pwc_sector'],x['synthetic_t']) for x in sector_comparison],height=190))
    else:
        story.append(P('Six-sector comparison data was not supplied for this report.'))
    story.append(P('<b>Interpretive rule:</b> matching the published national total is a mass balance check, not spatial validation. '
                   'The 75% woody / 25% leafy document split is an unverified composition assumption and is not silently substituted for the app\'s existing feedstock basis.','muted'))
    story.append(PageBreak())

    # PAGE 7
    story += heading('06 / Project finance','Annual cash-flow schedule')
    selected=years
    story.append(P('Indicative nominal cash flows, including construction year and the app\'s operating assumptions. All amounts in S$ thousands.'))
    story.append(table(['Calendar year','Processed tonnes','Revenue (S$k)','Operating cost (S$k)','Net cash flow (S$k)'],
                       [[int(x.get('calendar_year') or 0), num(x.get('tonnes')),
                         num((float(x.get('biochar_sales_sgd') or 0)+float(x.get('gate_fees_sgd') or 0)+float(x.get('credit_sales_sgd') or 0))/1000),
                         num(sum(float(x.get(f) or 0) for f in ['staff_sgd','maintenance_sgd','land_sgd','electricity_sgd','trucking_sgd','certification_sgd'])/1000),
                         num(float(x.get('cash_flow_sgd') or 0)/1000)] for x in selected],
                       [26*mm,30*mm,36*mm,42*mm,38*mm],small=True))
    story += [P('The first row is construction expenditure. Operating capital recovery charges are not additionally deducted from project cash flow.','muted'),PageBreak()]

    # PAGE 8
    story += heading('07 / Evidence register','Assumptions and next steps')
    key=('woody_share','collectable_share','biochar_price_usd','corc_spot_eur','discount_rate',
         'plant_life_years','operator_wage_sgd_month','electricity_price_sgd_kwh','haul_ef_kg_per_tkm')
    found=[a for a in r.get('assumptions',[]) if a.get('input') in key]
    if not found:found=r.get('assumptions',[])[:9]
    story.append(table(['Model input','Value used','Data classification','Origin'],
                       [[a.get('input'),num(a.get('value'),3),a.get('tag',''),str(a.get('source',''))[:70]] for a in found],
                       [50*mm,25*mm,26*mm,71*mm],small=True))
    story.append(P('Important qualifications','h2'))
    for x in [
        'The six-sector Word document contains no independently recorded operator tonnages. Its values cannot be used as a validation dataset.',
        'The model holds the national total fixed by construction. Spatial sector shares and planning-area quantities remain estimates.',
        'Facility sites have not been confirmed available, permitted or priced by suppliers for this exact project.',
        'Carbon credit quantities are conditional on registration, monitoring, verification and eligible use.',
        'Before procurement: obtain measured collections, plant and haul quotations, environmental permits, land availability and an independent lifecycle assessment.',
    ]:story.append(P('- '+t(x)))
    story.append(P('Data lineage','h2'))
    story.append(P('NEA national horticultural waste, 2025: 232,000 tonnes. Vegetation proxies: NParks tree inventory and ESA WorldCover as modelled by the project. '
                   'Alternative sector shares: supplied Word document, expressly labelled synthetic. Candidate sites, costs and carbon factors: BioTwin evidence register and underlying reference sources.'))
    story.append(Spacer(1,4*mm))
    story.append(P('Prepared with BioTwin Singapore as a scenario screening document. Independent consultant review and project feasibility studies are recommended prior to investment decisions.','muted'))

    doc.build(story,onFirstPage=lambda c,d:frame(c,d,True),onLaterPages=lambda c,d:frame(c,d,False))
    return pdf.getvalue()
