import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter
from urllib.request import urlretrieve

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mediapipe as mp

from lib.get_filepath import get_filepath
from lib.get_output_settings import get_output_settings
from lib.mp_get_parameter import mp_get_parameters
from lib.progress_window import ProgressWindow


MODEL_DIR = Path(__file__).parent / "models"
POSE_MODELS = {
    name: {
        "path": MODEL_DIR / f"pose_landmarker_{name}.task",
        "url": (
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            f"pose_landmarker_{name}/float16/latest/pose_landmarker_{name}.task"
        ),
    }
    for name in ("lite", "full", "heavy")
}
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "datas" / "outputs"
POSE_LANDMARKS = [
    (0, "鼻"),
    (1, "左目（内側）"),
    (2, "左目"),
    (3, "左目（外側）"),
    (4, "右目（内側）"),
    (5, "右目"),
    (6, "右目（外側）"),
    (7, "左耳"),
    (8, "右耳"),
    (9, "口（左）"),
    (10, "口（右）"),
    (11, "左肩"),
    (12, "右肩"),
    (13, "左肘"),
    (14, "右肘"),
    (15, "左手首"),
    (16, "右手首"),
    (17, "左小指"),
    (18, "右小指"),
    (19, "左人差し指"),
    (20, "右人差し指"),
    (21, "左親指"),
    (22, "右親指"),
    (23, "左腰"),
    (24, "右腰"),
    (25, "左膝"),
    (26, "右膝"),
    (27, "左足首"),
    (28, "右足首"),
    (29, "左かかと"),
    (30, "右かかと"),
    (31, "左つま先"),
    (32, "右つま先"),
]


def file_sha256(file_path):
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_analysis_metadata(video_path, parameters, output_settings):
    model_name = parameters.get("model", "lite")
    model = POSE_MODELS[model_name]
    landmark_names = dict(POSE_LANDMARKS)
    selected_landmarks = {
        str(landmark_id): landmark_names[landmark_id]
        for landmark_id in output_settings["landmarks"]
    }
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_video": str(Path(video_path).resolve()),
        "source_video_sha256": file_sha256(video_path),
        "model_variant": model_name,
        "model": str(model["path"].resolve()),
        "model_url": model["url"],
        "model_sha256": file_sha256(model["path"]),
        "script_sha256": file_sha256(__file__),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "mediapipe_version": mp.__version__,
        "opencv_version": cv2.__version__,
        "matplotlib_version": matplotlib.__version__,
        "pose_parameters": parameters,
        "output_settings": output_settings,
        "selected_landmarks": selected_landmarks,
    }


def metadata_summary(metadata):
    parameters = metadata["pose_parameters"]
    landmark_ids = ",".join(metadata["selected_landmarks"])
    frame_processing_seconds = metadata.get("timing", {}).get(
        "frame_processing_seconds"
    )
    timing_summary = (
        f" | processing={frame_processing_seconds:.3f}s"
        if frame_processing_seconds is not None
        else ""
    )
    return (
        f"MediaPipe {metadata['mediapipe_version']} | "
        f"model={Path(metadata['model']).name} | "
        f"device={metadata['used_delegate']} | "
        f"poses={parameters['num_poses']} | "
        f"detection={parameters['min_pose_detection_confidence']:.2f} | "
        f"presence={parameters['min_pose_presence_confidence']:.2f} | "
        f"tracking={parameters['min_tracking_confidence']:.2f} | "
        f"landmarks={landmark_ids or 'none'}"
        f"{timing_summary}"
    )


def draw_metadata(frame, metadata):
    parameters = metadata["pose_parameters"]
    lines = [
        (
            f"MediaPipe {metadata['mediapipe_version']} | "
            f"{Path(metadata['model']).name} | device={metadata['used_delegate']}"
        ),
        (
            f"poses={parameters['num_poses']} "
            f"det={parameters['min_pose_detection_confidence']:.2f} "
            f"pres={parameters['min_pose_presence_confidence']:.2f} "
            f"track={parameters['min_tracking_confidence']:.2f}"
        ),
        f"landmarks={','.join(metadata['selected_landmarks']) or 'none'}",
    ]
    cv2.rectangle(frame, (5, 5), (570, 72), (0, 0, 0), -1)
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

