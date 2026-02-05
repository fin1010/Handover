import streamlit as st
from datetime import datetime, date
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
APP_NAME = "School Daily Operations Log"
APP_VERSION = "v1.0"
SUPPORT_EMAIL = "finlayajayi@rocketmail.com"

VALUE_PROP = "Create a clear daily overview for SLT in under 3 minutes."
BADGE_TEXT = "No data stored • PDF export • Print-safe mode"

PRIVACY_BANNER = (
    "⚠️ Do not include pupil-identifiable information. "
    "This tool does not store submissions."
)

NOT_A_RECORD = (
    "This is a daily operational summary tool only. "
    "It does not replace safeguarding systems, behaviour systems, or your MIS."
)

DATA_STATEMENT = "No data is stored. Refreshing the page clears the session."
FEEDBACK_LINE = "Feedback welcome — it helps shape future updates."

# =========================================================
# BRAND / COLOURS
# =========================================================
BRAND_DARK = colors.HexColor("#0f172a")
BRAND_ACCENT = colors.HexColor("#2563eb")
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#475569")
BORDER = colors.HexColor("#CBD5E1")
BG_SOFT = colors.HexColor("#F1F5F9")

# =========================================================
# PAGE CONFIG (ONLY ONCE)
# =========================================================
st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", layout="wide")

# =========================================================
# HELPERS
# =========================================================
def now_str() -> str:
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


def safe_value(value: str, print_safe: bool) -> str:
    return "" if print_safe else (value.strip() if value else "")


# =========================================================
# ACCESS CODE GATE (Suggestions 1–2)
# - secrets.toml:
#   DEMO_CODE = "SCHOOL-DEMO"
#   PAID_CODES = ["GREENFIELD-OPS", "STMARY-DAILY"]
#
# - Tracks mode in session_state: "demo" or "paid"
# =========================================================
def check_access():
    demo_code = st.secrets.get("DEMO_CODE", None)
    paid_codes = st.secrets.get("PAID_CODES", [])

    if "access_granted" not in st.session_state:
        st.session_state.access_granted = False
        st.session_state.access_mode = None  # "demo" | "paid" | "unlocked"

    # If no codes configured, don't lock you out during development
    if not demo_code and (not paid_codes or len(paid_codes) == 0):
        st.session_state.access_granted = True
        st.session_state.access_mode = "unlocked"
        st.warning(
            "DEMO_CODE / PAID_CODES are not set in Streamlit secrets. "
            "The app is currently unlocked. Set these before selling."
        )
        return

    if st.session_state.access_granted:
        return

    st.markdown("## 🔒 Access Required")
    st.markdown("Enter your access code to use this tool.")
    code = st.text_input("Access code", type="password")

    if st.button("Unlock", use_container_width=True):
        if demo_code and code == demo_code:
            st.session_state.access_granted = True
            st.session_state.access_mode = "demo"
            st.rerun()
        elif code in paid_codes:
            st.session_state.access_granted = True
            st.session_state.access_mode = "paid"
            st.rerun()
        else:
            st.error("Invalid access code")

    st.caption(f"Support: {SUPPORT_EMAIL}")
    st.stop()


# =========================================================
# SAFE STATE ACTIONS (clear/demo)
# =========================================================
DEFAULTS = {
    "school_name": "",
    "log_date": date.today(),
    "day_type": "Normal day",
    "completed_by": "",
    "print_safe": False,
    "pdf_style": "Detailed (multi-page)",
    "attendance": "",
    "behaviour": "",
    "safeguarding": "",
    "staffing": "",
    "site": "",
    "parents": "",
    "events": "",
    "actions_taken": "",
    "priorities": "",
}

