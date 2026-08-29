"""MMPoseのRTMPoseモデルを使って動画から2D姿勢を推定する。"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata as importlib_metadata
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter
from typing import Any, Iterable

# MPS未実装のPyTorch演算だけCPUで実行する。torch/mmposeより先に設定する必要がある。
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lib.get_filepath import get_video_selection
from lib.get_output_settings import get_output_settings
from lib.progress_window import ProgressWindow
from lib.rtmpose_get_parameter import rtmpose_get_parameters


OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "datas" / "outputs"
RTMPOSE_LANDMARKS = [
    (0, "鼻"),
    (1, "左目"),
    (2, "右目"),
    (3, "左耳"),
    (4, "右耳"),
    (5, "左肩"),
    (6, "右肩"),
    (7, "左肘"),
    (8, "右肘"),
    (9, "左手首"),
    (10, "右手首"),
    (11, "左腰"),
    (12, "右腰"),
    (13, "左膝"),
    (14, "右膝"),
    (15, "左足首"),
    (16, "右足首"),
]
HALPE26_LANDMARKS = RTMPOSE_LANDMARKS + [
    (17, "頭頂"),
    (18, "首"),
    (19, "腰中心"),
    (20, "左母趾（親指側のつま先）"),
    (21, "右母趾（親指側のつま先）"),
    (22, "左小趾（小指側のつま先）"),
    (23, "右小趾（小指側のつま先）"),
    (24, "左かかと"),
    (25, "右かかと"),
]
COCO_SKELETON = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
]
HALPE26_SKELETON = [
    (15, 13),
    (13, 11),
    (11, 19),
    (16, 14),
    (14, 12),
    (12, 19),
    (17, 18),
    (18, 19),
    (18, 5),
    (5, 7),
    (7, 9),
    (18, 6),
    (6, 8),
    (8, 10),
    (1, 2),
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (3, 5),
    (4, 6),
    (15, 20),
    (15, 22),
    (15, 24),
    (16, 21),
    (16, 23),
    (16, 25),
]


def pose_layout_for_model(model: str) -> str:
    """MMPoseのモデル指定から出力キーポイント形式を判定する。"""
    normalized = model.strip().lower()
    if normalized == "body26" or "halpe26" in normalized:
        return "halpe26"
    return "coco17"


def landmarks_for_model(model: str):
    return (
        HALPE26_LANDMARKS
        if pose_layout_for_model(model) == "halpe26"
        else RTMPOSE_LANDMARKS
    )


def skeleton_for_model(model: str):
    return (
        HALPE26_SKELETON
        if pose_layout_for_model(model) == "halpe26"
        else COCO_SKELETON
    )


def file_sha256(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except (ImportError, RuntimeError):
        return False


def mps_available() -> bool:
    try:
        import torch

        backend = getattr(torch.backends, "mps", None)
        return bool(backend is not None and backend.is_available())
    except (ImportError, RuntimeError):
        return False


def resolve_device(parameters: dict[str, Any]) -> str:
    requested = parameters["device"]
    if requested == "CPU":
        return "cpu"
    cuda_device = f"cuda:{parameters['cuda_index']}"
    if requested == "CUDA":
        return cuda_device if cuda_available() else "cpu"
    if requested == "MPS":
        return "mps" if mps_available() else "cpu"
    if cuda_available():
        return cuda_device
    if mps_available():
        return "mps"
    return "cpu"


class DeviceFallbackInferencer:
    """アクセラレータ実行失敗時にCPUで同じ推論を再試行する。"""

    FALLBACK_ERRORS = (RuntimeError, AssertionError, NotImplementedError)

    def __init__(self, builder, kwargs: dict[str, Any]):
        self._builder = builder
        self._kwargs = kwargs.copy()
        self.used_device = self._kwargs["device"]
        self._inferencer = self._builder(**self._kwargs)
        self.detector_device = self.used_device
        self._configure_mps_hybrid()

    def _configure_mps_hybrid(self) -> None:
        """MPS未対応NMSを避けるため、人物検出器だけCPUへ移す。"""
        if self.used_device != "mps":
            return
        pose_inferencer = getattr(self._inferencer, "inferencer", None)
        detector = getattr(pose_inferencer, "detector", None)
        detector_model = getattr(detector, "model", None)
        if detector_model is None:
            return
        detector_model.to("cpu")
        self.detector_device = "cpu"
        print("[INFO] Apple Silicon: RTMPose=MPS, person detector=CPU")

    def _switch_to_cpu(self, error: Exception) -> None:
        print(f"[WARNING] {self.used_device}での推論に失敗しました: {error}")
        print("[WARNING] RTMPose推論器をCPUで再初期化します")
        self._kwargs["device"] = "cpu"
        self._inferencer = self._builder(**self._kwargs)
        self.used_device = "cpu"
        self.detector_device = "cpu"

    def __call__(self, *args, **kwargs):
        def generate():
            try:
                yield from self._inferencer(*args, **kwargs)
            except self.FALLBACK_ERRORS as error:
                if self.used_device == "cpu":
                    raise
                self._switch_to_cpu(error)
                yield from self._inferencer(*args, **kwargs)

        return generate()


def inferencer_init_kwargs(
    parameters: dict[str, Any], device: str
) -> dict[str, Any]:
    """MMPoseInferencer初期化引数を組み立てる。"""
    kwargs = {
        "pose2d": parameters["model"],
        "device": device,
    }
    detector = parameters.get("detector", "auto").strip()
    # MMPoseの姿勢モデルエイリアスに紐づく既定検出器を使用する。
    # 旧GUI値のhumanも後方互換のためautoと同じ扱いにする。
    if detector.lower() not in {"", "auto", "human"}:
        kwargs["det_model"] = detector
    return kwargs


def create_inferencer(parameters: dict[str, Any]):
    """MMPoseInferencerと実際に使用したデバイス名を返す。"""
    try:
        from mmpose.apis import MMPoseInferencer
    except ImportError as error:
        raise ImportError(
            "RTMPose用パッケージがありません。READMEの「RTMPoseの導入」を参照して "
            "MMPose、MMDetection、MMCV、PyTorchをインストールしてください。"
        ) from error

    requested_device = parameters["device"]
    device = resolve_device(parameters)
    if requested_device in {"CUDA", "MPS"} and device == "cpu":
        print(f"[WARNING] {requested_device}を利用できないためCPUへ切り替えます")

    kwargs = inferencer_init_kwargs(parameters, device)
    try:
        runtime = DeviceFallbackInferencer(MMPoseInferencer, kwargs)
        return runtime, runtime.used_device
    except DeviceFallbackInferencer.FALLBACK_ERRORS as error:
        if device == "cpu":
            raise
        print(f"[WARNING] {device}初期化に失敗しました: {error}")
        print("[WARNING] CPUへ切り替えます")
        kwargs["device"] = "cpu"
        runtime = DeviceFallbackInferencer(MMPoseInferencer, kwargs)
        return runtime, runtime.used_device


def _prediction_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = result.get("predictions") or []
    if predictions and isinstance(predictions[0], list):
        predictions = predictions[0]
    return [item for item in predictions if isinstance(item, dict)]


def _bbox_score(instance: dict[str, Any]) -> float:
    value = instance.get(
        "bbox_score", instance.get("bbox_scores", instance.get("score", 0.0))
    )
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        value = value[0] if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bbox(instance: dict[str, Any]) -> list[float] | None:
    value = instance.get("bbox", instance.get("bboxes"))
    if value is None:
        return None
    if hasattr(value, "tolist"):
        value = value.tolist()
    if len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = value[0]
    return [float(item) for item in value[:4]] if len(value) >= 4 else None


def select_instances(
    result: dict[str, Any], max_instances: int
) -> list[dict[str, Any]]:
    """信頼度の高い人物を上限まで残し、画面左から順に並べる。"""
    instances = sorted(_prediction_list(result), key=_bbox_score, reverse=True)
    instances = instances[:max_instances]
    return sorted(
        instances,
        key=lambda item: (_bbox(item) or [float("inf")])[0],
    )


def infer_frame(inferencer, frame, parameters: dict[str, Any]):
    generator = inferencer(
        frame,
        return_vis=False,
        bbox_thr=parameters["bbox_threshold"],
        nms_thr=parameters["nms_threshold"],
    )
    return select_instances(next(generator), parameters["max_instances"])


def instance_keypoints(instance: dict[str, Any]):
    keypoints = instance.get("keypoints")
    scores = instance.get("keypoint_scores")
    if hasattr(keypoints, "tolist"):
        keypoints = keypoints.tolist()
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    keypoints = keypoints or []
    scores = scores or []
    if keypoints and len(keypoints) == 1 and isinstance(keypoints[0][0], (list, tuple)):
        keypoints = keypoints[0]
    if scores and len(scores) == 1 and isinstance(scores[0], (list, tuple)):
        scores = scores[0]
    return keypoints, scores


def draw_pose(frame, instance: dict[str, Any], parameters: dict[str, Any]) -> None:
    keypoints, scores = instance_keypoints(instance)
    threshold = parameters["keypoint_threshold"]
    thickness = parameters["thickness"]

    for start, end in skeleton_for_model(parameters["model"]):
        if max(start, end) >= len(keypoints) or max(start, end) >= len(scores):
            continue
        if float(scores[start]) < threshold or float(scores[end]) < threshold:
            continue
        start_point = tuple(int(value) for value in keypoints[start][:2])
        end_point = tuple(int(value) for value in keypoints[end][:2])
        cv2.line(frame, start_point, end_point, (0, 255, 0), thickness)

    for keypoint, score in zip(keypoints, scores):
        if float(score) >= threshold:
            point = tuple(int(value) for value in keypoint[:2])
            cv2.circle(frame, point, parameters["radius"], (0, 0, 255), -1)

    if parameters["draw_bbox"]:
        bbox = _bbox(instance)
        if bbox:
            x1, y1, x2, y2 = (int(value) for value in bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 128, 0), thickness)


def draw_metadata(frame, metadata: dict[str, Any]) -> None:
    parameters = metadata["rtmpose_parameters"]
    lines = [
        (
            f"RTMPose {parameters['model']} | pose={metadata['used_device']} "
            f"detector={metadata.get('detector_device', metadata['used_device'])}"
        ),
        (
            f"people={parameters['max_instances']} "
            f"bbox={parameters['bbox_threshold']:.2f} "
            f"nms={parameters['nms_threshold']:.2f} "
            f"kpt={parameters['keypoint_threshold']:.2f}"
        ),
        f"landmarks={','.join(metadata['selected_landmarks']) or 'none'}",
    ]
    width = min(frame.shape[1] - 1, 760)
    cv2.rectangle(frame, (5, 5), (width, 72), (0, 0, 0), -1)
    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (12, 25 + index * 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def save_coordinate_graph(
    graph_data: dict[tuple[int, int], list[list[float]]],
    output_path: Path,
    landmark_id: int,
    metadata: dict[str, Any],
) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    landmark_data = {
        pose_id: values
        for (pose_id, current_id), values in graph_data.items()
        if current_id == landmark_id
    }
    for pose_id, values in landmark_data.items():
        times, x_values, y_values = values
        axes[0].plot(times, x_values, label=f"Pose {pose_id}", linewidth=0.8)
        axes[1].plot(times, y_values, label=f"Pose {pose_id}", linewidth=0.8)
    if len(landmark_data) > 1:
        for axis in axes:
            axis.legend()
    if not landmark_data:
        axes[0].text(
            0.5,
            0.5,
            "Pose keypoints were not detected",
            ha="center",
            va="center",
            transform=axes[0].transAxes,
        )
    axes[0].set_ylabel("x (normalized)")
    axes[1].set_ylabel("y (normalized)")
    axes[1].set_xlabel("Time (s)")
    figure.suptitle(f"RTMPose Coordinates - Keypoint {landmark_id}")
    figure.text(
        0.01,
        0.01,
        f"model={metadata['rtmpose_parameters']['model']} | device={metadata['used_device']}",
        fontsize=7,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def count_total_frames(video_path: str | Path) -> int:
    video = cv2.VideoCapture(str(video_path))
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) if video.isOpened() else 0
    video.release()
    return max(total, 1)


def normalize_video_writer_fps(source_fps: float) -> float:
    """OpenCV/FFmpegで安全に表現できる精度へ出力FPSを正規化する。"""
    try:
        fps = float(source_fps)
    except (TypeError, ValueError):
        return 30.0
    if not math.isfinite(fps) or fps <= 0:
        return 30.0
    # mp4vは小数3桁の高FPS（例: 239.483）を239483/1000として扱い、
    # MPEG-4のtimebase上限65535を超える。小数2桁なら時間精度を保ちつつ回避できる。
    return max(round(fps, 2), 0.01)


def create_output_video_writer(
    output_path: str | Path, source_fps: float, frame_size: tuple[int, int]
) -> tuple[Any, float]:
    output_fps = normalize_video_writer_fps(source_fps)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        output_fps,
        frame_size,
    )
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(
            f"出力動画を作成できませんでした: {output_path} "
            f"(source_fps={source_fps}, output_fps={output_fps})"
        )
    return writer, output_fps


def create_metadata(
    video_path: str | Path,
    parameters: dict[str, Any],
    output_settings: dict[str, Any],
    used_device: str,
) -> dict[str, Any]:
    landmarks = landmarks_for_model(parameters["model"])
    landmark_names = dict(landmarks)
    selected = {
        str(item): landmark_names[item] for item in output_settings["landmarks"]
    }
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_method": "mmpose_rtmpose_2d",
        "pose_layout": pose_layout_for_model(parameters["model"]),
        "source_video": str(Path(video_path).resolve()),
        "source_video_sha256": file_sha256(video_path),
        "script_sha256": file_sha256(__file__),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": {
            name: package_version(name)
            for name in (
                "torch",
                "mmengine",
                "mmcv",
                "mmdet",
                "mmpose",
                "opencv-contrib-python",
            )
        },
        "requested_device": parameters["device"],
        "used_device": used_device,
        "rtmpose_parameters": parameters,
        "output_settings": output_settings,
        "selected_landmarks": selected,
    }


def _open_csv_outputs(
    video_name: str,
    selected_landmarks: Iterable[int],
    enabled: bool,
    output_dir: Path,
):
    files: dict[int, Any] = {}
    writers: dict[int, Any] = {}
    if not enabled:
        return files, writers
    for landmark_id in selected_landmarks:
        path = output_dir / f"{video_name}_rtmpose_keypoint_{landmark_id}.csv"
        file = path.open("w", newline="", encoding="utf-8")
        writer = csv.writer(file)
        writer.writerow(
            [
                "frame",
                "time_seconds",
                "pose_id",
                "x",
                "y",
                "x_pixels",
                "y_pixels",
                "keypoint_score",
                "bbox_score",
            ]
        )
        files[landmark_id] = file
        writers[landmark_id] = writer
    return files, writers


def process_video(
    video_path: str | Path,
    parameters: dict[str, Any],
    output_settings: dict[str, Any],
    progress: ProgressWindow,
    output_dir: str | Path | None = None,
) -> None:
    total_started = perf_counter()
    video = cv2.VideoCapture(str(video_path))
    if not video.isOpened():
        raise RuntimeError(f"動画を開けませんでした: {video_path}")

    output_dir = Path(output_dir) if output_dir else OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    video_name = Path(video_path).stem
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    selected = output_settings["landmarks"]

    try:
        inferencer, used_device = create_inferencer(parameters)
        metadata = create_metadata(
            video_path, parameters, output_settings, used_device
        )
        metadata["detector_device"] = getattr(
            inferencer, "detector_device", used_device
        )
    except Exception:
        video.release()
        raise
    metadata["timing"] = {"started_at_utc": datetime.now(timezone.utc).isoformat()}
    metadata_path = output_dir / f"{video_name}_rtmpose_analysis_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    csv_files, csv_writers = _open_csv_outputs(
        video_name, selected, output_settings["csv"], output_dir
    )
    graph_data: dict[tuple[int, int], list[list[float]]] = {}
    output_video = None
    if output_settings["skeleton_video"]:
        video_output_path = output_dir / f"{video_name}_rtmpose_skeleton.mp4"
        try:
            output_video, output_video_fps = create_output_video_writer(
                video_output_path, fps, (width, height)
            )
            metadata["video"] = {
                "source_fps": fps,
                "output_fps": output_video_fps,
                "codec": "mp4v",
                "width": width,
                "height": height,
            }
        except RuntimeError:
            video.release()
            for file in csv_files.values():
                file.close()
            raise

    frame_number = 0
    inference_started = perf_counter()
    try:
        while not progress.is_canceled:
            success, frame = video.read()
            if not success:
                break
            instances = infer_frame(inferencer, frame, parameters)
            actual_device = getattr(inferencer, "used_device", used_device)
            if actual_device != used_device:
                used_device = actual_device
                metadata["used_device"] = actual_device
            metadata["detector_device"] = getattr(
                inferencer, "detector_device", used_device
            )
            time_seconds = frame_number / fps

            for pose_id, instance in enumerate(instances):
                keypoints, scores = instance_keypoints(instance)
                bbox_score = _bbox_score(instance)
                for landmark_id in selected:
                    if landmark_id >= len(keypoints) or landmark_id >= len(scores):
                        continue
                    x_pixels, y_pixels = (
                        float(value) for value in keypoints[landmark_id][:2]
                    )
                    score = float(scores[landmark_id])
                    x_normalized = x_pixels / width if width else 0.0
                    y_normalized = y_pixels / height if height else 0.0
                    if landmark_id in csv_writers:
                        csv_writers[landmark_id].writerow(
                            [
                                frame_number,
                                time_seconds,
                                pose_id,
                                x_normalized,
                                y_normalized,
                                x_pixels,
                                y_pixels,
                                score,
                                bbox_score,
                            ]
                        )
                    if output_settings["coordinate_graph"]:
                        values = graph_data.setdefault(
                            (pose_id, landmark_id), [[], [], []]
                        )
                        values[0].append(time_seconds)
                        values[1].append(x_normalized)
                        values[2].append(y_normalized)
                if output_video:
                    draw_pose(frame, instance, parameters)

            if not instances:
                for writer in csv_writers.values():
                    writer.writerow(
                        [frame_number, time_seconds, "", "", "", "", "", "", ""]
                    )

            if output_video:
                draw_metadata(frame, metadata)
                output_video.write(frame)

            frame_number += 1
            progress.update(frame_number, f"RTMPose解析中: {Path(video_path).name}")
    finally:
        inference_seconds = perf_counter() - inference_started
        video.release()
        for file in csv_files.values():
            file.close()
        if output_video:
            output_video.release()

    if output_settings["coordinate_graph"]:
        for landmark_id in selected:
            graph_path = output_dir / (
                f"{video_name}_rtmpose_keypoint_{landmark_id}_coordinates.png"
            )
            save_coordinate_graph(graph_data, graph_path, landmark_id, metadata)

    metadata.update(
        {
            "processed_frames": frame_number,
            "canceled": progress.is_canceled,
        }
    )
    metadata["timing"].update(
        {
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "inference_seconds": round(inference_seconds, 6),
            "effective_fps": round(frame_number / inference_seconds, 6)
            if inference_seconds > 0
            else 0.0,
            "total_processing_seconds": round(perf_counter() - total_started, 6),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[DEBUG] Finish RTMPose Analysis: {video_path}")


def main() -> None:
    video_paths, input_root, is_folder = get_video_selection()
    if not video_paths:
        return
    parameters = rtmpose_get_parameters()
    if parameters is None:
        return
    output_settings = get_output_settings(
        landmarks_for_model(parameters["model"]),
        item_label="キーポイント",
        video_label="RTMPose骨格線入り動画",
    )
    if output_settings is None:
        return
    root_path = Path(input_root) if is_folder and input_root else None
    for video_path_string in video_paths:
        video_path = Path(video_path_string)
        if root_path:
            relative_parent = video_path.parent.relative_to(root_path)
            output_dir = OUTPUTS_DIR / root_path.name / relative_parent
        else:
            output_dir = OUTPUTS_DIR
        with ProgressWindow(
            count_total_frames(video_path), f"RTMPose 解析: {video_path.name}"
        ) as progress:
            process_video(
                video_path, parameters, output_settings, progress, output_dir
            )
        if progress.is_canceled:
            break


if __name__ == "__main__":
    main()
