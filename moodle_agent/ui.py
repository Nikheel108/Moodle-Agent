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

st.set_page_config(page_title="Moodle Agent Dashboard", page_icon="🎓", layout="wide")

st.title("🎓 Moodle Assignment Agent")
st.markdown(f"**Welcome, {STUDENT_NAME}!** Your personal AI assistant is active.")

db = TaskDatabase()
tasks = db.get_all_tasks()

# --- Helper logic for grouping ---
courses = {}
for t in tasks:
    if t.course_name not in courses:
        courses[t.course_name] = []
    courses[t.course_name].append(t)

# Calculate course next deadline
course_info = []
for c_name, c_tasks in courses.items():
    pending = [t for t in c_tasks if t.status != 'submitted']
    next_deadline = min([t.due_date for t in pending if t.due_date], default=None)
    course_info.append({
        "name": c_name,
        "tasks": c_tasks,
        "pending_count": len(pending),
        "next_deadline": next_deadline
    })
# Sort courses by next deadline
course_info.sort(key=lambda x: str(x["next_deadline"]) if x["next_deadline"] else "9999")

# Session state for navigation
if 'selected_course' not in st.session_state:
    st.session_state.selected_course = None

# --- Sidebar Summary ---
st.sidebar.header("📊 Overview")
st.sidebar.metric("Total Assignments", len(tasks))
st.sidebar.metric("Pending", sum(1 for t in tasks if t.status != 'submitted'))
st.sidebar.metric("Submitted", sum(1 for t in tasks if t.status == 'submitted'))

if st.sidebar.button("🔄 Sync Moodle Now"):
    with st.spinner("Fetching latest assignments..."):
        subprocess.run(["python", "-m", "moodle_agent.cli", "sync"], capture_output=True)
        st.toast("Sync complete!")
        st.rerun()

# --- Main Dashboard Tabs ---
tab1, tab2, tab3 = st.tabs(["🏠 Courses Dashboard", "⚡ Action Center (Review)", "📜 History & Logs"])

