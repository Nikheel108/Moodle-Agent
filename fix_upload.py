import sys
with open('moodle_agent/ui.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
'''                                    st.success("Uploaded!")
                                    st.rerun()''',
'''                                    st.toast(f"🎉 Successfully Uploaded {t.assignment_name if 't' in locals() else task.assignment_name}!")
                                    st.balloons()
                                    import time
                                    time.sleep(1.5)
                                    st.rerun()'''
)

with open('moodle_agent/ui.py', 'w', encoding='utf-8') as f:
    f.write(code)
