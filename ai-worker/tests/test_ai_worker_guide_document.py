from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "AI_WORKER_COMPLETE_GUIDE.md"
PDF = ROOT / "output" / "pdf" / "AI_WORKER_COMPLETE_GUIDE_EASY.pdf"


def test_guide_explains_reproducible_training_and_orchestration() -> None:
    text = GUIDE.read_text(encoding="utf-8")

    required_fragments = (
        "### 13.5 쉽게 이해하고 실제 코드로 보는 파인튜닝",
        "### 13.6 쉽게 이해하고 실제 코드로 보는 증류",
        "### 13.7 쉽게 이해하고 실제 오케스트레이션 코드 보기",
        "먼저 어려운 단어를 아주 쉽게 바꾸면 다음과 같다.",
        "각 모델에게 잘하는 일을 맡기고, 마지막에 결과를 모아 판단하는 **역할 분담**",
        "loss.backward()",
        "optimizer.step()",
        "DistillationSample",
        "to_qwen_record",
        "fuse_track_scores",
        "RuntimeCandidate",
        "현재 저장소의 기록만으로는 프로젝트 CCTV 전체",
    )
    for fragment in required_fragments:
        assert fragment in text


def test_guide_references_existing_implementation_files() -> None:
    paths = (
        "scripts/train_clip_vitl14_distill.py",
        "scripts/finetune_clip_l14_sonnet_aux.py",
        "scripts/finetune_prid2011_solider_backbone.py",
        "src/qwen_backend/distillation.py",
        "src/qwen_backend/distillation_cli.py",
        "src/qwen_backend/multi_model_candidate_engine.py",
        "src/qwen_backend/attribute_ensemble.py",
    )
    text = GUIDE.read_text(encoding="utf-8")
    for relative in paths:
        assert relative in text
        assert (ROOT / relative).is_file()


def test_pdf_artifact_is_present() -> None:
    assert PDF.is_file()
    assert PDF.read_bytes().startswith(b"%PDF-")
    assert PDF.stat().st_size > 100_000
