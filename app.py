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

DATA_STATEMENT = "No data is stored. Refreshing the page clears the session."

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    layout="wide"
)

# =========================================================
# SAFE SESSION STATE INIT
# =========================================================
DEFAULTS = {
    "school_name": "",
    "log_date": date.today(),
    "day_type": "Normal day",
    "completed_by": "",
    "attendance": "",
    "behaviour": "",
    "safeguarding": "",
    "staffing": "",
    "site": "",
    "parents": "",
    "events": "",
    "actions": "",
    "priorities": "",
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# STYLING (UPDATED)
# =========================================================
st.markdown(
    """
<style>

/* App background */
.stApp {
    background-color: #f1f5f9;
}

/* Cards */
.card {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
}

/* ===== MAIN PAGE HEADING CONTRAST FIX ===== */
div[data-testid="stAppViewContainer"] h1,
div[data-testid="stAppViewContainer"] h2,
div[data-testid="stAppViewContainer"] h3 {
    color: #0f172a !important;
    font-weight: 700;
}

div[data-testid="stAppViewContainer"] h4 {
    color: #1e293b !important;
    font-weight: 600;
}

/* Text inputs (main page) */
div[data-testid="stAppViewContainer"] textarea,
div[data-testid="stAppViewContainer"] input,
div[data-testid="stAppViewContainer"] select {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0b1220;
}
section[data-testid="stSidebar"] * {
    color: #e5e7eb !important;
}
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select {
    background-color: #111827 !important;
    color: #f8fafc !important;
    border: 1px solid #334155 !important;
}

/* Buttons */
.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 12px;
    font-weight: 700;
}

.stDownloadButton>button {
    background-color: #0f172a;
    color: white;
    border-radius: 12px;
    font-weight: 700;
}

</style>
""",
    unsafe_allow_html=True
)

# =========================================================
# HEADER
# =========================================================
st.markdown(f"# {APP_NAME}")
st.markdown(
    "Create a clear daily operational overview for SLT in under **3 minutes**."
)
st.info(
    "⚠️ Do not include pupil-identifiable information. "
    "This tool does not store data or submissions."
)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.subheader("Document details")
    st.text_input("School name (optional)", key="school_name")
    st.date_input("Date", key="log_date")
    st.selectbox(
        "Day type",
        ["Normal day", "Trip day", "Exam day", "INSET", "Other"],
        key="day_type",
    )
    st.text_input("Completed by (optional)", key="completed_by")
    st.caption(DATA_STATEMENT)

# =========================================================
# MAIN LAYOUT
# =========================================================
left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Daily inputs")

    st.text_area("🕘 Attendance & punctuality", key="attendance", height=90)
    st.text_area("🧠 Behaviour & pastoral issues", key="behaviour", height=90)
    st.text_area("🛡️ Safeguarding activity (high level)", key="safeguarding", height=90)
    st.text_area("👥 Staffing & cover", key="staffing", height=90)
    st.text_area("🏫 Site & facilities", key="site", height=90)
    st.text_area("📞 Parent communications", key="parents", height=90)
    st.text_area("📅 Events / timetable notes", key="events", height=90)
    st.text_area("✅ Actions taken today", key="actions", height=90)
    st.text_area("🎯 Priorities for tomorrow", key="priorities", height=90)

    generate = st.button("Generate daily summary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Output")

    if not generate:
        st.info("Fill in the log and click **Generate daily summary**.")
    else:
        def lines(text):
            return [l.strip("-• ") for l in text.splitlines() if l.strip()]

        created = datetime.now().strftime("%d %b %Y %H:%M")

        st.markdown("### Daily Summary")
        st.markdown(
            f"""
**School:** {st.session_state.school_name or "—"}  
**Date:** {st.session_state.log_date.strftime('%d %b %Y')}  
**Completed by:** {st.session_state.completed_by or "—"}  
**Generated:** {created}
"""
        )

        def section(title, content):
            items = lines(content)
            if not items:
                st.markdown(f"**{title}:** None reported")
            else:
                st.markdown(f"**{title}:**")
                for i in items:
                    st.markdown(f"- {i}")

        section("Attendance", st.session_state.attendance)
        section("Behaviour", st.session_state.behaviour)
        section("Safeguarding", st.session_state.safeguarding)
        section("Staffing", st.session_state.staffing)
        section("Site", st.session_state.site)
        section("Parents", st.session_state.parents)
        section("Events", st.session_state.events)
        section("Actions taken", st.session_state.actions)
        section("Priorities", st.session_state.priorities)

        st.caption(DATA_STATEMENT)

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown(
    f"""
---
**{APP_NAME} {APP_VERSION}** • Support: {SUPPORT_EMAIL}  
{DATA_STATEMENT}
"""
)
