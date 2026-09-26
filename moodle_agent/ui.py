import streamlit as st
import time
from pathlib import Path
from datetime import datetime
import os
import subprocess
import re
import sqlite3

from moodle_agent.config import DATA_DIR, STUDENT_NAME, STUDENT_PRN
from moodle_agent.task_db import TaskDatabase, TaskStatus
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
    "📜 History & Logs"
])

with tab1:
    st.subheader("Filter & Sort Assignments")
    colA, colB = st.columns(2)
    with colA:
        all_statuses = ["pending", "in_progress", "draft_ready", "awaiting_review", "approved", "submitted", "overdue"]
        status_filter = st.multiselect(
            "Filter by Status", 
            all_statuses, 
            default=["pending", "in_progress", "draft_ready", "awaiting_review", "approved", "overdue"]
        )
    with colB:
        urgency_filter = st.selectbox("Priority Deadlines", ["All", "🔴 Critical (<24h)", "🟠 Urgent (<3 days)", "🟡 Upcoming (<1 week)", "🟢 Relaxed"])
    
    filtered_tasks = [t for t in tasks if t.status in status_filter]
    if urgency_filter != "All":
        filtered_tasks = [t for t in filtered_tasks if get_urgency_level(t.due_date) == urgency_filter]

    if not filtered_tasks:
        st.info("No tasks match the current filters.")
    
    # Re-group by course
    display_courses = {}
    for t in filtered_tasks:
        if t.course_name not in display_courses:
            display_courses[t.course_name] = []
        display_courses[t.course_name].append(t)
        
    display_course_info = []
    for c_name, c_tasks in display_courses.items():
        pending_c = [t for t in c_tasks if t.status != 'submitted']
        next_dead = min([t.due_date for t in pending_c if t.due_date], default=None)
        display_course_info.append({
            "name": c_name,
            "tasks": c_tasks,
            "pending_count": len(pending_c),
            "next_deadline": next_dead
        })
    display_course_info.sort(key=lambda x: str(x["next_deadline"]) if x["next_deadline"] else "9999")
    
    if st.session_state.get('selected_course') not in display_courses:
        st.session_state.selected_course = None

    if st.session_state.selected_course is None:
        st.subheader("Your Courses")
        cols = st.columns(3)
        for i, c in enumerate(display_course_info):
            with cols[i % 3]:
                st.markdown(f"""
                <div style='padding:15px; border:1px solid #ddd; border-radius:10px; margin-bottom:15px; background-color:#2e2e2e;'>
                    <h4>{c['name']}</h4>
                    <p><b>Matching Tasks:</b> {len(c['tasks'])}</p>
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
            
        c_tasks = display_courses[st.session_state.selected_course]
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

# --- CSS Injections for Tabs, Cards, and Floating Notifications ---
st.markdown("""
<style>
/* Enhance Tab Navigation with accents */
[data-baseweb="tab-list"] {
    gap: 24px;
}
[data-baseweb="tab"] {
    height: 50px;
    white-space: pre-wrap;
    background-color: transparent;
    border-radius: 4px 4px 0px 0px;
    padding-top: 10px;
    padding-bottom: 10px;
}
[data-baseweb="tab"][aria-selected="true"] {
    background-color: #2b2b36;
    border-bottom: 3px solid #6366f1;
    color: #ffffff;
    font-weight: 600;
}

/* Floating Notification Panel */
.floating-notif {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background-color: #1e1e24;
    border-left: 4px solid #3b82f6;
    color: #e2e8f0;
    padding: 15px 20px;
    border-radius: 8px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    z-index: 9999;
    font-size: 0.9em;
    animation: slideIn 0.5s ease-out;
}
@keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
}
</style>
<div class='floating-notif'>
    🔔 <b>Agent Active:</b> Ready to draft, approve, and submit assignments.