DEMO = {
    "school_name": "Example Primary School",
    "log_date": date.today(),
    "day_type": "Normal day",
    "completed_by": "Office Manager",
    "print_safe": False,
    "pdf_style": "Detailed (multi-page)",
    "attendance": "Higher absence in Year 2 due to sickness\nSeveral late arrivals linked to transport delays",
    "behaviour": "Lunchtime disruption in playground; pastoral lead aware\nOne serious incident escalated to SLT (details recorded in school system)",
    "safeguarding": "Safeguarding concern raised and passed to DSL\nFollow-up action ongoing (details in safeguarding system)",
    "staffing": "Supply arranged for Year 5 afternoon\nTA absence impacted intervention group",
    "site": "Heating issue in Block B; site manager contacted\nPlayground gate checked and secured",
    "parents": "Several calls re transport delays\nOne complaint escalated to Deputy Head",
    "events": "Year 6 trip tomorrow; staffing confirmed\nAssembly schedule adjusted due to rehearsal",
    "actions_taken": "Cover arranged; SLT briefed on serious incident; site issue reported; parent complaint acknowledged",
    "priorities": "Monitor absence in Year 2\nConfirm heating repair time\nReview lunchtime supervision plan",
}


def request_clear():
    st.session_state["_do_clear"] = True


def request_demo():
    st.session_state["_do_demo"] = True


def apply_actions():
    # Initialize defaults once (before any widgets)
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Apply clear/demo before widgets render
    if st.session_state.get("_do_clear"):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.session_state["_do_clear"] = False

    if st.session_state.get("_do_demo"):
        for k, v in DEMO.items():
            st.session_state[k] = v
        st.session_state["_do_demo"] = False


# =========================================================
# OUTPUT BUILDERS
# =========================================================
def build_daily_summary_md(
    *,
    school_name: str,
    log_date: date,
    day_type: str,
    completed_by: str,
    created_at: str,
    print_safe: bool,
    sections: dict
) -> str:
    def section(title: str, body: str) -> str:
        items = clean_lines(body)
        if not items:
            return f"**{title}:** None reported.\n"
        bullets = "\n".join([f"- {x}" for x in items])
        return f"**{title}:**\n{bullets}\n"

    school_display = "" if print_safe else (school_name.strip() or "—")
    completed_display = "" if print_safe else (completed_by.strip() or "—")

    header = (
        f"### Daily Operations Summary\n"
        f"**School:** {school_display or '(hidden – print-safe)'}  \n"
        f"**Date:** {log_date.strftime('%d %b %Y')}  \n"
        f"**Day type:** {day_type}  \n"
        f"**Generated:** {created_at}  \n"
        f"**Completed by:** {completed_display or '(hidden – print-safe)'}\n"
        f"\n---\n"
    )

    body = ""
    body += section("Attendance & punctuality", sections["attendance"])
    body += "\n" + section("Behaviour & pastoral issues", sections["behaviour"])
    body += "\n" + section("Safeguarding activity (high-level only)", sections["safeguarding"])
    body += "\n" + section("Staffing & cover", sections["staffing"])
    body += "\n" + section("Site & facilities", sections["site"])
    body += "\n" + section("Parent communications", sections["parents"])
    body += "\n" + section("Events / timetable notes", sections["events"])
    body += "\n" + section("Actions taken today", sections["actions_taken"])
    body += "\n" + section("Priorities for tomorrow", sections["priorities"])

    footer = (
        "\n---\n"
        f"**Data:** {DATA_STATEMENT}\n\n"
        f"*{NOT_A_RECORD}*\n"
    )

    return header + body + footer


def build_slt_oneliner(sections: dict) -> str:
    return (
        "Today: "
        f"attendance {pick_items(sections['attendance'], 1)}, "
        f"behaviour {pick_items(sections['behaviour'], 1)}, "
        f"safeguarding {pick_items(sections['safeguarding'], 1)}, "
        f"cover {pick_items(sections['staffing'], 1)}, "
        f"site {pick_items(sections['site'], 1)}; "
        f"priority tomorrow: {pick_items(sections['priorities'], 1)}."
    )


# =========================================================
# PDF HELPERS
# =========================================================
def _draw_logo(c, logo_bytes: bytes | None, x: float, y: float, max_w: float, max_h: float):
    if not logo_bytes:
        return
    try:
        img = ImageReader(io.BytesIO(logo_bytes))
        iw, ih = img.getSize()
        scale = min(max_w / iw, max_h / ih)
        w, h = iw * scale, ih * scale
        c.drawImage(img, x, y - h, width=w, height=h, mask="auto")
    except Exception:
        return


