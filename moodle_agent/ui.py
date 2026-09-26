import streamlit as st
import time
from pathlib import Path
from datetime import datetime
import os
import subprocess
import re
import sqlite3

from moodle_agent.config import DATA_DIR, STUDENT_NAME, STUDENT_PRN
from moodle_agent.task_db import TaskDatabase
from moodle_agent.pdf_exporter import convert_md_to_pdf

st.set_page_config(page_title="Universal Agent Dashboard", page_icon="🤖", layout="wide")

db = TaskDatabase()
tasks = db.get_all_tasks()

# --- Utility Functions ---
def get_urgency_level(due_date):
    if not due_date: return "⚪ No Deadline"
    try:
        if isinstance(due_date, str):
            due_obj = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        else:
            due_obj = due_date
        days = (due_obj - datetime.now(due_obj.tzinfo)).total_seconds() / 86400
        if days < 0: return "🔴 Overdue"
        if days < 1: return "🔴 Critical (<24h)"
        if days < 3: return "🟠 Urgent (<3 days)"
        if days < 7: return "🟡 Upcoming (<1 week)"
        return "🟢 Relaxed"
    except:
        return "⚪ Unknown"

# --- Sidebar Controls (Notifications, Platform, Overrides) ---
st.sidebar.title("🤖 Agent Controls")

platform = st.sidebar.selectbox("🌐 Integration Platform", ["Moodle", "Canvas (Beta)", "Blackboard (Beta)"])
if platform != "Moodle":
    st.sidebar.warning(f"{platform} module is currently in beta.")

# Global Override Switch
agent_status = st.sidebar.toggle("🟢 Master Agent Switch (Active/Pause)", value=True)
if not agent_status:
    st.sidebar.error("Agent is currently PAUSED. No background tasks will run.")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Recent Notifications")
with st.sidebar.expander("View System Events", expanded=True):
    st.info("🔄 10 mins ago: Sync completed.")
    st.success("✅ 1 hour ago: DCGAN pdf uploaded.")
    st.warning("⚠️ 3 hours ago: Credential refresh needed soon.")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Trigger Manual Sync"):
    if agent_status:
        with st.spinner(f"Fetching assignments from {platform}..."):
            subprocess.run(["python", "-m", "moodle_agent.cli", "sync"], capture_output=True)
            st.toast("Sync complete!")
            st.rerun()
    else:
        st.sidebar.error("Enable Master Switch to sync.")

# --- Main Dashboard Tabs ---
st.title(f"🤖 Universal Assignment Agent - {platform}")
st.markdown(f"**User:** {STUDENT_NAME} | **PRN:** {STUDENT_PRN}")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Dashboard & Filters", 
    "📈 Workflow Tracking", 
    "⚡ Action Center", 
    "⚙️ Admin & Controls", 
    "📜 Diagnostics"
])

