from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import cv2
import torch
import typer
from rich.console import Console

from qwen_backend.realtime_hud import render_dashboard
from qwen_backend.realtime_identity import validate_reference_image
from qwen_backend.realtime_model_security import ModelWeightError
from qwen_backend.realtime_models import (
    AppearanceProfile,
    AppearanceProfileError,
    CameraOpenError,
    FrameReadError,
    HeadlessAppearanceRequiredError,
    ProfileInputCancelledError,
    ReferenceImageError,
    SoliderCheckoutError,
    SoliderFeatureError,
)
from qwen_backend.realtime_vision import RealtimeVisionConfig, RealtimeVisionEngine

WINDOW_NAME = "EYES:ON U - 실시간 인상착의 유사도 탐색"
app = typer.Typer(add_completion=False, no_args_is_help=False)
console = Console()


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        raise CameraOpenError(camera_index=camera_index)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    capture.set(cv2.CAP_PROP_FPS, 30)
    return capture


def _device_name(device: str) -> str:
    torch_device = torch.device(device)
    if torch_device.type == "cuda" and torch.cuda.is_available():
        device_index = (
            int(device.partition(":")[2])
            if ":" in device
            else torch.cuda.current_device()
        )
        return f"GPU  {torch.cuda.get_device_name(device_index)}"
    return f"Device  {device}"


def _prompt_appearance() -> str:
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    try:
        appearance = simpledialog.askstring(
            "EYES:ON U 프로필 입력",
            (
                "찾을 사람의 인상착의를 입력하세요.\n\n"
                "예: 회색 반팔 검은색 바지 안경 넘긴머리 남자"
            ),
            parent=root,
        )
    finally:
        root.destroy()
    if appearance is None:
        raise ProfileInputCancelledError
    return appearance.strip()


@app.command()
def run(
    camera_index: Annotated[int, typer.Option("--camera-index", min=0)] = 0,
    appearance: Annotated[
        str | None,
        typer.Option(
            "--appearance",
            help="예: 회색 반팔 검은색 바지 안경 넘긴머리 남자",
        ),
    ] = None,
    clip_query_en: Annotated[
        str | None,
        typer.Option("--clip-query-en", help="선택: 직접 지정할 영문 CLIP 문장"),
    ] = None,
    reference_image: Annotated[
        Path | None,
        typer.Option(
            "--reference-image",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="선택: SOLIDER 동일인 검증용 기준 전신 사진",
        ),
    ] = None,
    yolo_weights: Annotated[str, typer.Option("--yolo-weights")] = "models/yolo11x.pt",
    solider_checkpoint: Annotated[
        str,
        typer.Option("--solider-checkpoint"),
    ] = "models/solider_reid/swin_base_msmt17.pth",
    solider_root: Annotated[
        str,
        typer.Option("--solider-root"),
    ] = "external/SOLIDER-REID-runtime-8c08e1c",
    device: Annotated[str, typer.Option("--device")] = "cuda",
    tracker: Annotated[str, typer.Option("--tracker")] = "bytetrack.yaml",
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0),
    ] = 0.30,
    image_size: Annotated[int, typer.Option("--image-size", min=1)] = 640,
    score_every_frames: Annotated[
        int,
        typer.Option("--score-every-frames", min=1),
    ] = 4,
    track_ttl_frames: Annotated[
        int,
        typer.Option("--track-ttl-frames", min=1),
    ] = 90,
    minimum_box_area_fraction: Annotated[
        float,
        typer.Option("--minimum-box-area-fraction", min=0.0, max=1.0),
    ] = 0.01,
    evidence_path: Annotated[
        Path,
        typer.Option("--evidence-path"),
    ] = Path("artifacts/realtime_demo/latest.jpg"),
    max_frames: Annotated[int, typer.Option("--max-frames", min=0)] = 0,
    auto_save_interval: Annotated[
        int,
        typer.Option(
            "--auto-save-interval",
            min=0,
            help="0이면 자동 저장을 끕니다. 양수이면 지정 프레임 간격으로 저장합니다.",
        ),
    ] = 0,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    if appearance is None:
        if headless:
            raise HeadlessAppearanceRequiredError
        appearance = _prompt_appearance()
    assert appearance is not None
    profile = AppearanceProfile.from_description(
        appearance,
        clip_query_en=clip_query_en,
    )
    validated_reference = (
        validate_reference_image(reference_image)
        if reference_image is not None
        else None
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    console.print("[cyan]YOLO11x + CLIP ViT-L/14 + SOLIDER 모델을 GPU에 올리는 중[/cyan]")
    engine = RealtimeVisionEngine(
        profile,
        RealtimeVisionConfig(
            yolo_weights=yolo_weights,
            solider_checkpoint=solider_checkpoint,
            solider_root=solider_root,
            reference_image=validated_reference,
            device=device,
            tracker=tracker,
            confidence=confidence,
            image_size=image_size,
            score_every_frames=score_every_frames,
            track_ttl_frames=track_ttl_frames,
            minimum_box_area_fraction=minimum_box_area_fraction,
        ),
    )
    capture = _open_camera(camera_index)
    console.print(f"[cyan]카메라 {camera_index} 연결 완료[/cyan]")
    console.print(f"[green]실시간 추론 시작[/green]  {profile.description_ko}")
    console.print(
        "[green]SOLIDER 모드[/green]  "
        + (
            "기준 사진 동일인 검증"
            if validated_reference is not None
            else "CLIP 안정 후보 자동등록 후 동일인 추적"
        )
    )

    frame_number = 0
    smoothed_fps = 0.0
    last_tick = time.perf_counter()
    try:
        if not headless:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, 1420, 760)
        while True:
            ok, frame = capture.read()
            if not ok:
                raise FrameReadError(camera_index=camera_index)
            inference = engine.process(frame, frame_number)
            now = time.perf_counter()
            instant_fps = 1.0 / max(now - last_tick, 1e-6)
            smoothed_fps = (
                instant_fps if frame_number == 0 else smoothed_fps * 0.9 + instant_fps * 0.1
            )
            last_tick = now
            dashboard = render_dashboard(
                frame,
                profile,
                inference,
                camera_index=camera_index,
                fps=smoothed_fps,
                device_name=_device_name(device),
                auto_save_interval=auto_save_interval,
            )
            if auto_save_interval > 0 and frame_number % auto_save_interval == 0:
                if not cv2.imwrite(str(evidence_path), dashboard):
                    raise OSError(f"preview_write_failed: {evidence_path.name}")
            if not headless:
                cv2.imshow(WINDOW_NAME, dashboard)
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("s") and not cv2.imwrite(str(evidence_path), dashboard):
                    raise OSError(f"preview_write_failed: {evidence_path.name}")
            frame_number += 1
            if max_frames > 0 and frame_number >= max_frames:
                break
    finally:
        capture.release()
        if not headless:
            cv2.destroyAllWindows()
    console.print(
        f"[green]runtime_complete[/green]  frames={frame_number}  evidence={evidence_path}"
    )


def main() -> None:
    try:
        app()
    except ProfileInputCancelledError as error:
        console.print(f"[yellow]{error}[/yellow]")
    except (
        AppearanceProfileError,
        CameraOpenError,
        FileNotFoundError,
        FrameReadError,
        HeadlessAppearanceRequiredError,
        ModelWeightError,
        ReferenceImageError,
        SoliderCheckoutError,
        SoliderFeatureError,
    ) as error:
        console.print(f"[red]{error}[/red]")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
