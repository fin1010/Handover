import streamlit as st
from datetime import datetime
import io
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# =========================================================
# APP IDENTITY
# =========================================================
APP_NAME = "Shift Handover Pro"
APP_VERSION = "v1.0"
VALUE_PROP = "Generate a clear shift handover summary + SBAR one-liner and export a professional PDF in under 60 seconds."
WHO_FOR = "Designed for care homes, wards, and teams needing fast, structured shift handovers."
SUPPORT_EMAIL = "finlayajayi@rocketmail.com"

PRIVACY_BANNER = (
    "Do not include identifiable personal data unless authorised by your organisation. "
    "This tool does not store submissions."
)
NOT_RECORD_DISCLAIMER = "This tool supports handover communication only. It is not a clinical record and is not medical advice."
DATA_STATEMENT = "No data is stored. Nothing is saved once the page is refreshed."

# =========================================================
# COLOURS (PDF)
# =========================================================
BRAND_DARK = colors.HexColor("#0f172a")
BRAND_ACCENT = colors.HexColor("#2563eb")
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#475569")
BORDER = colors.HexColor("#CBD5E1")
BG_SOFT = colors.HexColor("#F1F5F9")

# =========================================================
# HELPERS
# =========================================================
def now_str():
    return datetime.now().strftime("%d %b %Y, %H:%M")


def clean_lines(text: str) -> list[str]:
    if not text:
        return []
    lines = [ln.strip(" \t-•") for ln in text.splitlines()]
    return [ln for ln in lines if ln.strip()]


def pick_items(text: str, n: int) -> str:
    items = clean_lines(text)
    if not items:
        return "none"
    return "; ".join(items[:n])


# =========================================================
# ACCESS CODE GATE
# =========================================================
def check_access():
    if "access_granted" not in st.session_state:
        st.session_state["access_granted"] = False

    if st.session_state["access_granted"]:
        return

    st.markdown("## 🔒 Access Required")
    st.markdown("Enter your access code to use this tool.")
    code = st.text_input("Access code", type="password")

    if st.button("Unlock", use_container_width=True):
        expected = st.secrets.get("ACCESS_CODE", None)
        if not expected:
            st.error("No ACCESS_CODE is set in secrets yet. Add one in .streamlit/secrets.toml (local) or Streamlit Cloud → Secrets.")
        elif code.strip() == str(expected).strip():
            st.session_state["access_granted"] = True
            st.rerun()
        else:
            st.error("Invalid access code")

    st.caption(f"Support: {SUPPORT_EMAIL}")
    st.stop()


# =========================================================
# SAFE STATE ACTIONS (CLEAR / DEMO / TEMPLATE)
# =========================================================
def request_clear():
    st.session_state["_do_clear"] = True


def request_demo():
    st.session_state["_do_demo"] = True


def request_template(name: str):
    st.session_state["_do_template"] = name


TEMPLATES = {
    "Care Home": {
        "incidents": "Fall (time, location, injury/no injury)\nMedication error (what, when, action taken)\nSafeguarding concern (brief + escalated to who)",
        "staffing": "Staffing shortfall (role + times)\nAgency/new staff (handover needs)\nBreak cover issues",
        "residents": "Resident: concern + action + monitoring plan\nResident: behaviours + triggers + plan\nResident: hydration/nutrition risk + plan",
        "tasks": "Obs due + time\nCare plan update needed\nStock/maintenance task",
        "escalation": "Escalated to senior on shift as appropriate. Continue monitoring overnight.",
    },
    "NHS Ward": {
        "incidents": "Deterioration/NEWS2 trigger (score, actions)\nMedication issue (what, outcome)\nFall/pressure area concern",
        "staffing": "Ward short (role + times)\nBank/agency staff on shift\nHigh acuity bays needing support",
        "residents": "Patient: clinical concern + plan\nPatient: pending scans/results\nPatient: discharge barriers",
        "tasks": "Bloods due + time\nCannula/lines to review\nChase imaging/results\nDischarge paperwork",
        "escalation": "Escalated to nurse in charge/med reg as appropriate. SBAR used.",
    },
    "Generic": {
        "incidents": "Incident 1\nIncident 2",
        "staffing": "Staffing issue 1\nStaffing issue 2",
        "residents": "Person of concern 1\nPerson of concern 2",
        "tasks": "Task 1\nTask 2",
        "escalation": "",
    },
}