# モデル準備
def prepare_model(model_name):
    if model_name not in POSE_MODELS:
        raise ValueError(f"Unknown pose model: {model_name}")

    model = POSE_MODELS[model_name]
    if not model["path"].exists():
        print(f"[DEBUG] Download Pose Model: {model_name}")
        MODEL_DIR.mkdir(exist_ok=True)
        urlretrieve(model["url"], model["path"])
    return str(model["path"])


def gpu_platform_supported():
    if platform.system() == "Darwin":
        return True

    if platform.system() != "Linux":
        return False

    try:
        os_release = platform.freedesktop_os_release()
    except OSError:
        return False

    distribution = f"{os_release.get('ID', '')} {os_release.get('ID_LIKE', '')}"
    return "ubuntu" in distribution.lower()


def create_landmarker(parameters):
    pose_parameters = parameters.copy()
    requested_delegate = pose_parameters.pop("delegate")
    model_name = pose_parameters.pop("model", "lite")
    model_path = prepare_model(model_name)

    def create(delegate_name):
        delegate = getattr(mp.tasks.BaseOptions.Delegate, delegate_name)
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=model_path,
                delegate=delegate,
            ),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            **pose_parameters,
        )
        return mp.tasks.vision.PoseLandmarker.create_from_options(options)

    if requested_delegate == "GPU" and not gpu_platform_supported():
        print("[WARNING] MediaPipe GPU delegate is not supported on this platform")
        print("[WARNING] Fall back to CPU")
        return create("CPU"), "CPU"

    try:
        return create(requested_delegate), requested_delegate
    except RuntimeError as error:
        if requested_delegate != "GPU":
            raise

        print(f"[WARNING] GPU initialization failed: {error}")
        print("[WARNING] Fall back to CPU")
        return create("CPU"), "CPU"

# 骨格線の描画
def draw_skeleton(frame, pose_landmarks):
    height, width = frame.shape[:2]
    points = [(int(point.x * width), int(point.y * height)) for point in pose_landmarks]

    for connection in mp.tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS:
        cv2.line(frame, points[connection.start], points[connection.end], (0, 255, 0), 2)

    for point in points:
        cv2.circle(frame, point, 3, (0, 0, 255), -1)

# 座標グラフを保存
def save_coordinate_graph(graph_data, output_path, landmark_id, metadata):
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    landmark_data = {
        pose_id: values
        for (pose_id, current_id), values in graph_data.items()
        if current_id == landmark_id
    }

    if landmark_data:
        for pose_id, values in landmark_data.items():
            label = f"Pose {pose_id}"
            times, x_values, y_values, z_values = values
            axes[0].plot(times, x_values, label=label, linewidth=0.8)
            axes[1].plot(times, y_values, label=label, linewidth=0.8)
            axes[2].plot(times, z_values, label=label, linewidth=0.8)
        if len(landmark_data) > 1:
            for axis in axes:
                axis.legend()
    else:
        axes[1].text(
            0.5,
            0.5,
            "Pose landmarks were not detected",
            ha="center",
            va="center",
            transform=axes[1].transAxes,
        )

    axes[0].set_ylabel("x")
    axes[1].set_ylabel("y")
    axes[2].set_ylabel("z")
    axes[2].set_xlabel("Time (s)")
    figure.suptitle(f"Pose Coordinates - Landmark {landmark_id}")
    figure.text(0.01, 0.01, metadata_summary(metadata), fontsize=7)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

# 現在のフレーム数を取得
def count_total_frames(video_path):
    video = cv2.VideoCapture(video_path)
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) if video.isOpened() else 0
    video.release()
    return max(total, 1)

