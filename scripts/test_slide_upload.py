import asyncio
import os
import sys
from datetime import datetime, date

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.features.slides.upload import upload_slide_bytes

async def test_slide_upload():
    # Use the sample PPTX file
    pptx_path = "Assets/Week1_Variables_Loops.pptx"
    if not os.path.exists(pptx_path):
        print("PPTX file not found")
        return

    with open(pptx_path, "rb") as f:
        file_bytes = f.read()

    original_filename = "Week1_Variables_Loops.pptx"
    topic_name = "Test Topic"
    given_at_dt = datetime.now()
    # Read semester start from env or default to original value
    semester_start_env = os.environ.get("SEMESTER_START")
    if semester_start_env:
        try:
            semester_start_date = date.fromisoformat(semester_start_env)
        except Exception:
            semester_start_date = date(2025, 7, 7)
    else:
        semester_start_date = date(2025, 7, 7)

    result = await upload_slide_bytes(
        file_bytes=file_bytes,
        original_filename=original_filename,
        topic_name=topic_name,
        given_at_dt=given_at_dt,
        semester_start_date=semester_start_date,
        module_code="CMPG111",
    )

    print("Upload result:", result)

if __name__ == "__main__":
    asyncio.run(test_slide_upload())