def apply_state_actions_before_widgets():
    """
    Apply queued changes BEFORE widgets instantiate to avoid:
    StreamlitAPIException: session_state.<key> cannot be modified after widget is instantiated.
    """
    if st.session_state.get("_do_clear"):
        st.session_state.update({
            "org_name": "",
            "area": "",
            "shift": "Day",
            "completed_by": "",
            "reviewed_by": "",
            "review_date": "",
            "incidents": "",
            "staffing": "",
            "residents": "",
            "tasks": "",
            "escalation": "",
            "pdf_style": "Detailed (multi-page)",
            "print_safe": False,
        })
        st.session_state["_do_clear"] = False

    if st.session_state.get("_do_demo"):
        st.session_state.update({
            "org_name": "Example Care Home",
            "area": "Cedar Wing",
            "shift": "Night",
            "completed_by": "Senior Carer",
            "reviewed_by": "Nurse in Charge",
            "review_date": datetime.now().strftime("%d %b %Y"),
            "incidents": "Non-injury fall in lounge at 21:10; monitoring plan in place\nMedication delay identified (non-critical); follow up in morning",
            "staffing": "1 HCA short from 02:00–07:00\nAgency staff briefed on escalation and call bell response",
            "residents": "Resident A: reduced oral intake; encourage fluids; monitor overnight\nResident B: agitation after 23:00; reassurance and observe",
            "tasks": "Re-check obs at 01:00 for Resident A\nRestock continence supplies\nChase GP callback in morning",
            "escalation": "Escalated to senior on shift as appropriate; continue monitoring overnight.",
            "pdf_style": "Detailed (multi-page)",
            "print_safe": False,
        })
        st.session_state["_do_demo"] = False

    tmpl = st.session_state.get("_do_template", "")
    if tmpl:
        t = TEMPLATES.get(tmpl)
        if t:
            st.session_state.update({
                "incidents": t["incidents"],
                "staffing": t["staffing"],
                "residents": t["residents"],
                "tasks": t["tasks"],
                "escalation": t["escalation"],
            })
        st.session_state["_do_template"] = ""


# =========================================================
# OUTPUT BUILDERS
# =========================================================
def make_sbar_oneliner(area, shift, incidents, staffing, residents, tasks, escalation) -> str:
    s = f"{area or 'Area'} {shift}: "
    b = f"incidents {pick_items(incidents, 2)}, staffing {pick_items(staffing, 2)}; "
    a = f"concerns {pick_items(residents, 2)}; "
    r = f"tasks {pick_items(tasks, 2)}"
    if escalation.strip():
        r += f"; escalate: {escalation.strip()}"
    return (s + b + a + r + ".").strip()


def make_handover_summary_md(area, shift, created_at, incidents, staffing, residents, tasks, escalation, reviewed_by, review_date, print_safe) -> str:
    def section(title: str, items: list[str]) -> str:
        if not items:
            return f"**{title}:** None reported.\n"
        bullets = "\n".join([f"- {x}" for x in items])
        return f"**{title}:**\n{bullets}\n"

    header = (
        f"### Handover Summary\n"
        f"**Area:** {area or '—'} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"**Shift:** {shift} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"**Generated:** {created_at}\n"
    )

    body = (
        section("Incidents today", clean_lines(incidents))
        + "\n"
        + section("Staffing issues", clean_lines(staffing))
        + "\n"
        + section("Residents of concern", clean_lines(residents))
        + "\n"
        + section("Tasks outstanding", clean_lines(tasks))
    )

    esc = escalation.strip()
    esc_line = f"\n**Escalation / Notes:** {esc if esc else 'None.'}\n"

    if print_safe:
        reviewed_block = "\n---\n**Reviewed by:** (hidden – print-safe mode)\n"
    else:
        reviewed_block = (
            "\n---\n"
            f"**Reviewed by:** {reviewed_by.strip() or '—'}  \n"
            f"**Review date:** {review_date.strip() or '—'}\n"
        )

    return header + "\n" + body + esc_line + reviewed_block