# 骨格推定本体
def process_video(video_path, parameters, output_settings, progress):
    total_processing_started = perf_counter()
    processing_started_at = datetime.now(timezone.utc)
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        print(f"[ERROR] 動画を開けませんでした: {video_path}")
        return

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    video_name = Path(video_path).stem
    fps = video.get(cv2.CAP_PROP_FPS) or 30
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))

    csv_files = {}
    csv_writers = {}
    output_video = None
    graph_data = {}
    selected_landmarks = output_settings["landmarks"]
    landmarker, used_delegate = create_landmarker(parameters)
    metadata = create_analysis_metadata(video_path, parameters, output_settings)
    metadata["requested_delegate"] = parameters["delegate"]
    metadata["used_delegate"] = used_delegate
    metadata["timing"] = {
        "started_at_utc": processing_started_at.isoformat(),
    }
    metadata_path = OUTPUTS_DIR / f"{video_name}_analysis_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if output_settings["csv"]:
        for landmark_id in selected_landmarks:
            csv_path = OUTPUTS_DIR / f"{video_name}_landmark_{landmark_id}.csv"
            csv_files[landmark_id] = csv_path.open(
                "w", newline="", encoding="utf-8"
            )
            csv_writers[landmark_id] = csv.writer(csv_files[landmark_id])
            csv_writers[landmark_id].writerow(
                [
                    "frame",
                    "time_seconds",
                    "pose_id",
                    "x",
                    "y",
                    "z",
                    "visibility",
                    "presence",
                ]
            )

    if output_settings["skeleton_video"]:
        output_path = OUTPUTS_DIR / f"{video_name}_skeleton.mp4"
        codec = cv2.VideoWriter_fourcc(*"mp4v")
        output_video = cv2.VideoWriter(
            str(output_path), codec, fps, (width, height)
        )
        if not output_video.isOpened():
            video.release()
            for csv_file in csv_files.values():
                csv_file.close()
            landmarker.close()
            raise RuntimeError(f"出力動画を作成できませんでした: {output_path}")

    frame_number = 0
    print(f"[DEBUG] Start Analysis: {video_path}")
    frame_processing_started = perf_counter()

    try:
        with landmarker:
            while not progress.is_canceled:
                success, frame = video.read()
                if not success:
                    break

                if used_delegate == "GPU":
                    input_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                    image_format = mp.ImageFormat.SRGBA
                else:
                    input_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image_format = mp.ImageFormat.SRGB

                mp_image = mp.Image(image_format=image_format, data=input_frame)
                timestamp_ms = int(frame_number * 1000 / fps)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)
                time_seconds = frame_number / fps

                for pose_id, pose_landmarks in enumerate(result.pose_landmarks):
                    draw_skeleton(frame, pose_landmarks)

                    for landmark_id in selected_landmarks:
                        landmark = pose_landmarks[landmark_id]

                        if landmark_id in csv_writers:
                            csv_writers[landmark_id].writerow(
                                [
                                    frame_number,
                                    time_seconds,
                                    pose_id,
                                    landmark.x,
                                    landmark.y,
                                    landmark.z,
                                    landmark.visibility,
                                    landmark.presence,
                                ]
                            )

                        if output_settings["coordinate_graph"]:
                            values = graph_data.setdefault(
                                (pose_id, landmark_id), [[], [], [], []]
                            )
                            values[0].append(time_seconds)
                            values[1].append(landmark.x)
                            values[2].append(landmark.y)
                            values[3].append(landmark.z)

                if not result.pose_landmarks:
                    for csv_writer in csv_writers.values():
                        csv_writer.writerow(
                            [frame_number, time_seconds, "", "", "", "", "", ""]
                        )

                if output_video:
                    draw_metadata(frame, metadata)
                    output_video.write(frame)

                frame_number += 1
                progress.update(
                    frame_number,
                    f"解析中: {Path(video_path).name}",
                )
    finally:
        frame_processing_seconds = perf_counter() - frame_processing_started
        video.release()
        for csv_file in csv_files.values():
            csv_file.close()
        if output_video:
            output_video.release()

    metadata["timing"].update(
        {
            "frame_processing_seconds": round(frame_processing_seconds, 6),
            "effective_fps": round(
                frame_number / frame_processing_seconds, 6
            )
            if frame_processing_seconds > 0
            else 0.0,
        }
    )

    if output_settings["coordinate_graph"]:
        for landmark_id in selected_landmarks:
            graph_path = (
                OUTPUTS_DIR / f"{video_name}_landmark_{landmark_id}_coordinates.png"
            )
            save_coordinate_graph(graph_data, graph_path, landmark_id, metadata)

    metadata["processed_frames"] = frame_number
    metadata["canceled"] = progress.is_canceled
    metadata["timing"].update(
        {
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_processing_seconds": round(
                perf_counter() - total_processing_started, 6
            ),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[DEBUG] Finish Analysis: {video_path}")


def main():
    video_path = get_filepath()
    if not video_path:
        return

    parameters = mp_get_parameters()
    if parameters is None:
        return

    output_settings = get_output_settings(POSE_LANDMARKS)
    if output_settings is None:
        return

    total_frames = count_total_frames(video_path)

    with ProgressWindow(total_frames, "MediaPipe Pose 解析") as progress:
        process_video(video_path, parameters, output_settings, progress)


if __name__ == "__main__":
    main()
