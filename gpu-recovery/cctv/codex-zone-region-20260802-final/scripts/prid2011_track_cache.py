from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding


def save_track_cache(path: Path, tracks: Sequence[TrackEmbedding]) -> None:
    if not tracks:
        raise ValueError("cannot save an empty track cache")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        track_ids=np.asarray([track.track_id for track in tracks]),
        identities=np.asarray([track.identity for track in tracks]),
        roles=np.asarray([track.role for track in tracks]),
        cameras=np.asarray([track.camera for track in tracks]),
        splits=np.asarray([track.split for track in tracks]),
        vectors=np.stack([track.vector for track in tracks]),
        frame_counts=np.asarray([track.frame_count for track in tracks], dtype=np.int64),
    )


def load_track_cache(path: Path) -> list[TrackEmbedding]:
    with np.load(path, allow_pickle=False) as cache:
        track_ids = np.asarray(cache["track_ids"]).astype(str)
        identities = np.asarray(cache["identities"]).astype(str)
        roles = np.asarray(cache["roles"]).astype(str)
        cameras = np.asarray(cache["cameras"]).astype(str)
        splits = np.asarray(cache["splits"]).astype(str)
        vectors = np.asarray(cache["vectors"], dtype=np.float32)
        frame_counts = np.asarray(cache["frame_counts"], dtype=np.int64)
    lengths = {
        len(track_ids),
        len(identities),
        len(roles),
        len(cameras),
        len(splits),
        len(vectors),
        len(frame_counts),
    }
    if len(lengths) != 1:
        raise ValueError("track cache arrays have inconsistent lengths")
    return [
        TrackEmbedding(
            track_id=str(track_ids[index]),
            identity=str(identities[index]),
            role=str(roles[index]),
            camera=str(cameras[index]),
            split=str(splits[index]),
            vector=vectors[index],
            frame_count=int(frame_counts[index]),
        )
        for index in range(len(track_ids))
    ]
