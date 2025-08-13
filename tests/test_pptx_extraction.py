from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation

from pptx_extraction import extract_pptx_text


def _create_sample_pptx(path: Path) -> None:
    prs = Presentation()
    layout = prs.slide_layouts[0]

    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.title.text = "Title 1"
    slide1.placeholders[1].text = "Subtitle 1"

    slide2 = prs.slides.add_slide(layout)
    slide2.shapes.title.text = "Title 2"
    slide2.placeholders[1].text = "Subtitle 2"

    prs.save(path)


def test_extract_pptx_text(tmp_path: Path) -> None:
    pptx_file = tmp_path / "sample.pptx"
    _create_sample_pptx(pptx_file)

    result = extract_pptx_text(str(pptx_file))

    assert result == {
        1: ["Title 1", "Subtitle 1"],
        2: ["Title 2", "Subtitle 2"],
    }