# =========================================================
# PDF HELPERS
# =========================================================
def _draw_logo_if_present(c, logo_bytes: bytes | None, x: float, y: float, max_w: float, max_h: float):
    if not logo_bytes:
        return
    try:
        img = ImageReader(io.BytesIO(logo_bytes))
        iw, ih = img.getSize()
        scale = min(max_w / iw, max_h / ih)
        w = iw * scale
        h = ih * scale
        c.drawImage(img, x, y - h, width=w, height=h, mask="auto")
    except Exception:
        return


def pdf_build_detailed(
    *,
    logo_bytes: bytes | None,
    org_name: str,
    area: str,
    shift: str,
    created_at: str,
    completed_by: str,
    reviewed_by: str,
    review_date: str,
    incidents: str,
    staffing: str,
    residents: str,
    tasks: str,
    escalation: str,
    sbar: str,
    print_safe: bool,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin_x = 16 * mm
    margin_top = 16 * mm
    margin_bottom = 16 * mm
    content_w = width - 2 * margin_x
    y = height - margin_top

    completed_by_pdf = "" if print_safe else (completed_by.strip() if completed_by else "")
    reviewed_by_pdf = "" if print_safe else (reviewed_by.strip() if reviewed_by else "")
    review_date_pdf = "" if print_safe else (review_date.strip() if review_date else "")

    def footer(page_num: int):
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.line(margin_x, margin_bottom + 12 * mm, width - margin_x, margin_bottom + 12 * mm)

        c.setFont("Helvetica", 8.8)
        c.setFillColor(TEXT_MUTED)
        c.drawString(margin_x, margin_bottom + 6 * mm, f"Generated: {created_at}")
        c.drawRightString(width - margin_x, margin_bottom + 6 * mm, f"Page {page_num}")

        c.setFont("Helvetica", 8.3)
        c.setFillColor(TEXT_MUTED)
        c.drawString(margin_x, margin_bottom + 2.5 * mm, f"{APP_NAME} {APP_VERSION} • Support: {SUPPORT_EMAIL}")

        if reviewed_by_pdf or review_date_pdf:
            rb = reviewed_by_pdf if reviewed_by_pdf else "—"
            rd = review_date_pdf if review_date_pdf else "—"
            c.drawRightString(width - margin_x, margin_bottom + 2.5 * mm, f"Reviewed by: {rb} • {rd}")

    def new_page(page_num: int):
        c.showPage()
        return height - margin_top

    def ensure_space(required_mm: float, page_num: int) -> tuple[float, int]:
        nonlocal y
        if y - required_mm < (margin_bottom + 20 * mm):
            footer(page_num)
            y = new_page(page_num + 1)
            page_num += 1
            draw_compact_header()
        return y, page_num

    def draw_header_bar():
        nonlocal y
        bar_h = 20 * mm
        c.setFillColor(BRAND_DARK)
        c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)

        _draw_logo_if_present(c, logo_bytes, margin_x, height - 4 * mm, max_w=26 * mm, max_h=14 * mm)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margin_x + (30 * mm if logo_bytes else 0), height - 13.5 * mm, "Shift Handover")

        c.setFont("Helvetica", 10)
        brand = org_name.strip() if org_name.strip() else APP_NAME
        c.drawRightString(width - margin_x, height - 13.3 * mm, brand)

        y = height - bar_h - 8 * mm

    def draw_compact_header():
        nonlocal y
        c.setFillColor(BG_SOFT)
        c.setLineWidth(0)
        c.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)

        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_x, height - 7 * mm, "Shift Handover")
        c.setFont("Helvetica", 9)
        c.setFillColor(TEXT_MUTED)
        c.drawRightString(width - margin_x, height - 7 * mm, f"{area or '—'} • {shift} • {created_at}")

        y = height - 10 * mm - 10 * mm

    def draw_section(title: str, items_text: str, page_num: int) -> int:
        nonlocal y
        items = clean_lines(items_text)

        wrap_width = 92
        bullet_lines = []
        if not items:
            bullet_lines = ["None reported."]
        else:
            for it in items:
                wrapped = textwrap.wrap(it, width=wrap_width, break_long_words=False, break_on_hyphens=False)
                bullet_lines.append("• " + wrapped[0])
                for cont in wrapped[1:]:
                    bullet_lines.append("   " + cont)

        required = (10 + 8 + len(bullet_lines) * 5.4 + 18) * mm
        y, page_num = ensure_space(required, page_num)

        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(TEXT_DARK)
        c.drawString(margin_x, y, title)
        y -= 6 * mm

        card_padding_top = 6 * mm
        line_h = 5.2 * mm
        card_h = (card_padding_top + len(bullet_lines) * line_h + 6 * mm)

        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.roundRect(margin_x, y - card_h, content_w, card_h, 6, fill=1, stroke=1)

        tx = margin_x + 7 * mm
        ty = y - card_padding_top
        c.setFont("Helvetica", 10.8)
        c.setFillColor(TEXT_DARK)
        for ln in bullet_lines:
            ty -= line_h
            c.drawString(tx, ty, ln)

        y -= (card_h + 8 * mm)
        return page_num

    def draw_notes(title: str, text: str, page_num: int) -> int:
        nonlocal y
        note = text.strip() if text.strip() else "None."
        lines = textwrap.wrap(note, width=100, break_long_words=False, break_on_hyphens=False) or [note]

        required = (10 + 8 + len(lines) * 5.4 + 18) * mm
        y, page_num = ensure_space(required, page_num)

        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(TEXT_DARK)
        c.drawString(margin_x, y, title)
        y -= 6 * mm

        card_padding_top = 6 * mm
        line_h = 5.2 * mm
        card_h = card_padding_top + len(lines) * line_h + 6 * mm

        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.roundRect(margin_x, y - card_h, content_w, card_h, 6, fill=1, stroke=1)

        c.setFont("Helvetica", 10.8)
        c.setFillColor(TEXT_DARK)
        tx = margin_x + 7 * mm
        ty = y - card_padding_top
        for ln in lines:
            ty -= line_h
            c.drawString(tx, ty, ln)

        y -= (card_h + 8 * mm)
        return page_num

    page = 1
    draw_header_bar()
    page = draw_section("Incidents today", incidents, page)
    page = draw_section("Staffing issues", staffing, page)
    page = draw_section("Residents of concern", residents, page)
    page = draw_section("Tasks outstanding", tasks, page)
    page = draw_notes("Escalation / Notes", escalation, page)
    page = draw_notes("SBAR one-liner", sbar, page)

    footer(page)
    c.save()
    return buf.getvalue()


