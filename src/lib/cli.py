"""各解析スクリプトで共通利用する対話式CLI。"""

from pathlib import Path
import sys
from time import monotonic


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def cli_requested() -> bool:
    return "--cli" in sys.argv[1:]


class CliProgressWindow:
    """ProgressWindowと同じインターフェースを持つターミナル用進捗表示。"""

    def __init__(self, total, title="解析中"):
        self.total = max(int(total), 1)
        self.title = title
        self.is_canceled = False
        self.is_closed = False
        self.started = monotonic()
        self.last_reported = -1
        print(f"{title}: 0/{self.total} (0.0%)")

    def update(self, current, message=""):
        if self.is_closed:
            return
        current = max(0, min(int(current), self.total))
        step = max(1, self.total // 100)
        if current != self.total and current - self.last_reported < step:
            return
        self.last_reported = current
        percent = current / self.total * 100
        elapsed = monotonic() - self.started
        suffix = f" | {message}" if message else ""
        print(
            f"\r{self.title}: {current}/{self.total} ({percent:.1f}%) "
            f"elapsed={elapsed:.1f}s{suffix}",
            end="",
            flush=True,
        )
        if current == self.total:
            print()

    def cancel(self):
        self.is_canceled = True

    def close(self):
        if not self.is_closed:
            self.is_closed = True
            print()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def select_videos_cli() -> tuple[list[Path], Path | None]:
    raw = input("動画またはフォルダーのパス: ").strip().strip('"')
    path = Path(raw).expanduser()
    if path.is_dir():
        videos = sorted(
            item for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        )
        return videos, path
    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
        return [path], None
    print("動画またはフォルダーが見つかりません。")
    return [], None


def ask(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def ask_int(prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        try:
            value = int(ask(prompt, str(default)))
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"{minimum}以上の整数を入力してください。")


def ask_float(prompt: str, default: float, minimum: float = 0.0, maximum=None) -> float:
    while True:
        try:
            value = float(ask(prompt, str(default)))
            if value >= minimum and (maximum is None or value <= maximum):
                return value
        except ValueError:
            pass
        print("有効な数値を入力してください。")


def ask_bool(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "はい"}:
            return True
        if value in {"n", "no", "いいえ"}:
            return False


def output_settings_cli(landmarks=None, video_key="skeleton_video"):
    result = {
        "csv": ask_bool("CSVを出力", False),
        "coordinate_graph": ask_bool("座標グラフを出力", False),
        video_key: ask_bool("動画を出力", False),
    }
    if landmarks:
        default = " ".join(str(item[0]) for item in landmarks)
        raw = ask("出力するキーポイント番号（空白区切り）", default)
        try:
            result["landmarks"] = [int(item) for item in raw.split()]
            valid = {item[0] for item in landmarks}
            result["landmarks"] = [item for item in result["landmarks"] if item in valid]
        except ValueError:
            result["landmarks"] = []
    else:
        result["landmarks"] = []
    if not any(result[key] for key in ("csv", "coordinate_graph", video_key)):
        print("出力が選択されていないため、動画出力を有効にします。")
        result[video_key] = True
    return result


def mediapipe_parameters_cli() -> dict:
    return {
        "num_poses": ask_int("検出する人数", 1, 1),
        "min_pose_detection_confidence": ask_float("姿勢検出の信頼度", 0.5, 0, 1),
        "min_pose_presence_confidence": ask_float("姿勢存在の信頼度", 0.5, 0, 1),
        "min_tracking_confidence": ask_float("追跡の信頼度", 0.5, 0, 1),
        "output_segmentation_masks": ask_bool("セグメンテーションマスクを出力", False),
        "delegate": ask("処理デバイス (CPU/GPU)", "CPU").upper(),
        "model": ask("モデル (lite/full/heavy)", "lite"),
    }
