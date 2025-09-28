import asyncio
import os
import sys
import re
from datetime import datetime, date, timedelta

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.features.slides.upload import upload_slide_bytes, create_topic_from_extraction

async def run():
    assets_dir = "Assets"
    pptx_files = [f for f in os.listdir(assets_dir) if f.lower().endswith('.pptx')]

    def get_week_num(filename):
        match = re.match(r'Week(\d+)_', filename)
        return int(match.group(1)) if match else 0

    week_files = [f for f in pptx_files if f.startswith('Week')]
    week_files.sort(key=get_week_num)

    # Read SEMESTER_START from env or default
    semester_start_env = os.environ.get("SEMESTER_START")
    if semester_start_env:
        try:
            semester_start = date.fromisoformat(semester_start_env)
        except Exception:
            semester_start = date(2025, 7, 7)
    else:
        semester_start = date(2025, 7, 7)
    module_code = "CMPG111"

    # Phase 1: persist extractions without creating topics
    extractions = []
    for idx, filename in enumerate(week_files):
        filepath = os.path.join(assets_dir, filename)
        with open(filepath, 'rb') as f:
            b = f.read()
        # Assign week by order (idx=0 -> week 1)
        target_date = semester_start + timedelta(weeks=idx)
        given_at_dt = datetime.combine(target_date, datetime.min.time().replace(hour=10))
        print('Uploading', filename, 'as week', idx+1)
        res = await upload_slide_bytes(b, filename, filename, given_at_dt, semester_start, module_code, create_topic=False)
        print(' -> extraction id:', res.get('extraction', {}).get('id'))
        extractions.append(res.get('extraction'))

    # Phase 2: create topics for each extraction
    for ex in extractions:
        if not ex:
            continue
        print('Creating topic for extraction id', ex.get('id'))
        topic = await create_topic_from_extraction(ex, module_code)
        print(' -> topic id:', topic.get('id'))

if __name__ == '__main__':
    asyncio.run(run())