def pdf_build_one_page_condensed(
    *,
    logo_bytes: bytes | None,
    org_name: str,
    area: str,
    shift: str,
    created_at: str,
    reviewed_by: str,
    review_date: str,
    incidents: str,
    staffing: str,
    residents: str,
    tasks: str,
    escalation: str,
    sbar: str,
    print_safe: bool,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin_x = 14 * mm
    margin_top = 14 * mm
    margin_bottom = 14 * mm
    content_w = width - 2 * margin_x

    reviewed_by_pdf = "" if print_safe else (reviewed_by.strip() if reviewed_by else "")
    review_date_pdf = "" if print_safe else (review_date.strip() if review_date else "")

    def title_bar():
        bar_h = 16 * mm
        c.setFillColor(BRAND_DARK)
        c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
        _draw_logo_if_present(c, logo_bytes, margin_x, height - 3 * mm, max_w=22 * mm, max_h=12 * mm)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin_x + (26 * mm if logo_bytes else 0), height - 11.3 * mm, "Shift Handover (Condensed)")

        c.setFont("Helvetica", 9)
        brand = org_name.strip() if org_name.strip() else APP_NAME
        c.drawRightString(width - margin_x, height - 11.0 * mm, brand)

    def footer():
        c.setStrokeColor(BORDER)
        c.line(margin_x, margin_bottom + 11 * mm, width - margin_x, margin_bottom + 11 * mm)
        c.setFont("Helvetica", 8.8)
        c.setFillColor(TEXT_MUTED)
        c.drawString(margin_x, margin_bottom + 6 * mm, f"Generated: {created_at}")

        c.setFont("Helvetica", 8.3)
        c.setFillColor(TEXT_MUTED)
        c.drawString(margin_x, margin_bottom + 2.5 * mm, f"{APP_NAME} {APP_VERSION} • Support: {SUPPORT_EMAIL}")

        if reviewed_by_pdf or review_date_pdf:
            rb = reviewed_by_pdf if reviewed_by_pdf else "—"
            rd = review_date_pdf if review_date_pdf else "—"
            c.drawRightString(width - margin_x, margin_bottom + 2.5 * mm, f"Reviewed by: {rb} • {rd}")

    def block(y, title, text, max_lines=6):
        items = clean_lines(text)
        wrap_width = 95
        lines = []
        if not items:
            lines = ["- None."]
        else:
            for it in items:
                wrapped = textwrap.wrap(it, width=wrap_width, break_long_words=False, break_on_hyphens=False)
                lines.append("- " + wrapped[0])
                for cont in wrapped[1:]:
                    lines.append("  " + cont)

        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["(more in app)"]

        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_x, y, title)
        y -= 5 * mm

        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        h = (len(lines) * 4.8 * mm) + 8 * mm
        c.roundRect(margin_x, y - h, content_w, h, 6, fill=1, stroke=1)

        c.setFont("Helvetica", 9.8)
        c.setFillColor(TEXT_DARK)
        ty = y - 6 * mm
        for ln in lines:
            c.drawString(margin_x + 6 * mm, ty, ln)
            ty -= 4.8 * mm

        return y - h - 6 * mm

    title_bar()
    y = height - margin_top - 18 * mm

    c.setFillColor(BG_SOFT)
    c.rect(margin_x, y - 10 * mm, content_w, 10 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_x + 4 * mm, y - 6.6 * mm, f"Area: {area or '—'}")
    c.drawString(margin_x + 70 * mm, y - 6.6 * mm, f"Shift: {shift}")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin_x - 4 * mm, y - 6.6 * mm, f"Generated: {created_at}")
    y -= 16 * mm

    y = block(y, "Incidents today", incidents, max_lines=6)
    y = block(y, "Staffing issues", staffing, max_lines=5)
    y = block(y, "Residents of concern", residents, max_lines=6)
    y = block(y, "Tasks outstanding", tasks, max_lines=6)
    y = block(y, "Escalation / Notes", escalation, max_lines=3)
    y = block(y, "SBAR one-liner", sbar, max_lines=2)

    footer()
    c.showPage()
    c.save()
    return buf.getvalue()


