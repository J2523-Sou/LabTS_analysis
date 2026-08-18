import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lib.get_color_marker_parameters import get_color_marker_parameters
from lib.get_filepath import get_filepath
from lib.get_output_settings import get_output_settings
from lib.progress_window import ProgressWindow


OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "datas" / "outputs"


def file_sha256(file_path):
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_total_frames(video_path):
    video = cv2.VideoCapture(video_path)
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) if video.isOpened() else 0
    video.release()
    return max(total, 1)


def create_color_mask(frame, parameters, hsv=None):
    if hsv is None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue = parameters["target_hue"]
    tolerance = parameters["hue_tolerance"]
    min_saturation = parameters["min_saturation"]
    min_value = parameters["min_value"]
    lower_hue = hue - tolerance
    upper_hue = hue + tolerance

    def in_range(start, end):
        lower = np.array([start, min_saturation, min_value], dtype=np.uint8)
        upper = np.array([end, 255, 255], dtype=np.uint8)
        return cv2.inRange(hsv, lower, upper)

    if lower_hue < 0:
        mask = cv2.bitwise_or(
            in_range(0, upper_hue),
            in_range(180 + lower_hue, 179),
        )
    elif upper_hue > 179:
        mask = cv2.bitwise_or(
            in_range(lower_hue, 179),
            in_range(0, upper_hue - 180),
        )
    else:
        mask = in_range(lower_hue, upper_hue)

    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def detect_marker(frame, parameters, hsv=None):
    mask = create_color_mask(frame, parameters, hsv)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [
        contour
        for contour in contours
        if cv2.contourArea(contour) >= parameters["min_area"]
    ]
    if not contours:
        return None, None

    contour = max(contours, key=cv2.contourArea)
    moments = cv2.moments(contour)
    if moments["m00"] == 0:
        return None, None

    height, width = frame.shape[:2]
    x_pixel = int(moments["m10"] / moments["m00"])
    y_pixel = int(moments["m01"] / moments["m00"])
    marker = {
        "x_pixel": x_pixel,
        "y_pixel": y_pixel,
        "x": x_pixel / width,
        "y": y_pixel / height,
        "area": cv2.contourArea(contour),
    }
    return marker, contour


def calculate_rotation(marker, center):
    if marker is None or center is None:
        return None

    relative_x_pixels = marker["x_pixel"] - center["x_pixel"]
    relative_y_pixels = center["y_pixel"] - marker["y_pixel"]
    angle_degrees = (
        np.degrees(np.arctan2(relative_y_pixels, relative_x_pixels)) + 360
    ) % 360
    return {
        "relative_x": marker["x"] - center["x"],
        "relative_y": center["y"] - marker["y"],
        "relative_x_pixels": relative_x_pixels,
        "relative_y_pixels": relative_y_pixels,
        "radius_pixels": float(np.hypot(relative_x_pixels, relative_y_pixels)),
        "angle_degrees": float(angle_degrees),
    }


def draw_trail(frame, trail, color):
    visible_trail = trail[-100:]
    for start, end in zip(visible_trail, visible_trail[1:]):
        cv2.line(frame, start, end, color, 2)