def pdf_detailed(
    *,
    logo_bytes: bytes | None,
    school_name: str,
    log_date: date,
    day_type: str,
    completed_by: str,
    created_at: str,
    print_safe: bool,
    sections: dict,
    oneliner: str
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin_x = 16 * mm
    margin_top = 16 * mm
    margin_bottom = 16 * mm
    content_w = width - 2 * margin_x
    y = height - margin_top
    page = 1

    school_pdf = safe_value(school_name, print_safe) or ("(hidden – print-safe)" if print_safe else "—")
    completed_pdf = safe_value(completed_by, print_safe) or ("(hidden – print-safe)" if print_safe else "—")

    def footer():
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.line(margin_x, margin_bottom + 12 * mm, width - margin_x, margin_bottom + 12 * mm)

        c.setFont("Helvetica", 8.7)
        c.setFillColor(TEXT_MUTED)
        c.drawString(margin_x, margin_bottom + 6 * mm, f"Generated: {created_at}")
        c.drawRightString(width - margin_x, margin_bottom + 6 * mm, f"Page {page}")

        c.setFont("Helvetica", 8.2)
        c.drawString(margin_x, margin_bottom + 2.5 * mm, f"{APP_NAME} {APP_VERSION} • Support: {SUPPORT_EMAIL}")

    def new_page():
        nonlocal y, page
        footer()
        c.showPage()
        page += 1
        y = height - margin_top
        draw_header(compact=True)

    def draw_header(compact: bool = False):
        nonlocal y
        if not compact:
            bar_h = 18 * mm
            c.setFillColor(BRAND_DARK)
            c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
            _draw_logo(c, logo_bytes, margin_x, height - 3 * mm, 24 * mm, 12 * mm)

            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin_x + (28 * mm if logo_bytes else 0), height - 12.5 * mm, "Daily Operations Log")
            c.setFont("Helvetica", 10)
            c.drawRightString(width - margin_x, height - 12.2 * mm, school_pdf)
            y = height - bar_h - 8 * mm
        else:
            c.setFillColor(BG_SOFT)
            c.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin_x, height - 7 * mm, "Daily Operations Log")
            c.setFont("Helvetica", 9)
            c.setFillColor(TEXT_MUTED)
            c.drawRightString(width - margin_x, height - 7 * mm, f"{log_date.strftime('%d %b %Y')} • {day_type}")
            y = height - 10 * mm - 10 * mm

    def ensure(space_mm: float):
        nonlocal y
        if y - space_mm < margin_bottom + 20 * mm:
            new_page()

    def draw_meta():
        nonlocal y
        ensure(30 * mm)
        c.setFont("Helvetica", 10)
        c.setFillColor(TEXT_DARK)
        c.drawString(margin_x, y, f"Date: {log_date.strftime('%d %b %Y')}")
        c.drawString(margin_x + 70 * mm, y, f"Day type: {day_type}")
        y -= 6 * mm
        c.drawString(margin_x, y, f"Completed by: {completed_pdf}")
        y -= 10 * mm

        # Banner note
        c.setFillColor(colors.HexColor("#fff7ed"))
        c.setStrokeColor(colors.HexColor("#fed7aa"))
        c.roundRect(margin_x, y - 12 * mm, content_w, 12 * mm, 6, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(margin_x + 6 * mm, y - 7.8 * mm, "Privacy:")
        c.setFont("Helvetica", 9.5)
        c.drawString(margin_x + 24 * mm, y - 7.8 * mm, "Do not include pupil-identifiable information.")
        y -= 18 * mm

    def draw_section(title: str, body: str):
        nonlocal y
        items = clean_lines(body)
        wrap_width = 96
        lines = []

        if not items:
            lines = ["• None reported."]
        else:
            for it in items:
                wrapped = textwrap.wrap(it, width=wrap_width, break_long_words=False, break_on_hyphens=False)
                lines.append("• " + wrapped[0])
                for cont in wrapped[1:]:
                    lines.append("   " + cont)

        required = (10 + 8 + len(lines) * 5.2 + 16) * mm
        ensure(required)

        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(TEXT_DARK)
        c.drawString(margin_x, y, title)
        y -= 6 * mm

        card_h = (6 + len(lines) * 5.2 + 6) * mm
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.roundRect(margin_x, y - card_h, content_w, card_h, 6, fill=1, stroke=1)

        tx = margin_x + 6 * mm
        ty = y - 6 * mm
        c.setFont("Helvetica", 10.2)
        c.setFillColor(TEXT_DARK)
        for ln in lines:
            ty -= 5.2 * mm
            c.drawString(tx, ty, ln)

        y -= (card_h + 8 * mm)

    draw_header(compact=False)
    draw_meta()

    order = [
        ("Attendance & punctuality", "attendance"),
        ("Behaviour & pastoral issues", "behaviour"),
        ("Safeguarding activity (high-level only)", "safeguarding"),
        ("Staffing & cover", "staffing"),
        ("Site & facilities", "site"),
        ("Parent communications", "parents"),
        ("Events / timetable notes", "events"),
        ("Actions taken today", "actions_taken"),
        ("Priorities for tomorrow", "priorities"),
        ("SLT one-liner", None),
    ]

    for title, key in order:
        if key:
            draw_section(title, sections[key])
        else:
            draw_section(title, oneliner)

    footer()
    c.save()
    return buf.getvalue()


def pdf_one_page(
    *,
    logo_bytes: bytes | None,
    school_name: str,
    log_date: date,
    day_type: str,
    completed_by: str,
    created_at: str,
    print_safe: bool,
    sections: dict,
    oneliner: str
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin_x = 14 * mm
    margin_bottom = 14 * mm
    content_w = width - 2 * margin_x

    school_pdf = safe_value(school_name, print_safe) or ("(hidden – print-safe)" if print_safe else "—")
    completed_pdf = safe_value(completed_by, print_safe) or ("(hidden – print-safe)" if print_safe else "—")

    # Header
    bar_h = 16 * mm
    c.setFillColor(BRAND_DARK)
    c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
    _draw_logo(c, logo_bytes, margin_x, height - 3 * mm, 22 * mm, 12 * mm)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(margin_x + (26 * mm if logo_bytes else 0), height - 11.2 * mm, "Daily Operations Log (Condensed)")
    c.setFont("Helvetica", 9.5)
    c.drawRightString(width - margin_x, height - 11.0 * mm, school_pdf)

    y = height - bar_h - 10 * mm

    # Meta strip
    c.setFillColor(BG_SOFT)
    c.rect(margin_x, y - 10 * mm, content_w, 10 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_x + 4 * mm, y - 6.6 * mm, f"Date: {log_date.strftime('%d %b %Y')}")
    c.drawString(margin_x + 62 * mm, y - 6.6 * mm, f"Type: {day_type}")
    c.setFont("Helvetica", 9)
    c.setFillColor(TEXT_MUTED)
    c.drawRightString(width - margin_x - 4 * mm, y - 6.6 * mm, f"By: {completed_pdf}")
    y -= 14 * mm

    def block(title: str, text: str, max_lines: int = 2):
        nonlocal y
        items = clean_lines(text)
        wrap_w = 100
        lines = []
        if not items:
            lines = ["- None."]
        else:
            for it in items:
                wrapped = textwrap.wrap(it, width=wrap_w, break_long_words=False, break_on_hyphens=False)
                lines.append("- " + wrapped[0])
                for cont in wrapped[1:]:
                    lines.append("  " + cont)
        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["(more in app)"]

        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 10.0)
        c.drawString(margin_x, y, title)
        y -= 4.6 * mm

        h = (len(lines) * 4.2 * mm) + 7 * mm
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.roundRect(margin_x, y - h, content_w, h, 6, fill=1, stroke=1)

        c.setFont("Helvetica", 9.2)
        c.setFillColor(TEXT_DARK)
        ty = y - 5.4 * mm
        for ln in lines:
            c.drawString(margin_x + 6 * mm, ty, ln)
            ty -= 4.2 * mm

        y -= (h + 5.0 * mm)

    # Blocks (plain titles, no emojis)
    block("Attendance", sections["attendance"])
    block("Behaviour", sections["behaviour"])
    block("Safeguarding (high-level)", sections["safeguarding"])
    block("Staffing/Cover", sections["staffing"])
    block("Site/Facilities", sections["site"])
    block("Parents", sections["parents"])
    block("Events", sections["events"])
    block("Actions taken", sections["actions_taken"])
    block("Priorities tomorrow", sections["priorities"])
    block("SLT one-liner", oneliner)

    # Footer
    c.setStrokeColor(BORDER)
    c.line(margin_x, margin_bottom + 11 * mm, width - margin_x, margin_bottom + 11 * mm)
    c.setFont("Helvetica", 8.6)
    c.setFillColor(TEXT_MUTED)
    c.drawString(margin_x, margin_bottom + 6 * mm, f"Generated: {created_at}")
    c.setFont("Helvetica", 8.1)
    c.drawString(margin_x, margin_bottom + 2.5 * mm, f"{APP_NAME} {APP_VERSION} • Support: {SUPPORT_EMAIL}")

    c.showPage()
    c.save()
    return buf.getvalue()


# =========================================================
# STREAMLIT APP
# =========================================================

# Apply clear/demo BEFORE widgets render
apply_actions()

# Access gate
check_access()

# Styles  ✅ ADDED: DARK HEADINGS INSIDE WHITE CARDS (.card)
st.markdown(
    f"""
<style>
.stApp {{
  background: {BG_SOFT.hexval()};
}}

.card {{
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 8px 22px rgba(15,23,42,0.08);
  margin-bottom: 16px;
}}

/* ===== FIX: MAKE ALL HEADINGS INSIDE WHITE BOXES DARK ===== */
.card h1, .card h2, .card h3, .card h4, .card h5, .card h6 {{
  color: #020617 !important;   /* slate-950 */
  font-weight: 800 !important;
}}
/* Some Streamlit versions wrap headings inside markdown containers */
.card [data-testid="stMarkdownContainer"] h1,
.card [data-testid="stMarkdownContainer"] h2,
.card [data-testid="stMarkdownContainer"] h3,
.card [data-testid="stMarkdownContainer"] h4,
.card [data-testid="stMarkdownContainer"] h5,
.card [data-testid="stMarkdownContainer"] h6 {{
  color: #020617 !important;
  font-weight: 800 !important;
}}

.subtle {{
  color: #334155;
  font-size: 0.98rem;
}}

.badge {{
  display:inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #0f172a;
  font-size: 0.85rem;
}}

.banner {{
  border: 1px solid #fed7aa;
  background: #fff7ed;
  border-radius: 12px;
  padding: 10px 12px;
  margin: 10px 0 12px 0;
}}

.kv {{
  border: 1px solid #cbd5e1;
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 14px;
  margin: 12px 0;
}}

.footerline {{
  color: #64748b;
  font-size: 0.9rem;
  margin-top: 18px;
}}

.stButton>button {{
  background: {BRAND_ACCENT.hexval()};
  color: white;
  border: 0;
  border-radius: 12px;
  padding: 0.65rem 1rem;
  font-weight: 800;
}}

.stDownloadButton>button {{
  background: {BRAND_DARK.hexval()};
  color: white;
  border: 0;
  border-radius: 12px;
  padding: 0.65rem 1rem;
  font-weight: 800;
}}

section[data-testid="stSidebar"] {{
  background: #0b1220;
  border-right: 1px solid #111827;
}}
section[data-testid="stSidebar"] * {{
  color: #e5e7eb !important;
}}

div[data-testid="stAppViewContainer"] input,
div[data-testid="stAppViewContainer"] textarea,
div[data-testid="stAppViewContainer"] select {{
  background-color: #ffffff !important;
  color: #0f172a !important;
  border: 1px solid #cbd5e1 !important;
  border-radius: 10px !important;
}}

section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] select {{
  background-color: #111827 !important;
  color: #f8fafc !important;
  border: 1px solid #334155 !important;
  border-radius: 10px !important;
}}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {{
  color: #cbd5e1 !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

# HEADER + TRUST LAYER
st.markdown(f"# {APP_NAME} — {APP_VERSION}")
st.markdown(f"<div class='subtle'>{VALUE_PROP}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='badge'>🛡️ {BADGE_TEXT}</div>", unsafe_allow_html=True)

# Demo mode banner at top
if st.session_state.get("access_mode") == "demo":
    st.warning(
        f"🔎 Demo mode — for evaluation use only. Contact {SUPPORT_EMAIL} to continue long-term use.",
        icon="ℹ️",
    )

st.markdown(
    f"<div class='banner'><b>{PRIVACY_BANNER}</b><br>"
    f"<span class='subtle'>{NOT_A_RECORD}</span><br>"
    f"<span class='subtle'><b>⏱️ Typically takes 2–3 minutes.</b> • {DATA_STATEMENT}</span></div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="kv">
<b>Who this is for</b><br>
<span class="subtle">Office managers, duty leads, and senior leaders who need a quick daily overview to brief SLT.</span><br><br>
<b>Who this is not for</b><br>
<span class="subtle">Not a safeguarding record, behaviour system, or MIS replacement. Use your existing school systems for names and case details.</span>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="kv">
<b>What you get</b><br>
<ul style="margin-top:6px; color:#334155;">
  <li>A clear daily summary for SLT</li>
  <li>A one-line briefing sentence</li>
  <li>A printable PDF for records/inspection readiness</li>
</ul>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("How to use (1 minute)"):
    st.markdown(
        f"""
1) One person completes the log (usually office/duty lead/SLT).
2) Add **high-level notes** only — one item per line.
3) Click **Generate daily summary** to produce the summary + SLT one-liner + PDF.
4) {DATA_STATEMENT}