# =========================================================
# STREAMLIT UI
# =========================================================
st.set_page_config(page_title=APP_NAME, layout="wide")

# Gate first
check_access()

# Apply queued state changes BEFORE widgets render
apply_state_actions_before_widgets()

# Dark theme CSS (background same as sidebar)
st.markdown(
    """
<style>
/* App background = sidebar colour */
.stApp { background-color: #0b1220; color: #f8fafc; }

/* Sidebar */
section[data-testid="stSidebar"]{
  background-color:#0b1220;
  border-right: 1px solid #111827;
}
section[data-testid="stSidebar"] * { color:#f8fafc !important; }

/* Cards */
.card{
  background-color:#111827;
  border:1px solid #334155;
  border-radius:14px;
  padding:18px 18px 10px 18px;
  margin-bottom:16px;
  box-shadow: 0 10px 26px rgba(0,0,0,0.25);
}

/* Text */
.subtle{ color:#cbd5e1; }
.pill{
  display:inline-block;
  padding:6px 10px;
  border-radius:999px;
  background:#0f172a;
  border:1px solid #334155;
  color:#f8fafc;
  font-size:0.85rem;
}
.footerline{ color:#94a3b8; font-size:0.9rem; margin-top:8px; }

/* Inputs - main + sidebar (dark inputs, bright text) */
div[data-testid="stAppViewContainer"] input,
div[data-testid="stAppViewContainer"] textarea,
div[data-testid="stAppViewContainer"] select,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] select{
  background-color:#020617 !important;
  color:#f8fafc !important;
  border:1px solid #334155 !important;
  border-radius:10px !important;
}
div[data-testid="stAppViewContainer"] input::placeholder,
div[data-testid="stAppViewContainer"] textarea::placeholder,
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder{
  color:#94a3b8 !important;
  opacity:1 !important;
}
div[data-testid="stAppViewContainer"] input,
div[data-testid="stAppViewContainer"] textarea,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea{
  caret-color:#f8fafc !important;
}

/* Buttons */
.stButton>button{
  background:#2563eb !important;
  color:#ffffff !important;
  border:0 !important;
  border-radius:12px !important;
  font-weight:700 !important;
  padding:0.65rem 1rem !important;
}
.stDownloadButton>button{
  background:#0f172a !important;
  color:#ffffff !important;
  border:1px solid #334155 !important;
  border-radius:12px !important;
  font-weight:700 !important;
  padding:0.65rem 1rem !important;
}
pre { border-radius:12px !important; }
</style>
""",
    unsafe_allow_html=True,
)

