from __future__ import annotations

import argparse
import json
from pathlib import Path

from .distillation import DistillationSample, file_sha256


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qwen-annotation")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--teacher-model", required=True)
    parser.add_argument(
        "--source-kind",
        choices=("human", "open_model", "synthetic_fixture", "florence", "sonnet"),
        default="open_model",
    )
    parser.add_argument("--prompt-version", default="candidate-v1")
    parser.add_argument(
        "--approval-status",
        choices=("pending", "approved", "rejected"),
        default="pending",
    )
    parser.add_argument("--reviewed-by")
    parser.add_argument("--teacher-agreement", action="store_true")
    parser.add_argument("--decision", choices=("match", "review", "reject"), required=True)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--color")
    parser.add_argument("--clothing")
    parser.add_argument("--object-name")
    parser.add_argument("--texture", action="append", default=[])
    parser.add_argument("--bbox", nargs=4, type=float)
    parser.add_argument("--track-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    image_root = args.image_root.expanduser().resolve(strict=True)
    image_path = args.image.expanduser().resolve(strict=True)
    relative_image = image_path.relative_to(image_root).as_posix()
    geometry: dict[str, object] | None = None
    if args.bbox or args.track_id is not None:
        geometry = {}
        if args.bbox:
            geometry["bbox"] = {"bbox2d": args.bbox}
        if args.track_id is not None:
            geometry["trackId"] = args.track_id
    sample = DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": args.sample_id,
            "imagePath": relative_image,
            "attributes": {
                "color": args.color,
                "clothing": args.clothing,
                "objectName": args.object_name,
                "texture": tuple(args.texture),
            },
            "decision": args.decision,
            "confidence": args.confidence,
            "provenance": {
                "sourceKind": args.source_kind,
                "teacherModel": args.teacher_model,
                "promptVersion": args.prompt_version,
                "sourceHash": file_sha256(image_path),
                "approvalStatus": args.approval_status,
                "reviewedBy": args.reviewed_by,
                "teacherAgreement": args.teacher_agreement,
            },
            "geometry": geometry,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as output_file:
        output_file.write(
            json.dumps(sample.model_dump(mode="json", by_alias=True), ensure_ascii=False)
        )
        output_file.write("\n")
    print(
        json.dumps({"sampleId": sample.sample_id, "output": str(args.output)}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

