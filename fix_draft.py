import sys
with open('moodle_agent/ui.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
'''                        if st.button("👀 View Draft", key=f"dash_view_draft_{t.id}"):
                            st.session_state[f"show_draft_{t.id}"] = not st.session_state.get(f"show_draft_{t.id}", False)''',
'''                        if st.button("👀 View Draft", key=f"dash_view_draft_{t.id}"):
                            with open(t.draft_path, 'r', encoding='utf-8') as f:
                                show_draft_dialog(t.assignment_name, f.read())'''
)

code = code.replace(
'''            if st.session_state.get(f"show_draft_{t.id}", False):
                with st.expander("📄 Draft Preview", expanded=True):
                    with open(t.draft_path, 'r', encoding='utf-8') as f:
                        st.markdown(f.read(), unsafe_allow_html=True)
''', ''
)

with open('moodle_agent/ui.py', 'w', encoding='utf-8') as f:
    f.write(code)