**Privacy reminder:** Do not include pupil-identifiable information.
"""
    )

st.markdown(f"📧 Questions or feedback? Email **{SUPPORT_EMAIL}**  \n_{FEEDBACK_LINE}_")

# SIDEBAR
with st.sidebar:
    st.subheader("Document settings")

    logo_file = st.file_uploader("Logo for PDF (optional)", type=["png", "jpg", "jpeg"])
    logo_bytes = logo_file.getvalue() if logo_file else None

    st.text_input("School name (optional)", key="school_name")
    st.date_input("Log date", key="log_date")
    st.selectbox("Day type", ["Normal day", "Exam day", "Trip day", "INSET", "Other"], key="day_type")
    st.text_input("Completed by (optional)", key="completed_by")

    st.divider()
    st.toggle(
        "Print-safe mode (hide school & staff names)",
        key="print_safe",
        help="Hides school name and staff name fields in outputs. Does NOT auto-redact free text.",
    )

    st.radio("PDF style", ["Detailed (multi-page)", "One-page (condensed)"], key="pdf_style", index=0)

    st.divider()
    st.subheader("Quick actions")
    if st.button("Load demo data", use_container_width=True):
        request_demo()
        st.rerun()

    if st.button("Clear form", use_container_width=True):
        request_clear()
        st.rerun()

    st.caption(f"🛡️ {DATA_STATEMENT}")

# MAIN LAYOUT
left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Daily inputs")

    st.text_area("🕘 Attendance & punctuality", key="attendance", height=105, placeholder="One item per line…")
    st.text_area("🧠 Behaviour & pastoral issues", key="behaviour", height=105, placeholder="One item per line…")
    st.text_area("🛡️ Safeguarding activity (high-level only)", key="safeguarding", height=105, placeholder="High-level only. No names…")
    st.text_area("👥 Staffing & cover", key="staffing", height=105, placeholder="One item per line…")
    st.text_area("🏫 Site & facilities", key="site", height=105, placeholder="One item per line…")
    st.text_area("📞 Parent communications", key="parents", height=105, placeholder="One item per line…")
    st.text_area("📅 Events / timetable notes", key="events", height=105, placeholder="One item per line…")
    st.text_area("✅ Actions taken today", key="actions_taken", height=105, placeholder="What was done today…")
    st.text_area("🎯 Priorities for tomorrow", key="priorities", height=105, placeholder="Top priorities for tomorrow…")

    generate = st.button("Generate daily summary", use_container_width=True)

    st.markdown(
        f"<div class='footerline'><b>Data:</b> {DATA_STATEMENT}<br>"
        f"<b>Support:</b> {SUPPORT_EMAIL}</div>",
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Output")

    if not generate:
        st.info("Fill the daily inputs and click **Generate daily summary**.")
        st.caption(f"🛡️ {DATA_STATEMENT}")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        created_at = now_str()
        print_safe = st.session_state.get("print_safe", False)

        sections = {
            "attendance": st.session_state.get("attendance", ""),
            "behaviour": st.session_state.get("behaviour", ""),
            "safeguarding": st.session_state.get("safeguarding", ""),
            "staffing": st.session_state.get("staffing", ""),
            "site": st.session_state.get("site", ""),
            "parents": st.session_state.get("parents", ""),
            "events": st.session_state.get("events", ""),
            "actions_taken": st.session_state.get("actions_taken", ""),
            "priorities": st.session_state.get("priorities", ""),
        }

        oneliner = build_slt_oneliner(sections)

        summary_md = build_daily_summary_md(
            school_name=st.session_state.get("school_name", ""),
            log_date=st.session_state.get("log_date", date.today()),
            day_type=st.session_state.get("day_type", "Normal day"),
            completed_by=st.session_state.get("completed_by", ""),
            created_at=created_at,
            print_safe=print_safe,
            sections=sections,
        )

        tab1, tab2, tab3 = st.tabs(["Daily Summary", "SLT One-liner", "PDF Export"])

        with tab1:
            st.markdown(summary_md)

        with tab2:
            st.code(oneliner, language="text")
            st.caption("Tip: paste this into an SLT update message or daily briefing.")

        with tab3:
            if st.session_state.get("pdf_style", "Detailed (multi-page)").startswith("One-page"):
                pdf_bytes = pdf_one_page(
                    logo_bytes=logo_bytes,
                    school_name=st.session_state.get("school_name", ""),
                    log_date=st.session_state.get("log_date", date.today()),
                    day_type=st.session_state.get("day_type", "Normal day"),
                    completed_by=st.session_state.get("completed_by", ""),
                    created_at=created_at,
                    print_safe=print_safe,
                    sections=sections,
                    oneliner=oneliner,
                )
                fname = f"school_daily_log_{st.session_state.get('log_date', date.today()).isoformat()}_condensed.pdf"
            else:
                pdf_bytes = pdf_detailed(
                    logo_bytes=logo_bytes,
                    school_name=st.session_state.get("school_name", ""),
                    log_date=st.session_state.get("log_date", date.today()),
                    day_type=st.session_state.get("day_type", "Normal day"),
                    completed_by=st.session_state.get("completed_by", ""),
                    created_at=created_at,
                    print_safe=print_safe,
                    sections=sections,
                    oneliner=oneliner,
                )
                fname = f"school_daily_log_{st.session_state.get('log_date', date.today()).isoformat()}.pdf"

            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )

            st.caption(f"🛡️ {DATA_STATEMENT}")

        st.markdown("</div>", unsafe_allow_html=True)

# Demo reminder in footer (only in demo mode)
if st.session_state.get("access_mode") == "demo":
    st.caption(f"Demo access • {DATA_STATEMENT} • Contact {SUPPORT_EMAIL} to continue.")

# APP FOOTER
st.markdown(
    f"<div class='footerline'>"
    f"<b>{APP_NAME} {APP_VERSION}</b> • Support: {SUPPORT_EMAIL} • {DATA_STATEMENT}<br>"
    f"{FEEDBACK_LINE}"
    f"</div>",
    unsafe_allow_html=True,
)
