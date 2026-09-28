import os
from pathlib import Path
from moodle_agent.config import DRAFTS_DIR
import re
from moodle_agent.pdf_exporter import convert_md_to_pdf

drafts = list(Path(DRAFTS_DIR).rglob('*.md'))
for t_draft_path in drafts:
    t_assignment_name = t_draft_path.parent.name
    safe_title = re.sub(r'[\\/*?:"<>|]', '-', t_assignment_name)
    prn = '202401110020'
    pdf_path = str(t_draft_path.parent / f'{prn}_{safe_title}.pdf')
    print('Testing path:', pdf_path)
    
    content = open(t_draft_path, encoding='utf-8').read()
    try:
        res = convert_md_to_pdf(content, pdf_path)
        print('Result:', res)
    except Exception as e:
        print('Exception:', e)