def draw_tracking(
    frame,
    marker,
    marker_contour,
    center,
    center_contour,
    marker_trail,
    center_trail,
    rotation,
    parameters,
):
    if marker is not None:
        marker_point = (marker["x_pixel"], marker["y_pixel"])
        cv2.drawContours(frame, [marker_contour], -1, (0, 255, 255), 2)
        cv2.circle(frame, marker_point, 6, (0, 0, 255), -1)
        marker_trail.append(marker_point)

    if center is not None:
        center_point = (center["x_pixel"], center["y_pixel"])
        cv2.drawContours(frame, [center_contour], -1, (255, 255, 0), 2)
        cv2.circle(frame, center_point, 6, (255, 0, 0), -1)
        center_trail.append(center_point)

    draw_trail(frame, marker_trail, (255, 0, 255))
    draw_trail(frame, center_trail, (255, 255, 0))

    if rotation is not None:
        marker_point = (marker["x_pixel"], marker["y_pixel"])
        center_point = (center["x_pixel"], center["y_pixel"])
        cv2.line(frame, center_point, marker_point, (255, 255, 255), 2)

    marker_parameters = parameters["marker"]
    center_parameters = parameters["rotation_center"]
    marker_status = "OK" if marker is not None else "NG"
    center_status = "OK" if center is not None else "NG"
    cv2.rectangle(frame, (5, 5), (570, 75), (0, 0, 0), -1)
    cv2.putText(
        frame,
        (
            f"Marker: H={marker_parameters['target_hue']} {marker_status} | "
            f"Center: H={center_parameters['target_hue']} {center_status}"
        ),
        (12, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        (
            f"angle={rotation['angle_degrees']:.2f} deg "
            f"radius={rotation['radius_pixels']:.2f} px"
            if rotation is not None
            else "angle/radius: unavailable"
        ),
        (12, 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 0) if rotation is not None else (0, 0, 255),
        1,
        cv2.LINE_AA,
    )


def save_coordinate_graph(records, output_path, metadata):
    times = [record["time_seconds"] for record in records]
    marker_x = [
        record["marker"]["x"] if record["marker"] else np.nan
        for record in records
    ]
    marker_y = [
        record["marker"]["y"] if record["marker"] else np.nan
        for record in records
    ]
    center_x = [
        record["center"]["x"] if record["center"] else np.nan
        for record in records
    ]
    center_y = [
        record["center"]["y"] if record["center"] else np.nan
        for record in records
    ]
    radius = [
        record["rotation"]["radius_pixels"] if record["rotation"] else np.nan
        for record in records
    ]
    angle = [
        record["rotation"]["angle_degrees"] if record["rotation"] else np.nan
        for record in records
    ]

    figure, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(times, marker_x, label="Marker", linewidth=0.8)
    axes[0].plot(times, center_x, label="Center", linewidth=0.8)
    axes[1].plot(times, marker_y, label="Marker", linewidth=0.8)
    axes[1].plot(times, center_y, label="Center", linewidth=0.8)
    axes[2].plot(times, radius, linewidth=0.8)
    axes[3].plot(times, angle, linewidth=0.8)
    axes[0].legend()
    axes[1].legend()
    axes[0].set_ylabel("x (normalized)")
    axes[1].set_ylabel("y (normalized)")
    axes[2].set_ylabel("radius (px)")
    axes[3].set_ylabel("angle (deg)")
    axes[3].set_xlabel("Time (s)")
    axes[0].set_ylim(0, 1)
    axes[1].set_ylim(1, 0)
    axes[3].set_ylim(0, 360)
    marker_parameters = metadata["color_marker_parameters"]["marker"]
    center_parameters = metadata["color_marker_parameters"]["rotation_center"]
    timing = metadata["timing"]
    figure.suptitle("Color Marker and Rotation Center")
    figure.text(
        0.01,
        0.01,
        (
            f"marker_H={marker_parameters['target_hue']} | "
            f"center_H={center_parameters['target_hue']} | "
            f"processing={timing['frame_processing_seconds']:.3f}s"
        ),
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def create_metadata(video_path, parameters, output_settings, started_at):
    return {
        "created_at_utc": started_at.isoformat(),
        "source_video": str(Path(video_path).resolve()),
        "source_video_sha256": file_sha256(video_path),
        "script": str(Path(__file__).resolve()),
        "script_sha256": file_sha256(__file__),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "matplotlib_version": matplotlib.__version__,
        "color_marker_parameters": parameters,
        "output_settings": output_settings,
        "timing": {"started_at_utc": started_at.isoformat()},
    }


def process_video(video_path, parameters, output_settings, progress):
    total_started = perf_counter()
    started_at = datetime.now(timezone.utc)
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise RuntimeError(f"動画を開けませんでした: {video_path}")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    video_name = Path(video_path).stem
    fps = video.get(cv2.CAP_PROP_FPS) or 30
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    metadata = create_metadata(video_path, parameters, output_settings, started_at)
    metadata_path = OUTPUTS_DIR / f"{video_name}_marker_analysis_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    csv_file = None
    csv_writer = None
    if output_settings["csv"]:
        csv_path = OUTPUTS_DIR / f"{video_name}_marker.csv"
        csv_file = csv_path.open("w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            [
                "frame",
                "time_seconds",
                "marker_detected",
                "marker_x_pixel",
                "marker_y_pixel",
                "marker_x",
                "marker_y",
                "marker_area_pixels",
                "center_detected",
                "center_x_pixel",
                "center_y_pixel",
                "center_x",
                "center_y",
                "center_area_pixels",
                "relative_x_pixels",
                "relative_y_pixels",
                "relative_x",
                "relative_y",
                "radius_pixels",
                "angle_degrees",
            ]
        )

    output_video = None
    if output_settings["video"]:
        output_path = OUTPUTS_DIR / f"{video_name}_marker_tracking.mp4"
        output_video = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not output_video.isOpened():
            video.release()
            if csv_file:
                csv_file.close()
            raise RuntimeError(f"出力動画を作成できませんでした: {output_path}")

    records = []
    marker_trail = []
    center_trail = []
    frame_number = 0
    frame_processing_started = perf_counter()
    print(f"[DEBUG] Start Color Marker Tracking: {video_path}")

    try:
        while not progress.is_canceled:
            success, frame = video.read()
            if not success:
                break

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            marker, marker_contour = detect_marker(
                frame, parameters["marker"], hsv
            )
            center, center_contour = detect_marker(
                frame, parameters["rotation_center"], hsv
            )
            rotation = calculate_rotation(marker, center)
            time_seconds = frame_number / fps
            record = {
                "frame": frame_number,
                "time_seconds": time_seconds,
                "marker": marker,
                "center": center,
                "rotation": rotation,
            }
            records.append(record)

            if csv_writer:
                csv_writer.writerow(
                    [
                        frame_number,
                        time_seconds,
                        int(marker is not None),
                        marker["x_pixel"] if marker else "",
                        marker["y_pixel"] if marker else "",
                        marker["x"] if marker else "",
                        marker["y"] if marker else "",
                        marker["area"] if marker else "",
                        int(center is not None),
                        center["x_pixel"] if center else "",
                        center["y_pixel"] if center else "",
                        center["x"] if center else "",
                        center["y"] if center else "",
                        center["area"] if center else "",
                        rotation["relative_x_pixels"] if rotation else "",
                        rotation["relative_y_pixels"] if rotation else "",
                        rotation["relative_x"] if rotation else "",
                        rotation["relative_y"] if rotation else "",
                        rotation["radius_pixels"] if rotation else "",
                        rotation["angle_degrees"] if rotation else "",
                    ]
                )

            if output_video:
                draw_tracking(
                    frame,
                    marker,
                    marker_contour,
                    center,
                    center_contour,
                    marker_trail,
                    center_trail,
                    rotation,
                    parameters,
                )
                output_video.write(frame)

            frame_number += 1
            progress.update(frame_number, f"追跡中: {Path(video_path).name}")
    finally:
        frame_processing_seconds = perf_counter() - frame_processing_started
        video.release()
        if csv_file:
            csv_file.close()
        if output_video:
            output_video.release()

    metadata["processed_frames"] = frame_number
    metadata["marker_detected_frames"] = sum(
        record["marker"] is not None for record in records
    )
    metadata["center_detected_frames"] = sum(
        record["center"] is not None for record in records
    )
    metadata["rotation_calculated_frames"] = sum(
        record["rotation"] is not None for record in records
    )
    metadata["canceled"] = progress.is_canceled
    metadata["timing"].update(
        {
            "frame_processing_seconds": round(frame_processing_seconds, 6),
            "effective_fps": round(frame_number / frame_processing_seconds, 6)
            if frame_processing_seconds > 0
            else 0.0,
        }
    )

    if output_settings["coordinate_graph"]:
        graph_path = OUTPUTS_DIR / f"{video_name}_marker_coordinates.png"
        save_coordinate_graph(records, graph_path, metadata)

    metadata["timing"].update(
        {
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_processing_seconds": round(perf_counter() - total_started, 6),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[DEBUG] Finish Color Marker Tracking: {video_path}")


def main():
    video_path = get_filepath()
    if not video_path:
        return

    parameters = get_color_marker_parameters(video_path)
    if parameters is None:
        return

    output_settings = get_output_settings(video_label="マーカ追跡動画")
    if output_settings is None:
        return

    with ProgressWindow(count_total_frames(video_path), "色マーカ追跡") as progress:
        process_video(video_path, parameters, output_settings, progress)


if __name__ == "__main__":
    main()
