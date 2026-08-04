from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast

import joblib
import numpy as np
import torch
from numpy.typing import NDArray
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn

from scripts.build_zone_region_dataset import FEATURE_NAMES, ROUTES, RouteName
from scripts.zone_region_metrics import evaluate_zone_predictions

ACTIVATION_STATUS = "experiment_selected_not_integrated"
MOCK_RECOMMENDATION_POLICY_ID = "dashboard_mock_jurisdiction_mass_v1"
MOCK_JURISDICTION_MASS_MINIMUM = 0.50


class Classifier(Protocol):
    def fit(self, X: NDArray[np.float32], y: NDArray[np.int64]) -> object: ...

    def predict(self, X: NDArray[np.float32]) -> NDArray[np.int64]: ...


class LinearClassifier(Classifier, Protocol):
    classes_: NDArray[np.int64]
    coef_: NDArray[np.float32]
    intercept_: NDArray[np.float32]


class ZoneMlp(nn.Module):
    def __init__(self, feature_count: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(feature_count, 64),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 4),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.network(values)


def load_route_dataset(
    payload: bytes,
    *,
    source: Path,
    route: RouteName,
    expected_cohort: str,
) -> tuple[np.ndarray, np.ndarray]:
    features: list[list[float]] = []
    targets: list[int] = []
    for line in payload.decode("utf-8").splitlines():
        row = json.loads(line)
        if row["cohort"] != expected_cohort:
            raise ValueError(
                f"{source} contains {row['cohort']!r}; expected only {expected_cohort!r}"
            )
        if row["route"] != route:
            continue
        features.append(row["features"])
        targets.append(int(row["targetZone"]) - 1)
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(targets, dtype=np.int64),
    )