with tab1:
    if st.session_state.selected_course is None:
        st.subheader("Your Courses")
        if not course_info:
            st.info("No assignments found. Sync your Moodle account!")
            
        cols = st.columns(3)
        for i, c in enumerate(course_info):
            with cols[i % 3]:
                st.markdown(f"""
                <div style='padding:15px; border:1px solid #ddd; border-radius:10px; margin-bottom:15px; background-color:#2e2e2e;'>
                    <h4>{c['name']}</h4>
                    <p><b>Pending Tasks:</b> {c['pending_count']}</p>
                    <p><b>Next Deadline:</b> {c['next_deadline'] or 'None'}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View Tasks", key=f"view_{i}"):
                    st.session_state.selected_course = c['name']
                    st.rerun()
    else:
        st.subheader(f"Tasks for: {st.session_state.selected_course}")
        if st.button("⬅️ Back to Courses"):
            st.session_state.selected_course = None
            st.rerun()
            
        # Display Tasks in a table format using columns
        c_tasks = courses[st.session_state.selected_course]
        st.markdown("---")
        header1, header2, header3, header4, header5 = st.columns([3, 2, 1.5, 1.5, 1.5])
        header1.write("**Title**")
        header2.write("**Deadline**")
        header3.write("**Draft Ready?**")
        header4.write("**Submitted?**")
        header5.write("**Action / Download**")
        st.markdown("---")
        
        for t in c_tasks:
            col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1.5])
            col1.write(t.assignment_name)
            col2.write(str(t.due_date))
            
            has_draft = bool(t.draft_path and os.path.exists(t.draft_path))
            col3.write("✅ Yes" if has_draft else "❌ No")
            col4.write("✅ Yes" if t.status == 'submitted' else "❌ No")
            
            with col5:
                if t.status == 'submitted' and t.upload_package_path and os.path.exists(t.upload_package_path):
                    with open(t.upload_package_path, "rb") as pdf_file:
                        st.download_button("Download PDF", data=pdf_file, file_name=os.path.basename(t.upload_package_path), mime="application/pdf", key=f"dl_{t.id}")
                elif not has_draft and t.status != 'submitted':
                    if st.button("Generate", key=f"gen_{t.id}"):
                        with st.spinner("Generating..."):
                            subprocess.run(["python", "-m", "moodle_agent.cli", "generate", str(t.id), "--type", "draft"])
                            st.rerun()
                elif has_draft and t.status != 'submitted':
                    st.info("Check Action Center")

with tab2:
    st.subheader("Action Center (Urgent Reviews & Submissions)")
    # Sort unsubmitted tasks by due date
    urgent_tasks = sorted([t for t in tasks if t.status != 'submitted'], key=lambda x: str(x.due_date) if x.due_date else "9999")
    
    if not urgent_tasks:
        st.success("All caught up! No pending tasks.")
        
    for task in urgent_tasks:
        with st.expander(f"🚨 {task.assignment_name} (Due: {task.due_date})"):
            has_draft = bool(task.draft_path and os.path.exists(task.draft_path))
            if not has_draft:
                st.warning("Draft not generated yet.")
                if st.button("Generate Draft", key=f"urgent_gen_{task.id}"):
                    with st.spinner("Generating..."):
                        subprocess.run(["python", "-m", "moodle_agent.cli", "generate", str(task.id), "--type", "draft"])
                        st.rerun()
            else:
                with open(task.draft_path, 'r', encoding='utf-8') as f:
                    draft_content = f.read()
                
                st.markdown("#### Draft Preview")
                with st.container(height=300):
                    st.markdown(draft_content)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve & Export to PDF", key=f"urgent_app_{task.id}"):
                        safe_title = re.sub(r'[\\/*?:"<>|]', '-', task.assignment_name)
                        pdf_filename = f"{STUDENT_PRN}_{safe_title}.pdf"
                        pdf_dir = Path(task.draft_path).parent
                        pdf_path = str(pdf_dir / pdf_filename)
                        
                        if convert_md_to_pdf(draft_content, pdf_path):
                            st.success(f"PDF created: {pdf_filename}")
                            db.update_status(task.id, 'approved')
                            with sqlite3.connect(db.db_path) as conn:
                                conn.execute("UPDATE tasks SET upload_package_path = ? WHERE id = ?", (pdf_path, task.id))
                            st.rerun()
                
                with c2:
                    if task.status == 'approved':
                        if st.button("Auto-Submit to Moodle", key=f"urgent_sub_{task.id}"):
                            from moodle_agent.moodle_client import MoodleClient
                            with st.spinner("Uploading and submitting to Moodle..."):
                                pdf_path = db.get_task(task.id).upload_package_path
                                if pdf_path and os.path.exists(pdf_path):
                                    client = MoodleClient()
                                    item_id = client.upload_file(pdf_path)
                                    if item_id and client.submit_assignment_file(task.id, item_id):
                                        db.update_status(task.id, 'submitted')
                                        st.success("✅ Submitted!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to auto-submit.")
                                else:
                                    st.error("PDF not found.")

with tab3:
    st.subheader("📜 System Logs & History")
    submitted_tasks = [t for t in tasks if t.status == 'submitted']
    
    st.markdown("### Submission History")
    if not submitted_tasks:
        st.info("No submissions yet.")
    else:
        for t in submitted_tasks:
            st.success(f"✅ **{t.assignment_name}** - Submitted successfully for *{t.course_name}*")
            
    st.markdown("### Agent Activity Logs")
    log_path = Path(DATA_DIR) / "app.log"
    if log_path.exists():
        with open(log_path, 'r') as f:
            lines = f.readlines()
            # Show last 50 lines
            log_content = "".join(lines[-50:])
        st.code(log_content, language="text")
    else:
        st.info("No activity logs found yet.")