# Header
st.markdown(f"<h1 style='margin-bottom:0.25rem'>{APP_NAME}</h1>", unsafe_allow_html=True)
st.markdown(f"<div class='subtle'>{VALUE_PROP}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtle'><b>{WHO_FOR}</b></div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtle'>Support: <b>{SUPPORT_EMAIL}</b></div>", unsafe_allow_html=True)
st.markdown(f"<div class='pill'>🛡️ {DATA_STATEMENT}</div>", unsafe_allow_html=True)
st.write("")

# Privacy banner (now readable on dark)
st.markdown(
    f"""
<div class="card">
  <div style="font-weight:800; margin-bottom:6px;">Privacy & Disclaimer</div>
  <div class="subtle" style="margin-bottom:8px;">{PRIVACY_BANNER}</div>
  <div style="font-weight:700;">{NOT_RECORD_DISCLAIMER}</div>
</div>
""",
    unsafe_allow_html=True,
)

# How-to (safe string)
with st.expander("How to use (1 minute)"):
    st.markdown(f"""
1) Fill each box with **one item per line** (keep it factual and brief).  
2) Click **Generate handover** to create the summary + SBAR.  
3) Click **Download PDF** to print/share.  
4) Use **Print-safe mode** to hide identity fields (it does **not** auto-redact free text).  
5) Refreshing the page clears the session — **{DATA_STATEMENT}**
""")

# Sidebar
with st.sidebar:
    st.subheader("Document settings")

    logo_file = st.file_uploader("Logo (PNG/JPG) for PDF", type=["png", "jpg", "jpeg"])
    logo_bytes = logo_file.getvalue() if logo_file else None

    st.text_input("Organisation name (optional)", key="org_name", placeholder="e.g., Penylan Care Home")
    st.text_input("Area / Unit (optional)", key="area", placeholder="e.g., Cedar Wing / Ward 7")
    st.selectbox("Shift", ["Day", "Night", "Long day", "Early", "Late", "Other"], key="shift")
    st.text_input("Completed by (optional)", key="completed_by", placeholder="Name + role (if appropriate)")

    st.divider()
    st.subheader("Review")
    st.text_input("Reviewed by", key="reviewed_by", placeholder="e.g., Nurse in charge / Senior carer")
    st.text_input("Review date", key="review_date", placeholder="e.g., 04 Feb 2026")

    st.divider()
    st.toggle(
        "Print-safe mode (hide identity fields)",
        key="print_safe",
        value=False,
        help="Hides Completed by / Reviewed by / Review date in PDF and on-screen. Does NOT auto-redact free-text boxes.",
    )

    st.divider()
    st.radio("PDF style", ["Detailed (multi-page)", "One-page (condensed)"], key="pdf_style", index=0)

    st.divider()
    st.subheader("Quick actions")
    if st.button("Load demo data", use_container_width=True):
        request_demo()
        st.rerun()

    st.subheader("Templates")
    c1, c2, c3 = st.columns(3)
    if c1.button("Care Home", use_container_width=True):
        request_template("Care Home")
        st.rerun()
    if c2.button("NHS Ward", use_container_width=True):
        request_template("NHS Ward")
        st.rerun()
    if c3.button("Generic", use_container_width=True):
        request_template("Generic")
        st.rerun()

    st.divider()
    if st.button("Clear form", use_container_width=True):
        request_clear()
        st.rerun()

    st.caption(f"🛡️ {DATA_STATEMENT}")

