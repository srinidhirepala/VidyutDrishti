"""Rebuild slide 9 (Working Prototype) with all 7 fresh snapshots."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from lxml import etree
import copy, os

SNAP = r'c:\Hackathon\VidyutDrishti\snapshots'
PPT  = r'c:\Hackathon\VidyutDrishti\VidyutDrishti_Pitch.pptx'

MODULES = [
    ('01-dashboard.png',         'Dashboard',         'KPIs · 6 charts · feeder forecast'),
    ('02-inspection-queue.png',  'Inspection Queue',  'Ranked by Rs. × confidence'),
    ('03-meter-lookup.png',      'Meter Lookup',      '4-layer drill-down · rule trace'),
    ('04-feedback-form.png',     'Feedback',          'Inspector outcome · live refresh'),
    ('05-zone-map.png',          'Zone Risk Map',     'Bengaluru Leaflet heatmap'),
    ('06-evaluation-metrics.png','Eval Metrics',      'Live P=78% · R=85% · F1=0.81'),
    ('07-roi-calculator.png',    'ROI Calculator',    'Interactive sliders · 5-yr NPV'),
]

COLOR_PRIMARY   = RGBColor(15, 23, 42)
COLOR_SECONDARY = RGBColor(30, 64, 175)
COLOR_WHITE     = RGBColor(255, 255, 255)
COLOR_LIGHT     = RGBColor(248, 250, 252)
COLOR_BODY      = RGBColor(30, 41, 59)
COLOR_GOLD      = RGBColor(161, 98, 7)

prs  = Presentation(PPT)
W    = prs.slide_width
H    = prs.slide_height
slide = prs.slides[8]   # 0-indexed → slide 9

# ── remove everything except the header bar, title texts, footer, and counter ──
KEEP_TEXT = {
    'WORKING PROTOTYPE',
    'Seven modules, all live in the submitted Docker stack',
    '09 / 12',
    'VidyutDrishti  ·  AI for Bharat  ·  Theme 8: Smart Meter Intelligence & Loss Detection (BESCOM)',
    'github.com/srinidhirepala/VidyutDrishti',
}

to_remove = []
for shape in slide.shapes:
    t = shape.text_frame.text.strip() if shape.has_text_frame else ''
    if shape.shape_type == 13:          # picture → always remove
        to_remove.append(shape)
    elif t and t not in KEEP_TEXT:      # text not in keep-list → remove
        to_remove.append(shape)
    elif not t and shape.shape_type != 1:  # non-rect, no text → remove
        to_remove.append(shape)

sp_tree = slide.shapes._spTree
for shape in to_remove:
    sp_tree.remove(shape._element)

# ── layout: 4 cards top row, 3 cards bottom row ──
MARGIN_L  = Inches(0.25)
MARGIN_T  = Inches(1.30)
GAP       = Inches(0.18)
CARD_H    = Inches(2.55)
IMG_FRAC  = 0.68          # fraction of card height for image

total_w   = W - MARGIN_L * 2
card_w4   = (total_w - GAP * 3) / 4
card_w3   = (total_w - GAP * 2) / 3

def add_card(slide, img_path, title, subtitle, left, top, cw, ch):
    img_h = Emu(ch * IMG_FRAC)
    lbl_h = ch - img_h

    # white card background
    bg = slide.shapes.add_shape(1, left, top, cw, ch)
    bg.fill.solid(); bg.fill.fore_color.rgb = COLOR_WHITE
    bg.line.color.rgb = RGBColor(203, 213, 225); bg.line.width = Pt(0.5)

    # screenshot image
    slide.shapes.add_picture(img_path, left, top, cw, img_h)

    # navy label bar
    bar = slide.shapes.add_shape(1, left, top + img_h, cw, lbl_h)
    bar.fill.solid(); bar.fill.fore_color.rgb = COLOR_SECONDARY
    bar.line.fill.background()

    # title text
    tb = slide.shapes.add_textbox(left + Inches(0.05), top + img_h + Inches(0.04),
                                  cw - Inches(0.1), lbl_h * 0.55)
    tf = tb.text_frame; tf.word_wrap = False
    p  = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r  = p.add_run(); r.text = title
    r.font.bold = True; r.font.size = Pt(8); r.font.color.rgb = COLOR_WHITE

    # subtitle text
    tb2 = slide.shapes.add_textbox(left + Inches(0.05), top + img_h + lbl_h * 0.52,
                                   cw - Inches(0.1), lbl_h * 0.48)
    tf2 = tb2.text_frame; tf2.word_wrap = False
    p2  = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.LEFT
    r2  = p2.add_run(); r2.text = subtitle
    r2.font.bold = False; r2.font.size = Pt(6.5); r2.font.color.rgb = RGBColor(186, 230, 253)

# top row: 4 cards
for i in range(4):
    left = MARGIN_L + i * (card_w4 + GAP)
    img, title, sub = MODULES[i]
    add_card(slide, os.path.join(SNAP, img), title, sub, left, MARGIN_T, card_w4, CARD_H)

# bottom row: 3 cards centred
row2_top = MARGIN_T + CARD_H + GAP
for i in range(3):
    left = MARGIN_L + i * (card_w3 + GAP)
    img, title, sub = MODULES[4 + i]
    add_card(slide, os.path.join(SNAP, img), title, sub, left, row2_top, card_w3, CARD_H)

prs.save(PPT)
print(f"Slide 9 rebuilt with 7 snapshots. Saved.")