</div>
""", unsafe_allow_html=True)

with tab3:
    st.subheader("Action Center")
    st.markdown("Review generated drafts, override system locks, and finalize submissions.")
    
    urgent_tasks = sorted([t for t in tasks if t.status != 'submitted'], key=lambda x: str(x.due_date) if x.due_date else "9999")
    
    def get_time_remaining(due_date_str):
        if not due_date_str: return "No deadline"
        try:
            due_obj = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
            delta = due_obj - datetime.now(due_obj.tzinfo)
            total_seconds = int(delta.total_seconds())
            if total_seconds < 0:
                return f"Overdue by {abs(total_seconds)//86400}d {(abs(total_seconds)//3600)%24}h"
            days = total_seconds // 86400
            hours = (total_seconds // 3600) % 24
            return f"{days}d {hours}h remaining"
        except:
            return "Unknown"

    def get_urgency_color(urgency):
        if "Critical" in urgency or "Overdue" in urgency: return "#ef4444" # red
        if "Urgent" in urgency: return "#f97316" # orange
        if "Upcoming" in urgency: return "#eab308" # yellow
        return "#22c55e" # green

    if not urgent_tasks:
        st.success("🎉 You're all caught up! No pending actions required.")

    for task in urgent_tasks:
        urgency = get_urgency_level(task.due_date)
        color = get_urgency_color(urgency)
        countdown = get_time_remaining(task.due_date)
        
        # Modern Card UI
        st.markdown(f"""
        <div style="
            background: #1e1e1e;
            border-left: 6px solid {color};
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div>
                <h4 style="margin: 0; padding-bottom: 4px; color: #f8fafc;">{task.assignment_name}</h4>
                <div style="color: #94a3b8; font-size: 0.9em; display: flex; gap: 15px;">
                    <span>📚 {task.course_name}</span>
                    <span>⏳ <b>{countdown}</b></span>
                    <span>📝 Status: {task.status.replace('_', ' ').title()}</span>
                </div>
            </div>
            <div style="color: {color}; font-weight: bold; font-size: 0.85em; background: {color}22; padding: 4px 10px; border-radius: 12px;">
                {urgency.split()[0]}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        has_draft = bool(task.draft_path and os.path.exists(task.draft_path))
        
        with st.expander(f"View & Manage '{task.assignment_name}'", expanded=False):
            if not has_draft:
                st.info("Agent has not drafted this assignment yet.")
                col_gen, _ = st.columns([1, 4])
                with col_gen:
                    if st.button("🤖 Generate Draft", key=f"force_gen_{task.id}", type="primary"):
                        if agent_status:
                            with st.spinner("Generating..."):
                                subprocess.run(["python", "-m", "moodle_agent.cli", "generate", str(task.id), "--type", "draft"])
                                st.rerun()
                        else:
                            st.error("Agent paused.")
            else:
                with open(task.draft_path, 'r', encoding='utf-8') as f:
                    draft_content = f.read()
                
                st.markdown("##### 📄 Draft Preview")
                with st.container(height=250):
                    st.markdown(draft_content)
                
                # Quick Action Buttons
                st.markdown("##### ⚡ Quick Actions")
                btn_cols = st.columns([1.2, 1.2, 1.2, 1.5, 2])
                with btn_cols[0]:
                    is_approved = (task.status == 'approved')
                    btn_label = "✅ Approved" if is_approved else "✅ Approve"
                    btn_type = "secondary" if is_approved else "primary"
                    
                    if st.button(btn_label, key=f"app_{task.id}", type=btn_type, disabled=is_approved):
                        safe_title = re.sub(r'[\\/*?:"<>|]', '-', task.assignment_name)
                        pdf_path = str(Path(task.draft_path).parent / f"{STUDENT_PRN}_{safe_title}.pdf")
                        if convert_md_to_pdf(draft_content, pdf_path):
                            db.update_task_status(task.id, TaskStatus.APPROVED)
                            db.update_task_paths(task.id, upload_package_path=pdf_path)
                            st.toast(f"✅ {task.assignment_name} Draft Approved & PDF Exported!")
                            time.sleep(0.5) # Give toast time to appear before rerun
                            st.rerun()
                
                with btn_cols[1]:
                    if st.button("🔄 Retry Draft", key=f"retry_{task.id}"):
                        with st.spinner("Regenerating..."):
                            subprocess.run(["python", "-m", "moodle_agent.cli", "generate", str(task.id), "--type", "draft"])
                            st.toast("Draft regenerated!")
                            st.rerun()

                with btn_cols[2]:
                    if task.status == 'approved':
                        if st.button("🚀 Upload", key=f"upload_{task.id}", type="primary"):
                            from moodle_agent.moodle_client import MoodleClient
                            pdf_path = db.get_task(task.id).upload_package_path
                            if pdf_path and os.path.exists(pdf_path):
                                client = MoodleClient()
                                item_id = client.upload_file(pdf_path)
                                if item_id and client.submit_assignment_file(task.moodle_assignment_id, item_id):
                                    db.update_task_status(task.id, TaskStatus.SUBMITTED)
                                    st.success("Uploaded!")
                                    st.rerun()
                                else:
                                    st.error("Failed to submit to Moodle. Check logs.")
                            else:
                                st.error("PDF missing.")
                                
                with btn_cols[3]:
                    if task.status == 'approved' and db.get_task(task.id).upload_package_path:
                        pdf_path = db.get_task(task.id).upload_package_path
                        if os.path.exists(pdf_path):
                            with open(pdf_path, "rb") as f:
                                st.download_button("💾 Download PDF", data=f, file_name=Path(pdf_path).name, mime="application/pdf", key=f"dl_{task.id}")
                                
                with btn_cols[4]:
                    if st.button("⚠️ Force Override", key=f"override_{task.id}"):
                        st.warning("Override toggled.")
                        
        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

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
    st.subheader("🗃️ Submission History")
    submitted_tasks = sorted([t for t in tasks if t.status == 'submitted'], key=lambda x: str(x.updated_at), reverse=True)
    
    if not submitted_tasks:
        st.info("No assignments have been submitted yet.")
    else:
        for t in submitted_tasks:
            with st.container():
                st.markdown(f"#### 📝 {t.assignment_name}")
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                with col1:
                    st.markdown(f"**Course:** {t.course_name}")
                with col2:
                    st.markdown(f"**Submitted At:** {t.updated_at[:16].replace('T', ' ')}")
                with col3:
                    st.markdown(f"**Deadline:** {get_time_remaining(t.due_date)}")
                with col4:
                    if t.upload_package_path and os.path.exists(t.upload_package_path):
                        with open(t.upload_package_path, "rb") as f:
                            st.download_button("💾 Download PDF", data=f, file_name=Path(t.upload_package_path).name, mime="application/pdf", key=f"hist_dl_{t.id}")
                st.divider()

    st.subheader("System Logs & Diagnostics")
    log_path = Path(DATA_DIR) / "app.log"
    if log_path.exists():
        with open(log_path, 'r') as f:
            log_content = "".join(f.readlines()[-100:])
        st.code(log_content, language="text")
    else:
        st.info("No system logs found.")
