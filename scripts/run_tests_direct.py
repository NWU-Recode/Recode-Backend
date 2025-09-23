import sys
import types
import asyncio
from pathlib import Path


def make_app_stub(app_path: Path):
    # Create a placeholder 'app' package module so submodules can be imported
    mod = types.ModuleType("app")
    mod.__path__ = [str(app_path)]
    sys.modules["app"] = mod


async def run_workflow_check():
    try:
        from app.features.topic_detections.topics.topic_service import topic_service
        print("Loaded topic_service")
        topics = await topic_service.get_all_topics_for_week(1, None)
        print("Topics for week 1:", topics)
    except Exception as e:
        print("Workflow check failed:", repr(e))


async def run_slide_upload_check():
    try:
        from app.features.slides.upload import upload_slide_bytes
        sample = Path(__file__).parent.parent / "Assets" / "Week1_Variables_Loops.pptx"
        if not sample.exists():
            print("Slide upload sample not found, skipping upload test")
            return
        data = sample.read_bytes()
        from datetime import datetime, date
        res = await upload_slide_bytes(
            file_bytes=data,
            original_filename=sample.name,
            topic_name="Test Topic",
            given_at_dt=datetime.now(),
            semester_start_date=date(2025,7,7),
            module_code="CMPG111",
        )
        print("Slide upload result:", res)
    except Exception as e:
        print("Slide upload check failed:", repr(e))


def main():
    repo_root = Path(__file__).parent.parent
    app_path = repo_root / "app"
    make_app_stub(app_path)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_workflow_check())
    loop.run_until_complete(run_slide_upload_check())


if __name__ == "__main__":
    main()
