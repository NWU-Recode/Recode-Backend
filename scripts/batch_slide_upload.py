import asyncio
import os
import sys
from datetime import datetime, date, timedelta
import os
import re

# Ensure project root on sys.path so `app` package imports succeed
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.features.slides.upload import upload_slide_bytes

async def batch_upload_slides():
    # Directory with PPTX files
    assets_dir = "Assets"
    pptx_files = [f for f in os.listdir(assets_dir) if f.lower().endswith('.pptx')]
    
    # Sort by week number and exclude test files
    def get_week_num(filename):
        match = re.match(r'Week(\d+)_', filename)
        return int(match.group(1)) if match else 0
    
    # Filter out test files and sort by week number
    week_files = [f for f in pptx_files if f.startswith('Week')]
    week_files.sort(key=get_week_num)
    
    # Read SEMESTER_START from env (YYYY-MM-DD) or default
    semester_start_env = os.environ.get("SEMESTER_START")
    if semester_start_env:
        try:
            semester_start = date.fromisoformat(semester_start_env)
        except Exception:
            semester_start = date(2025, 7, 7)
    else:
        semester_start = date(2025, 7, 7)  # As in endpoints.py
    
    for idx, filename in enumerate(week_files):
        filepath = os.path.join(assets_dir, filename)
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        # Parse topic from filename but do not trust week in filename
        topic_match = re.match(r'Week\d+_(.+)\.pptx', filename)
        topic_name = topic_match.group(1).replace('_', ' ').title() if topic_match else "Topic"

        # Assign week by order: idx=0 -> week 1
        target_date = semester_start + timedelta(weeks=idx)
        given_at_dt = datetime.combine(target_date, datetime.min.time().replace(hour=10))

        print(f"Uploading {filename} as week {idx+1}, topic: {topic_name}")

        result = await upload_slide_bytes(
            file_bytes=file_bytes,
            original_filename=filename,
            topic_name=topic_name,
            given_at_dt=given_at_dt,
            semester_start_date=semester_start,
            module_code="CMPG111",
        )

        print(f"Result: extraction_id={(result.get('extraction') or {}).get('id')}, topic_id={(result.get('topic') or {}).get('id') if result.get('topic') else 'None'}")
        print("---")

if __name__ == "__main__":
    asyncio.run(batch_upload_slides())