def write_commitment_and_read_verified_sealed(
    *,
    commitment_path: Path,
    commitment: dict[str, Any],
    sealed_path: Path,
    expected_sealed_sha256: str,
) -> tuple[bytes, bytes]:
    commitment_payload = json.dumps(
        commitment,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    commitment_path.write_bytes(commitment_payload)
    sealed_payload = sealed_path.read_bytes()
    actual_sealed_sha256 = hashlib.sha256(sealed_payload).hexdigest()
    if actual_sealed_sha256 != expected_sealed_sha256:
        raise ValueError(
            "sealed dataset SHA-256 does not match the precommitted dataset manifest"
        )
    return commitment_payload, sealed_payload


def _metrics(
    targets: np.ndarray,
    predictions: np.ndarray,
    *,
    train_seconds: float,
    inference_seconds: float,
    device: str,
) -> dict[str, Any]:
    measured = evaluate_zone_predictions(
        tuple(int(value) + 1 for value in targets),
        tuple(int(value) + 1 for value in predictions),
    )
    return {
        **asdict(measured),
        "trainSeconds": train_seconds,
        "inferenceMillisecondsPerSample": inference_seconds * 1000.0 / len(targets),
        "device": device,
        "confusionMatrix": confusion_matrix(targets, predictions, labels=range(4)).tolist(),
    }


def prediction_sha256(predictions: np.ndarray) -> str:
    payload = json.dumps(
        [int(value) for value in np.asarray(predictions).reshape(-1)],
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _run_sklearn(
    name: str,
    model: Classifier,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
    *,
    export_safe_linear_model: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    model.fit(train_x, train_y)
    train_seconds = time.perf_counter() - started
    started = time.perf_counter()
    predictions = np.asarray(model.predict(test_x)).reshape(-1)
    inference_seconds = time.perf_counter() - started
    artifact = output_dir / f"{name}.joblib"
    joblib.dump(model, artifact)
    result: dict[str, Any] = {
        **_metrics(
            test_y,
            predictions,
            train_seconds=train_seconds,
            inference_seconds=inference_seconds,
            device="cpu",
        ),
        "artifact": artifact.name,
        "predictionSha256": prediction_sha256(predictions),
    }
    if export_safe_linear_model:
        linear_model = cast(LinearClassifier, model)
        safe_artifact = output_dir / f"{name}.safe.json"
        safe_payload = {
            "classes": [int(value) for value in linear_model.classes_.tolist()],
            "coefficients": linear_model.coef_.tolist(),
            "featureNames": FEATURE_NAMES,
            "intercepts": linear_model.intercept_.tolist(),
            "model": "logistic_regression_multiclass",
            "predictionCount": len(predictions),
            "predictionSha256": result["predictionSha256"],
            "schemaVersion": "eyesonu-zone-logistic-safe-v1",
            "sourceArtifactSha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        }
        safe_bytes = (
            json.dumps(safe_payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        safe_artifact.write_bytes(safe_bytes)
        result.update(
            {
                "safeArtifact": safe_artifact.name,
                "safeArtifactSha256": hashlib.sha256(safe_bytes).hexdigest(),
            }
        )
    return result


def _run_mlp(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    cast(Callable[[int], torch.Generator], torch.manual_seed)(20260802)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    fit_x, validation_x, fit_y, validation_y = train_test_split(
        train_x,
        train_y,
        test_size=0.20,
        random_state=20260802,
        stratify=train_y,
    )
    scaler = StandardScaler().fit(fit_x)
    fit_tensor = torch.tensor(scaler.transform(fit_x), dtype=torch.float32, device=device)
    fit_targets = torch.tensor(fit_y, dtype=torch.long, device=device)
    validation_tensor = torch.tensor(
        scaler.transform(validation_x), dtype=torch.float32, device=device
    )
    validation_targets = torch.tensor(validation_y, dtype=torch.long, device=device)
    model = ZoneMlp(train_x.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.001)
    optimizer_step = cast(Callable[[], object | None], optimizer.step)
    loss_function = nn.CrossEntropyLoss(label_smoothing=0.02)
    best_state: dict[str, torch.Tensor] | None = None
    best_loss = float("inf")
    remaining_patience = 25
    started = time.perf_counter()
    for _ in range(300):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss_function(model(fit_tensor), fit_targets).backward()
        optimizer_step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(loss_function(model(validation_tensor), validation_targets))
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            remaining_patience = 25
        else:
            remaining_patience -= 1
            if remaining_patience == 0:
                break
    train_seconds = time.perf_counter() - started
    if best_state is None:
        raise RuntimeError("MLP validation did not produce a checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    test_tensor = torch.tensor(scaler.transform(test_x), dtype=torch.float32, device=device)
    started = time.perf_counter()
    with torch.no_grad():
        predictions = model(test_tensor).argmax(dim=1).cpu().numpy()
    if device.type == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - started
    artifact = output_dir / "gpu_mlp.pt"
    torch.save(
        {
            "featureNames": FEATURE_NAMES,
            "stateDict": best_state,
            "scalerMean": scaler.mean_,
            "scalerScale": scaler.scale_,
        },
        artifact,
    )
    return {
        **_metrics(
            test_y,
            predictions,
            train_seconds=train_seconds,
            inference_seconds=inference_seconds,
            device=str(device),
        ),
        "artifact": artifact.name,
    }


def _run_xgboost(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.90,
        colsample_bytree=0.90,
        objective="multi:softprob",
        device="cuda",
        tree_method="hist",
        random_state=20260802,
    )
    started = time.perf_counter()
    model.fit(train_x, train_y)
    train_seconds = time.perf_counter() - started
    model.set_params(device="cpu")
    started = time.perf_counter()
    predictions = np.asarray(model.predict(test_x)).reshape(-1)
    inference_seconds = time.perf_counter() - started
    artifact = output_dir / "gpu_xgboost.joblib"
    joblib.dump(model, artifact)
    return {
        **_metrics(
            test_y,
            predictions,
            train_seconds=train_seconds,
            inference_seconds=inference_seconds,
            device="cuda_train_cpu_inference",
        ),
        "artifact": artifact.name,
    }


def _run_catboost(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=500,
        depth=7,
        learning_rate=0.04,
        loss_function="MultiClass",
        task_type="GPU",
        devices="0",
        random_seed=20260802,
        verbose=False,
    )
    result = _run_sklearn("gpu_catboost", model, train_x, train_y, test_x, test_y, output_dir)
    result["device"] = "cuda_train_cpu_inference"
    return result


def run_named_model(
    name: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if name == "posterior_argmax":
        final_indices = tuple(
            FEATURE_NAMES.index(f"final_zone_{zone_id}") for zone_id in range(1, 5)
        )
        started = time.perf_counter()
        predictions = test_x[:, final_indices].argmax(axis=1)
        inference_seconds = time.perf_counter() - started
        metrics = _metrics(
            test_y,
            predictions,
            train_seconds=0.0,
            inference_seconds=inference_seconds,
            device="cpu",
        )
        manifest_path = output_dir / "posterior_argmax.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "featureIndices": list(final_indices),
                    "model": "posterior_argmax",
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        metrics["artifact"] = manifest_path.name
        return metrics
    if name == "logistic":
        return _run_sklearn(
            name,
            LogisticRegression(max_iter=2000, C=1.0),
            train_x,
            train_y,
            test_x,
            test_y,
            output_dir,
            export_safe_linear_model=True,
        )
    if name == "extra_trees":
        return _run_sklearn(
            name,
            ExtraTreesClassifier(
                n_estimators=800,
                min_samples_leaf=2,
                max_features="sqrt",
                n_jobs=-1,
                random_state=20260802,
            ),
            train_x,
            train_y,
            test_x,
            test_y,
            output_dir,
        )
    if name == "hist_gradient_boosting":
        return _run_sklearn(
            name,
            HistGradientBoostingClassifier(
                max_iter=400,
                learning_rate=0.05,
                max_leaf_nodes=31,
                l2_regularization=0.01,
                random_state=20260802,
            ),
            train_x,
            train_y,
            test_x,
            test_y,
            output_dir,
        )
    if name == "gpu_mlp":
        return _run_mlp(train_x, train_y, test_x, test_y, output_dir)
    if name == "gpu_xgboost":
        return _run_xgboost(train_x, train_y, test_x, test_y, output_dir)
    if name == "gpu_catboost":
        return _run_catboost(train_x, train_y, test_x, test_y, output_dir)
    raise ValueError(f"unsupported zone model: {name}")


ModelRunner: TypeAlias = Callable[
    [str, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Path],
    dict[str, Any],
]


def run_model_suite(
    model_names: tuple[str, ...],
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
    *,
    runner: ModelRunner = run_named_model,
) -> dict[str, dict[str, Any]]:
    return {
        name: runner(
            name,
            train_x,
            train_y,
            test_x,
            test_y,
            output_dir / name,
        )
        for name in model_names
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare four-zone ranking models on sealed data")
    parser.add_argument("--selection-dataset", type=Path, required=True)
    parser.add_argument("--sealed-dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload = args.dataset_manifest.read_bytes()
    manifest = json.loads(manifest_payload.decode("utf-8"))
    if manifest.get("schemaVersion") != "eyesonu-zone-region-dataset-v2":
        raise ValueError("unsupported zone-region dataset manifest")
    selection_payload = args.selection_dataset.read_bytes()
    selection_sha256 = hashlib.sha256(selection_payload).hexdigest()
    selection_manifest = manifest["datasets"]["selection"]
    sealed_manifest = manifest["datasets"]["sealed_test"]
    if selection_sha256 != selection_manifest["sha256"]:
        raise ValueError("selection dataset SHA-256 does not match the dataset manifest")
    if len(selection_payload) != selection_manifest["bytes"]:
        raise ValueError("selection dataset byte count does not match the dataset manifest")
    expected_sealed_sha256 = str(sealed_manifest["sha256"])
    dataset_manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    model_names = (
        "posterior_argmax",
        "logistic",
        "extra_trees",
        "hist_gradient_boosting",
        "gpu_mlp",
        "gpu_xgboost",
        "gpu_catboost",
    )
    selection_results: dict[str, dict[str, dict[str, Any]]] = {}
    for route in ROUTES:
        selection_x, selection_y = load_route_dataset(
            selection_payload,
            source=args.selection_dataset,
            route=route,
            expected_cohort="selection",
        )
        split_values = train_test_split(
            selection_x,
            selection_y,
            test_size=0.20,
            random_state=20260802,
            stratify=selection_y,
        )
        fit_x = np.asarray(split_values[0], dtype=np.float32)
        validation_x = np.asarray(split_values[1], dtype=np.float32)
        fit_y = np.asarray(split_values[2], dtype=np.int64)
        validation_y = np.asarray(split_values[3], dtype=np.int64)
        selection_results[route] = run_model_suite(
            model_names,
            fit_x,
            fit_y,
            validation_x,
            validation_y,
            args.output_dir / "selection_validation" / route,
        )
    eligible = [
        (route, model, metrics)
        for route, models in selection_results.items()
        for model, metrics in models.items()
        if "wilson95_lower" in metrics
    ]
    selected_route_value, selected_model, selection_metrics = max(
        eligible,
        key=lambda item: (
            item[2]["wilson95_lower"],
            item[2]["accuracy"],
            -item[2]["inferenceMillisecondsPerSample"],
            item[0],
            item[1],
        ),
    )
    selected_route = cast(RouteName, selected_route_value)
    selection_commitment = {
        "route": selected_route,
        "model": selected_model,
        "selectionDatasetSha256": selection_sha256,
        "datasetManifestSha256": dataset_manifest_sha256,
        "sealedDatasetExpectedSha256": expected_sealed_sha256,
        "selectionValidationMetrics": selection_metrics,
    }
    commitment_path = args.output_dir / "selection_commitment.json"
    commitment_payload, sealed_payload = write_commitment_and_read_verified_sealed(
        commitment_path=commitment_path,
        commitment=selection_commitment,
        sealed_path=args.sealed_dataset,
        expected_sealed_sha256=expected_sealed_sha256,
    )
    selected_train_x, selected_train_y = load_route_dataset(
        selection_payload,
        source=args.selection_dataset,
        route=selected_route,
        expected_cohort="selection",
    )
    sealed_x, sealed_y = load_route_dataset(
        sealed_payload,
        source=args.sealed_dataset,
        route=selected_route,
        expected_cohort="sealed_test",
    )
    sealed_output_dir = args.output_dir / "sealed_selected" / selected_route / selected_model
    sealed_metrics = run_named_model(
        selected_model,
        selected_train_x,
        selected_train_y,
        sealed_x,
        sealed_y,
        sealed_output_dir,
    )
    artifact_path = sealed_output_dir / str(sealed_metrics["artifact"])
    sealed_metrics["artifactUri"] = artifact_path.as_posix()
    if artifact_path.is_file():
        sealed_metrics["artifactSha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    safe_artifact_name = sealed_metrics.get("safeArtifact")
    if isinstance(safe_artifact_name, str):
        safe_artifact_path = sealed_output_dir / safe_artifact_name
        sealed_metrics["safeArtifactUri"] = safe_artifact_path.as_posix()
        sealed_metrics["safeArtifactSha256"] = hashlib.sha256(
            safe_artifact_path.read_bytes()
        ).hexdigest()
    feature_schema_sha256 = hashlib.sha256(
        json.dumps(FEATURE_NAMES, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "schemaVersion": "eyesonu-zone-region-model-comparison-v3",
        "selectionDatasetSha256": selection_commitment["selectionDatasetSha256"],
        "sealedDatasetSha256": hashlib.sha256(sealed_payload).hexdigest(),
        "datasetManifestSha256": dataset_manifest_sha256,
        "selectionCommitmentSha256": hashlib.sha256(commitment_payload).hexdigest(),
        "featureSchemaSha256": feature_schema_sha256,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cudaAvailable": torch.cuda.is_available(),
            "gpuCount": torch.cuda.device_count(),
            "gpuName": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "selectionRule": (
            "maximum selection-validation Wilson 95% lower bound, then accuracy, "
            "then minimum inference latency"
        ),
        "sealedUsage": (
            "sealed file loaded only after the selection commitment was written; "
            "evaluated once for that committed winner"
        ),
        "activationStatus": ACTIVATION_STATUS,
        "scope": {
            "zoneCount": 4,
            "status": "prototype_not_in_official_two_zone_mvp",
            "backendContractIntegrated": False,
            "jetsonIntegrated": False,
            "projectCctvEvidence": False,
        },
        "automaticRecommendationPolicy": {
            "policyId": MOCK_RECOMMENDATION_POLICY_ID,
            "minimumJurisdictionMass": MOCK_JURISDICTION_MASS_MINIMUM,
            "scope": "dashboard_mock_safety_heuristic",
            "operationallyApproved": False,
        },
        "promotionDecision": {
            "accepted": False,
            "reasonCodes": [
                "SYNTHETIC_PROXY_ONLY",
                "OFFICIAL_FOUR_ZONE_REQUIREMENT_NOT_PRESENT",
                "PROJECT_CCTV_IDENTITY_TRACK_HELDOUT_NOT_EVALUATED",
                "PAIRED_RUNTIME_IMPROVEMENT_NOT_EVALUATED",
                "CANDIDATE_TPR_AT_FAR_NOT_EVALUATED",
                "CALIBRATION_ECE_NOT_EVALUATED",
                "FALSE_ZONE_SWITCH_NOT_EVALUATED",
                "RUNTIME_IMPLEMENTATION_NOT_PRESENT",
            ],
            "gates": {
                "syntheticProxyWilson85Passed": bool(sealed_metrics["passed"]),
                "officialFourZoneRequirementPresent": False,
                "projectCctvIdentityTrackHeldoutPassed": False,
                "selectionPairedRuntimeImprovementPassed": False,
                "sealedPairedRuntimeImprovementPassed": False,
                "candidateTprAtFarPassed": False,
                "calibrationEcePassed": False,
                "falseZoneSwitchPassed": False,
                "runtimeImplementationPresent": False,
            },
        },
        "selected": {
            "route": selected_route,
            "model": selected_model,
            "selectionValidationMetrics": selection_metrics,
            "sealedMetrics": sealed_metrics,
        },
        "selectionValidationResults": selection_results,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
