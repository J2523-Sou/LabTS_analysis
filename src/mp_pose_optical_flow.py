"""MediaPipe Pose を一定間隔で実行し、その間を Optical Flow で補間する解析。"""

import csv
from pathlib import Path
from time import perf_counter

import cv2
import mediapipe as mp
import numpy as np

from lib.get_filepath import get_filepath
from lib.get_output_settings import get_output_settings
from lib.mp_get_parameter import mp_get_parameters
from lib.optical_flow_get_parameter import get_optical_flow_parameters
from lib.progress_window import ProgressWindow
from mp_pose import (
    OUTPUTS_DIR,
    POSE_LANDMARKS,
    create_analysis_metadata,
    create_landmarker,
    draw_metadata,
    draw_skeleton,
    save_coordinate_graph,
    count_total_frames,
)


def process_video(video_path, parameters, output_settings, interval, progress):
    started = perf_counter()
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise RuntimeError(f"動画を開けませんでした: {video_path}")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    name = Path(video_path).stem
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    selected = output_settings["landmarks"]
    landmarker, delegate = create_landmarker(parameters)
    metadata = create_analysis_metadata(video_path, parameters, output_settings)
    metadata.update({"analysis_method": "mediapipe_periodic_optical_flow",
                     "mediapipe_interval_frames": interval,
                     "optical_flow": {"algorithm": "Lucas-Kanade", "window": [21, 21]}})
    metadata["requested_delegate"] = parameters["delegate"]
    metadata["used_delegate"] = delegate
    metadata["timing"] = {"started_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}

    writers, files, graphs = {}, {}, {}
    if output_settings["csv"]:
        for landmark_id in selected:
            path = OUTPUTS_DIR / f"{name}_landmark_{landmark_id}_optical_flow.csv"
            file = path.open("w", newline="", encoding="utf-8")
            writer = csv.writer(file)
            writer.writerow(["frame", "time_seconds", "pose_id", "x", "y", "z", "visibility", "presence", "source"])
            files[landmark_id], writers[landmark_id] = file, writer

    output_video = None
    if output_settings["skeleton_video"]:
        path = OUTPUTS_DIR / f"{name}_skeleton_optical_flow.mp4"
        output_video = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    previous_gray = None
    tracked = []
    frame_number = 0
    metadata_path = OUTPUTS_DIR / f"{name}_optical_flow_analysis_metadata.json"

    try:
        with landmarker:
            while not progress.is_canceled:
                ok, frame = video.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                use_mp = frame_number % interval == 0 or previous_gray is None or not tracked
                source = "mediapipe" if use_mp else "optical_flow"
                if use_mp:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = landmarker.detect_for_video(image, int(frame_number * 1000 / fps))
                    tracked = []
                    for pose in result.pose_landmarks:
                        points = [[p.x * width, p.y * height] for p in pose]
                        tracked.append({"points": points, "landmarks": pose})
                else:
                    for pose in tracked:
                        old = np.float32(pose["points"]).reshape(-1, 1, 2)
                        new, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, old, None, winSize=(21, 21), maxLevel=3)
                        if new is None:
                            pose["points"] = []
                        else:
                            pose["points"] = new.reshape(-1, 2).tolist()

                for pose_id, pose in enumerate(tracked):
                    if not pose["points"]:
                        continue
                    for landmark_id in selected:
                        x, y = pose["points"][landmark_id]
                        x_norm, y_norm = x / width, y / height
                        values = graphs.setdefault((pose_id, landmark_id), [[], [], [], []])
                        values[0].append(frame_number / fps); values[1].append(x_norm); values[2].append(y_norm); values[3].append(0.0)
                        if landmark_id in writers:
                            writers[landmark_id].writerow([frame_number, frame_number / fps, pose_id, x_norm, y_norm, "", "", "", source])
                    if output_video:
                        for x, y in pose["points"]:
                            cv2.circle(frame, (int(x), int(y)), 2, (0, 0, 255), -1)
                if output_video:
                    draw_metadata(frame, metadata); output_video.write(frame)
                previous_gray = gray
                frame_number += 1
                progress.update(frame_number, f"解析中: {name}")
    finally:
        video.release(); landmarker.close()
        for file in files.values(): file.close()
        if output_video: output_video.release()

    if output_settings["coordinate_graph"]:
        for landmark_id in selected:
            save_coordinate_graph(graphs, OUTPUTS_DIR / f"{name}_landmark_{landmark_id}_optical_flow_coordinates.png", landmark_id, metadata)
    metadata.update({"processed_frames": frame_number, "canceled": progress.is_canceled,
                     "timing": {"total_processing_seconds": round(perf_counter() - started, 6)}})
    metadata_path.write_text(__import__("json").dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    video_path = get_filepath()
    if not video_path: return
    parameters = mp_get_parameters()
    if parameters is None: return
    optical_flow_parameters = get_optical_flow_parameters()
    if optical_flow_parameters is None: return
    interval = optical_flow_parameters["mediapipe_interval_frames"]
    settings = get_output_settings(POSE_LANDMARKS)
    if settings is None: return
    with ProgressWindow(count_total_frames(video_path), "Pose + Optical Flow 解析") as progress:
        process_video(video_path, parameters, settings, interval, progress)


if __name__ == "__main__":
    main()
