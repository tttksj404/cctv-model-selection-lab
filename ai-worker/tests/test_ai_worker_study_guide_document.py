from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "AI_WORKER_STUDY_GUIDE_MIDDLE_SCHOOL.md"
PDF = ROOT / "output" / "pdf" / "AI_WORKER_STUDY_GUIDE_MIDDLE_SCHOOL.pdf"


def test_study_guide_is_standalone_and_code_focused() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    required = (
        "# EyesOnU AI Worker",
        "## 4. 학습은 어떻게 이루어지는가?",
        "## 5. CLIP 학습",
        "## 6. Sonnet 선생님을 이용한 속성 학습",
        "## 7. SOLIDER 학습",
        "## 8. Qwen 증류",
        "## 9. CCTV 추론은 어떻게 실행되는가?",
        "loss.backward()",
        "optimizer.step()",
        "fuse_track_scores",
        "RuntimeCandidate",
        "프로젝트 CCTV 전체의 일반화 85% 증명",
    )
    for fragment in required:
        assert fragment in text


def test_study_guide_pdf_is_present() -> None:
    assert PDF.is_file()
    assert PDF.read_bytes().startswith(b"%PDF-")
    assert PDF.stat().st_size > 100_000
