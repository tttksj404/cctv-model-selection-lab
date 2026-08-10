from pathlib import Path

from qwen_backend.solider_clip_engine import EngineConfig, SoliderClipCandidateEngine


def _engine() -> SoliderClipCandidateEngine:
    return SoliderClipCandidateEngine(
        EngineConfig(
            model_key="fixture-hybrid-v1",
            device="cpu",
            yolo_weights="models/yolo11x.pt",
            tracker="bytetrack.yaml",
            reid_checkpoint=Path("models/solider_reid/swin_base_msmt17.pth"),
            solider_root=Path("external/SOLIDER-REID-runtime-8c08e1c"),
            clip_checkpoint="fixture-clip",
            top_k=5,
            max_crops_per_track=1,
            detector_confidence=0.25,
            frame_stride=1,
            sample_every_seconds=1.0,
            crop_margin=0.0,
            reid_weight=1.0,
            clip_weight=0.0,
            aggregate_top_frames=1,
            reid_batch_size=1,
        )
    )


def test_candidate_models_are_loaded_once_for_engine_lifetime(monkeypatch) -> None:
    engine = _engine()
    calls = {"yolo": 0, "clip": 0, "solider": 0}
    objects = {name: object() for name in calls}

    def load(name: str):
        calls[name] += 1
        return objects[name]

    monkeypatch.setattr(engine, "_load_detector", lambda: load("yolo"))
    monkeypatch.setattr(engine, "_load_clip_bundle", lambda: load("clip"))
    monkeypatch.setattr(engine, "_load_solider_encoder", lambda: load("solider"))

    assert engine._get_detector() is objects["yolo"]
    assert engine._get_detector() is objects["yolo"]
    assert engine._get_clip_bundle() is objects["clip"]
    assert engine._get_clip_bundle() is objects["clip"]
    assert engine._get_solider_encoder() is objects["solider"]
    assert engine._get_solider_encoder() is objects["solider"]

    assert calls == {"yolo": 1, "clip": 1, "solider": 1}
    assert engine.cache_status == {
        "yolo": {"loaded": True, "loads": 1, "hits": 1},
        "clip": {"loaded": True, "loads": 1, "hits": 1},
        "solider": {"loaded": True, "loads": 1, "hits": 1},
    }


def test_candidate_warm_up_loads_required_models_before_inference(monkeypatch) -> None:
    engine = _engine()
    calls = {"yolo": 0, "clip": 0}

    def load(name: str) -> object:
        calls[name] += 1
        return object()

    monkeypatch.setattr(engine, "_load_detector", lambda: load("yolo"))
    monkeypatch.setattr(engine, "_load_clip_bundle", lambda: load("clip"))

    engine.warm_up()
    engine.warm_up()

    assert calls == {"yolo": 1, "clip": 1}
    assert engine.cache_status["yolo"]["loaded"] is True
    assert engine.cache_status["clip"]["loaded"] is True