# Main layout
left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Input")

    incidents = st.text_area("Incidents today", height=140, key="incidents", placeholder="One item per line…")
    staffing = st.text_area("Staffing issues", height=110, key="staffing", placeholder="One item per line…")
    residents = st.text_area("Residents of concern", height=140, key="residents", placeholder="One item per line…")
    tasks = st.text_area("Tasks outstanding", height=140, key="tasks", placeholder="One item per line…")
    escalation = st.text_input("Escalation / Notes (optional)", key="escalation", placeholder="Optional…")

    generate = st.button("Generate handover", type="primary", use_container_width=True)
    st.markdown(f"<div class='footerline'><b>Data:</b> {DATA_STATEMENT}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Output")

    if generate:
        created_at = now_str()
        print_safe_value = st.session_state.get("print_safe", False)

        sbar = make_sbar_oneliner(
            area=st.session_state.get("area", ""),
            shift=st.session_state.get("shift", "Day"),
            incidents=incidents,
            staffing=staffing,
            residents=residents,
            tasks=tasks,
            escalation=escalation,
        )

        summary_md = make_handover_summary_md(
            area=st.session_state.get("area", ""),
            shift=st.session_state.get("shift", "Day"),
            created_at=created_at,
            incidents=incidents,
            staffing=staffing,
            residents=residents,
            tasks=tasks,
            escalation=escalation,
            reviewed_by=st.session_state.get("reviewed_by", ""),
            review_date=st.session_state.get("review_date", ""),
            print_safe=print_safe_value,
        )

        st.markdown(summary_md)
        st.divider()
        st.markdown("### SBAR one-liner")
        st.code(sbar, language="text")

        if st.session_state.get("pdf_style", "Detailed (multi-page)").startswith("One-page"):
            pdf_bytes = pdf_build_one_page_condensed(
                logo_bytes=logo_bytes,
                org_name=st.session_state.get("org_name", ""),
                area=st.session_state.get("area", ""),
                shift=st.session_state.get("shift", "Day"),
                created_at=created_at,
                reviewed_by=st.session_state.get("reviewed_by", ""),
                review_date=st.session_state.get("review_date", ""),
                incidents=incidents,
                staffing=staffing,
                residents=residents,
                tasks=tasks,
                escalation=escalation,
                sbar=sbar,
                print_safe=print_safe_value,
            )
            file_suffix = "condensed"
        else:
            pdf_bytes = pdf_build_detailed(
                logo_bytes=logo_bytes,
                org_name=st.session_state.get("org_name", ""),
                area=st.session_state.get("area", ""),
                shift=st.session_state.get("shift", "Day"),
                created_at=created_at,
                completed_by=st.session_state.get("completed_by", ""),
                reviewed_by=st.session_state.get("reviewed_by", ""),
                review_date=st.session_state.get("review_date", ""),
                incidents=incidents,
                staffing=staffing,
                residents=residents,
                tasks=tasks,
                escalation=escalation,
                sbar=sbar,
                print_safe=print_safe_value,
            )
            file_suffix = "detailed"

        safe_tag = "_printsafe" if print_safe_value else ""
        filename = f"handover_{file_suffix}{safe_tag}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )

        st.markdown(f"<div class='footerline'><b>Data:</b> {DATA_STATEMENT}</div>", unsafe_allow_html=True)
    else:
        st.info("Use demo/templates (sidebar) or fill the form, then click **Generate handover**.")
        st.markdown(f"<div class='footerline'><b>Data:</b> {DATA_STATEMENT}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown(
    f"<div class='footerline' style='text-align:center; margin-top:18px;'>"
    f"{APP_NAME} {APP_VERSION} • {DATA_STATEMENT} • Support: <b>{SUPPORT_EMAIL}</b>"
    f"</div>",
    unsafe_allow_html=True,
)

