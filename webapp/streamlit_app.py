import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "migrator"))
from suite_migrator import migrate_suite, extract_robot_files, classify_file

st.set_page_config(page_title="AI Suite Migrator", page_icon="🔄", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
h1 { font-family: 'Space Mono', monospace !important; }
.stButton > button {
    background: linear-gradient(135deg, #4f8fff, #7c3aed) !important;
    color: white !important; border: none !important;
    font-weight: 700 !important; font-size: 15px !important;
    padding: 14px !important; width: 100% !important;
}
.pipeline {
    display: flex; justify-content: center; align-items: center;
    gap: 10px; padding: 14px;
    background: rgba(79,143,255,0.05);
    border-radius: 10px; border: 1px solid rgba(79,143,255,0.15);
    margin: 12px 0 20px; flex-wrap: wrap;
    font-family: monospace; font-size: 12px; color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)

# Header
st.title("🔄 AI Suite Migrator")
st.markdown("Migrate your complete Robot Framework test suite to Playwright — file by file, automatically.")
st.markdown("""
<div class="pipeline">
    🤖 Robot Framework ZIP &nbsp;→&nbsp;
    🧠 AI Migration Engine &nbsp;→&nbsp;
    🎭 Playwright Project ZIP
</div>
""", unsafe_allow_html=True)
st.divider()

# Step 1 - Upload
st.markdown("### 📦 Step 1 — Upload Robot Framework Project ZIP")
st.caption("ZIP should contain your .robot files in any folder structure")

uploaded_zip = st.file_uploader("Upload project ZIP", type=["zip"])

if uploaded_zip:
    try:
        robot_files = extract_robot_files(uploaded_zip)
        uploaded_zip.seek(0)

        if robot_files:
            st.success(f"✅ Found **{len(robot_files)} .robot files**")

            types = {"test_suite": 0, "resource": 0, "variables": 0, "config": 0}
            for path, content in robot_files.items():
                t = classify_file(content)
                types[t] = types.get(t, 0) + 1

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🧪 Test Suites", types["test_suite"])
            c2.metric("📚 Resources",   types["resource"])
            c3.metric("📌 Variables",   types["variables"])
            c4.metric("⚙️ Config",      types["config"])

            with st.expander("📁 View detected files"):
                for path in sorted(robot_files.keys()):
                    ftype = classify_file(robot_files[path])
                    icons = {"test_suite": "🧪", "resource": "📚",
                             "variables": "📌", "config": "⚙️"}
                    st.markdown(f"{icons.get(ftype,'📄')} `{path}`")

            if len(robot_files) > 20:
                st.info(
                    f"⏱️ Large project detected ({len(robot_files)} files). "
                    "Migration will process in batches to avoid rate limits. "
                    f"Estimated time: **{len(robot_files) * 20 // 60 + 1}–{len(robot_files) * 30 // 60 + 1} minutes**."
                )
        else:
            st.error("No .robot files found in the ZIP.")
    except Exception as e:
        st.error(f"Error reading ZIP: {e}")

st.divider()

# Step 2 - Project name
st.markdown("### ✏️ Step 2 — Project Name")
project_name = st.text_input("Project name", placeholder="e.g. ECommerce Suite, Login Regression")

st.divider()

# Step 3 - Framework
st.markdown("### 🛠️ Step 3 — Choose Target Framework")

col1, col2 = st.columns(2)
with col1:
    if st.button("🐍 Playwright + Python", use_container_width=True):
        st.session_state["stack"] = "Playwright + Python"
with col2:
    if st.button("⚡ Playwright + JavaScript", use_container_width=True):
        st.session_state["stack"] = "Playwright + JavaScript"

stack = st.session_state.get("stack", "Playwright + Python")
st.info(f"Selected: **{stack}** — {'pytest + Page Objects → `.py` files' if 'Python' in stack else '@playwright/test + Page Objects → `.js` files'}")

st.divider()

# Step 4 - Migrate
st.markdown("### 🚀 Step 4 — Start Migration")

if st.button("🔄 Migrate Suite Now", use_container_width=True):

    if not uploaded_zip:
        st.error("⚠️ Please upload a ZIP file first.")
    else:
        name         = project_name.strip() or "migrated_suite"
        progress_bar = st.progress(0)
        status_text  = st.empty()
        log_area     = st.empty()
        log_lines    = []

        def on_progress(processed, total, original, migrated, status):
            progress_bar.progress(processed / total)
            icon = "✅" if status == "success" else "❌"
            status_text.markdown(f"⚙️ File **{processed}/{total}**: `{Path(original).name}`")
            log_lines.append(f"{icon} `{Path(original).name}` → `{migrated}`")
            log_area.markdown("\n".join(log_lines[-10:]))

        try:
            uploaded_zip.seek(0)
            zip_buffer, summary = migrate_suite(
                uploaded_zip,
                stack=stack,
                project_name=name,
                progress_callback=on_progress
            )

            progress_bar.progress(1.0)
            status_text.markdown("✅ **Migration complete!**")

            st.divider()
            st.markdown("### 📊 Migration Summary")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Files",  summary["total_files"])
            m2.metric("✅ Migrated",  summary["success_count"])
            m3.metric("❌ Failed",    summary["fail_count"])
            m4.metric("Framework",    stack.split(" + ")[1])

            if summary["fail_count"] > 0:
                st.warning(
                    f"⚠️ {summary['fail_count']} file(s) need manual review. "
                    "They are included in the ZIP with original content commented out."
                )

            st.success("🎉 Your migrated Playwright project is ready!")
            st.markdown(
                "**After downloading:**\n"
                "1. Extract the ZIP\n"
                "2. Install dependencies (see `README.md` inside)\n"
                "3. Update `BASE_URL` in the config file\n"
                "4. Review locators in the `pages/` folder\n"
                "5. Run the suite and fix any locator mismatches"
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name  = f"{name.replace(' ','_')}_{stack.split(' + ')[1].lower()}_{timestamp}.zip"

            st.download_button(
                label="⬇️ Download Migrated Project ZIP",
                data=zip_buffer,
                file_name=zip_name,
                mime="application/zip",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Migration failed: {str(e)}")

st.divider()
st.markdown(
    "<center><small style='color:#475569'>Built by "
    "<a href='https://github.com/naveen-erakam' style='color:#4f8fff'>Naveen Erakam</a>"
    " · AI Suite Migrator · Powered by Groq</small></center>",
    unsafe_allow_html=True
)