with tab1:
    st.subheader("Filter & Sort Assignments")
    colA, colB = st.columns(2)
    with colA:
        status_filter = st.multiselect("Filter by Status", ["pending", "approved", "submitted"], default=["pending", "approved", "submitted"])
    with colB:
        urgency_filter = st.selectbox("Priority Deadlines", ["All", "🔴 Critical (<24h)", "🟠 Urgent (<3 days)", "🟡 Upcoming (<1 week)", "🟢 Relaxed"])
    
    filtered_tasks = [t for t in tasks if t.status in status_filter]
    if urgency_filter != "All":
        filtered_tasks = [t for t in filtered_tasks if get_urgency_level(t.due_date) == urgency_filter]

    if not filtered_tasks:
        st.info("No tasks match the current filters.")

    cols = st.columns(3)
    for i, t in enumerate(filtered_tasks):
        with cols[i % 3]:
            urgency = get_urgency_level(t.due_date)
            st.markdown(f"""
            <div style='padding:15px; border:1px solid #444; border-radius:10px; margin-bottom:15px; background-color:#1e1e1e;'>
                <h5 style='margin:0; padding:0;'>{t.assignment_name}</h5>
                <p style='color:#bbb; font-size: 0.9em;'>{t.course_name}</p>
                <p><b>Priority:</b> {urgency}</p>
                <p><b>Status:</b> {t.status.upper()}</p>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("Workflow Stages & Progress")
    
    def get_progress(status):
        states = {'pending': 25, 'draft_ready': 50, 'approved': 75, 'submitted': 100}
        return states.get(status, 25)

    for t in [x for x in tasks if x.status != 'submitted']:
        st.markdown(f"**{t.assignment_name}** ({get_urgency_level(t.due_date)})")
        prog = get_progress(t.status)
        st.progress(prog)
        st.markdown(f"<small>Status: {'Scraped' if prog==25 else 'Drafting Complete' if prog==50 else 'Approved for Upload' if prog==75 else 'Done'}</small>", unsafe_allow_html=True)
        st.markdown("---")

with tab3:
    st.subheader("Action Center (Overrides & Manual Approval)")
    urgent_tasks = sorted([t for t in tasks if t.status != 'submitted'], key=lambda x: str(x.due_date) if x.due_date else "9999")
    
    for task in urgent_tasks:
        with st.expander(f"[{get_urgency_level(task.due_date)}] {task.assignment_name}"):
            has_draft = bool(task.draft_path and os.path.exists(task.draft_path))
            if not has_draft:
                st.warning("No draft found.")
                if st.button("Force Generate Draft", key=f"force_gen_{task.id}"):
                    if agent_status:
                        with st.spinner("Generating..."):
                            subprocess.run(["python", "-m", "moodle_agent.cli", "generate", str(task.id), "--type", "draft"])
                            st.rerun()
                    else:
                        st.error("Agent paused.")
            else:
                with open(task.draft_path, 'r', encoding='utf-8') as f:
                    draft_content = f.read()
                with st.container(height=300):
                    st.markdown(draft_content)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve & PDF", key=f"app_{task.id}"):
                        safe_title = re.sub(r'[\\/*?:"<>|]', '-', task.assignment_name)
                        pdf_path = str(Path(task.draft_path).parent / f"{STUDENT_PRN}_{safe_title}.pdf")
                        if convert_md_to_pdf(draft_content, pdf_path):
                            db.update_status(task.id, 'approved')
                            with sqlite3.connect(db.db_path) as conn:
                                conn.execute("UPDATE tasks SET upload_package_path = ? WHERE id = ?", (pdf_path, task.id))
                            st.success("PDF Exported!")
                            st.rerun()
                with c2:
                    if task.status == 'approved':
                        if st.button("Force Moodle Upload", key=f"upload_{task.id}"):
                            from moodle_agent.moodle_client import MoodleClient
                            pdf_path = db.get_task(task.id).upload_package_path
                            if pdf_path and os.path.exists(pdf_path):
                                client = MoodleClient()
                                item_id = client.upload_file(pdf_path)
                                if item_id and client.submit_assignment_file(task.id, item_id):
                                    db.update_status(task.id, 'submitted')
                                    st.success("Uploaded!")
                                    st.rerun()
                            else:
                                st.error("PDF missing.")

with tab4:
    st.subheader("Admin Control Panel")
    st.write("Manage secure credentials and define automation scope.")
    
    st.markdown("#### Automation Scope")
    auto_draft = st.toggle("Auto-Generate Drafts on Sync", value=True)
    auto_submit = st.toggle("Auto-Submit Assignments (Dangerous)", value=False)
    if auto_submit:
        st.warning("⚠️ Full Automation enabled. The agent will submit without manual review!")
    
    st.markdown("#### Security & Credentials")
    st.info("Credentials are securely locked in the Windows Credential Manager.")
    if st.button("Clear Saved Credentials"):
        import keyring
        keyring.delete_password("moodle_agent", "username")
        keyring.delete_password("moodle_agent", "password")
        st.success("Credentials cleared. Agent will request them on next sync.")

with tab5:
    st.subheader("System Logs & Diagnostics")
    log_path = Path(DATA_DIR) / "app.log"
    if log_path.exists():
        with open(log_path, 'r') as f:
            log_content = "".join(f.readlines()[-100:])
        st.code(log_content, language="text")
    else:
        st.info("No system logs found.")
