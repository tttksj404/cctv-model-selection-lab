from __future__ import annotations

import argparse
import json
from pathlib import Path

KNOWN = {
    "chirla-gallery-3-seq_001-3": {
        "upper_color": "white",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-gallery-5-seq_001-3": {
        "upper_color": "black",
        "lower_color": "green",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-gallery-6-seq_001-3": {
        "upper_color": "black",
        "lower_color": "green",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-gallery-9-seq_001-3": {
        "upper_color": "navy",
        "lower_color": "black",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-gallery-10-seq_001-3": {
        "upper_color": "black",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "partial body crop",
    },
    "chirla-query-1-seq_002-3": {
        "upper_color": "pink",
        "lower_color": "black",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-2-seq_004-4": {
        "upper_color": "white",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-3-seq_002-3": {
        "upper_color": "white",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-5-seq_002-3": {
        "upper_color": "black",
        "lower_color": "green",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-6-seq_002-3": {
        "upper_color": "black",
        "lower_color": "green",
        "carrying": "none",
        "headwear": "none",
        "visibility": "partial body crop",
    },
    "chirla-query-9-seq_007-1": {
        "upper_color": "gray",
        "lower_color": "beige",
        "carrying": "other bag",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-neg-1-seq_004-4": {
        "upper_color": "brown",
        "lower_color": "black",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-neg-5-seq_004-6": {
        "upper_color": "black",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-neg-6-seq_004-6": {
        "upper_color": "blue",
        "lower_color": "black",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-neg-9-seq_002-3": {
        "upper_color": "navy",
        "lower_color": "black",
        "carrying": "none",
        "headwear": "none",
        "visibility": "full body visible",
    },
    "chirla-query-neg-10-seq_002-3": {
        "upper_color": "navy",
        "lower_color": "gray",
        "carrying": "none",
        "headwear": "none",
        "visibility": "partial body crop",
    },
}

FIELDS = ("upper_color", "lower_color", "carrying", "headwear", "visibility")


def build_adjudication(manifest: Path, output: Path) -> int:
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tracks: dict[str, dict[str, str]] = {}
    for row in rows:
        tracks.setdefault(row["trackId"], row)
    output_rows = []
    for track_id, row in tracks.items():
        labels = KNOWN.get(track_id, {})
        attributes = {field: labels.get(field, "unknown") for field in FIELDS}
        adjudicable = any(value != "unknown" for value in attributes.values())
        output_rows.append(
            {
                "trackId": track_id,
                "identityGroupId": row["identityGroupId"],
                "targetRole": row["targetRole"],
                "sourceLabel": row.get("sourceIdentity"),
                "sourceLabelReviewer": "CHIRLA official benchmark directory label",
                "independentReviewer": "manual_contact_sheet_adjudicator_20260727",
                "identityAdjudication": "source_label_kept",
                "identityAdjudicationBasis": (
                    "directory identity and frame-path trace; visual identity is not asserted "
                    "where the crop is insufficient"
                ),
                "adjudicationStatus": "adjudicated_visible_attributes"
                if adjudicable
                else "not_adjudicable_crop",
                "representativeFramePath": row["framePath"],
                "adjudicatedAttributes": attributes,
                "adjudicationConfidence": "low" if adjudicable else "none",
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    return len(output_rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_adjudication(args.manifest, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
