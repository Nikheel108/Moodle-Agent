import sys
with open('moodle_agent/ui.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
'''        if not active_acc or selected_account != active_acc.username:
            acc_mgr.set_active_account(selected_account)
            st.rerun()''',
'''        if not active_acc or selected_account != active_acc.username:
            with st.spinner(f"🔄 Switching to {selected_account} and syncing..."):
                import time
                time.sleep(0.5)
                acc_mgr.set_active_account(selected_account)
                st.toast(f"✅ Switched active account to {selected_account}")
            st.rerun()'''
)

with open('moodle_agent/ui.py', 'w', encoding='utf-8') as f:
    f.write(code)
