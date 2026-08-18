import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk


COLOR_PRESETS = {
    "赤": 0,
    "黄": 30,
    "緑": 60,
    "青": 120,
}


def sample_hsv(frame, x, y, radius=3):
    height, width = frame.shape[:2]
    x_start = max(0, x - radius)
    x_end = min(width, x + radius + 1)
    y_start = max(0, y - radius)
    y_end = min(height, y + radius + 1)
    patch = cv2.cvtColor(
        frame[y_start:y_end, x_start:x_end], cv2.COLOR_BGR2HSV
    ).reshape(-1, 3)

    hue_angles = patch[:, 0] * (2 * np.pi / 180)
    hue = int(
        round(
            np.arctan2(np.sin(hue_angles).mean(), np.cos(hue_angles).mean())
            % (2 * np.pi)
            * 180
            / (2 * np.pi)
        )
    ) % 180
    saturation = int(np.median(patch[:, 1]))
    value = int(np.median(patch[:, 2]))
    return hue, saturation, value


def display_to_frame_coordinates(
    display_x,
    display_y,
    display_width,
    display_height,
    frame_width,
    frame_height,
):
    display_x = max(0, min(display_x, display_width - 1))
    display_y = max(0, min(display_y, display_height - 1))
    x = min(int(display_x * frame_width / display_width), frame_width - 1)
    y = min(int(display_y * frame_height / display_height), frame_height - 1)
    return x, y


def get_color_marker_parameters(video_path=None):
    root = tk.Tk()
    root.title("色マーカ追跡設定")
    root.resizable(False, False)

    def create_variables(default_color):
        return {
            "color_name": tk.StringVar(value=default_color),
            "target_hue": tk.IntVar(value=COLOR_PRESETS[default_color]),
            "hue_tolerance": tk.IntVar(value=10),
            "min_saturation": tk.IntVar(value=100),
            "min_value": tk.IntVar(value=80),
            "min_area": tk.IntVar(value=100),
            "status": tk.StringVar(value="プリセットを使用"),
        }

    marker_variables = create_variables("緑")
    center_variables = create_variables("赤")
    result = None

    def apply_preset(variables):
        color_name = variables["color_name"].get()
        if color_name in COLOR_PRESETS:
            variables["target_hue"].set(COLOR_PRESETS[color_name])
            variables["status"].set(f"{color_name}プリセットを使用")

    def choose_from_video(variables, marker_title):
        if not video_path:
            messagebox.showwarning(
                "動画から色を選択",
                "先に解析動画を指定してください。",
                parent=root,
            )
            return

        video = cv2.VideoCapture(str(video_path))
        if not video.isOpened():
            messagebox.showerror(
                "動画から色を選択",
                "動画を開けませんでした。",
                parent=root,
            )
            return

        total_frames = max(int(video.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
        picker = tk.Toplevel(root)
        picker.title(f"動画から{marker_title}の色を選択")
        picker.resizable(False, False)
        picker.transient(root)
        picker.grab_set()

        tk.Label(
            picker,
            text=f"フレームを移動し、{marker_title}の中央をクリックしてください。",
        ).pack(padx=15, pady=(12, 5))
        canvas_frame = tk.Frame(picker)
        canvas_frame.pack(padx=15, pady=5)
        canvas = tk.Canvas(
            canvas_frame,
            width=800,
            height=500,
            bg="black",
            cursor="crosshair",
            highlightthickness=0,
        )
        horizontal_scrollbar = tk.Scrollbar(
            canvas_frame, orient="horizontal", command=canvas.xview
        )
        vertical_scrollbar = tk.Scrollbar(
            canvas_frame, orient="vertical", command=canvas.yview
        )
        canvas.configure(
            xscrollcommand=horizontal_scrollbar.set,
            yscrollcommand=vertical_scrollbar.set,
        )
        canvas.grid(row=0, column=0)
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        selected_text = tk.StringVar(value="色が選択されていません")
        selected_label = tk.Label(picker, textvariable=selected_text)
        selected_label.pack(fill="x", padx=15, pady=5)
        zoom = tk.DoubleVar(value=1.0)
        state = {"frame": None, "display_width": 1, "display_height": 1}

        def render_frame(_value=None):
            frame = state["frame"]
            if frame is None:
                return

            height, width = frame.shape[:2]
            scale = min(800 / width, 500 / height, 1.0) * zoom.get()
            display_width = max(1, int(width * scale))
            display_height = max(1, int(height * scale))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb).resize(
                (display_width, display_height), Image.Resampling.LANCZOS
            )
            photo = ImageTk.PhotoImage(image)
            canvas.delete("video_frame")
            canvas.create_image(
                0, 0, image=photo, anchor="nw", tags="video_frame"
            )
            canvas.image = photo
            canvas.configure(scrollregion=(0, 0, display_width, display_height))
            state.update(
                {
                    "display_width": display_width,
                    "display_height": display_height,
                }
            )

        def show_frame(frame_number):
            video.set(cv2.CAP_PROP_POS_FRAMES, int(float(frame_number)))
            success, frame = video.read()
            if not success:
                return
            state["frame"] = frame
            render_frame()

        def select_color(event):
            frame = state["frame"]
            if frame is None:
                return

            height, width = frame.shape[:2]
            x, y = display_to_frame_coordinates(
                canvas.canvasx(event.x),
                canvas.canvasy(event.y),
                state["display_width"],
                state["display_height"],
                width,
                height,
            )
            hue, saturation, value = sample_hsv(frame, x, y)
            variables["color_name"].set("動画から選択")
            variables["target_hue"].set(hue)
            variables["min_saturation"].set(max(0, saturation - 50))
            variables["min_value"].set(max(0, value - 50))
            variables["status"].set(f"H={hue} S={saturation} V={value}")

            preview_hsv = np.uint8([[[hue, saturation, value]]])
            red, green, blue = cv2.cvtColor(
                preview_hsv, cv2.COLOR_HSV2RGB
            )[0, 0]
            selected_label.config(bg=f"#{red:02x}{green:02x}{blue:02x}")
            selected_text.set(
                f"選択位置: ({x}, {y})  H={hue} S={saturation} V={value}"
            )
            print(
                f"[DEBUG] Selected {marker_title} Color: x={x}, y={y}, "
                f"H={hue}, S={saturation}, V={value}"
            )

        def close_picker():
            video.release()
            picker.grab_release()
            picker.destroy()

        canvas.bind("<Button-1>", select_color)
        tk.Scale(
            picker,
            variable=zoom,
            from_=1.0,
            to=5.0,
            resolution=0.25,
            orient="horizontal",
            length=500,
            label="拡大倍率",
            command=render_frame,
        ).pack(padx=15, pady=5)
        tk.Scale(
            picker,
            from_=0,
            to=total_frames - 1,
            orient="horizontal",
            length=500,
            label="フレーム番号",
            command=show_frame,
        ).pack(padx=15, pady=5)
        tk.Button(picker, text="設定へ戻る", command=close_picker, width=12).pack(
            pady=(5, 12)
        )
        picker.protocol("WM_DELETE_WINDOW", close_picker)
        show_frame(0)

    def add_marker_frame(parent, title, variables):
        frame = tk.LabelFrame(parent, text=title, padx=10, pady=8)
        frame.pack(side="left", padx=8, fill="y")

        tk.Label(frame, text="色プリセット").grid(row=0, column=0, sticky="e")
        preset_box = ttk.Combobox(
            frame,
            textvariable=variables["color_name"],
            values=list(COLOR_PRESETS),
            state="readonly",
            width=12,
        )
        preset_box.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        preset_box.bind(
            "<<ComboboxSelected>>", lambda _event: apply_preset(variables)
        )
        tk.Button(
            frame,
            text="動画から色を選択",
            command=lambda: choose_from_video(variables, title),
            width=20,
        ).grid(row=1, column=0, columnspan=2, pady=5)
        tk.Label(frame, textvariable=variables["status"]).grid(
            row=2, column=0, columnspan=2, pady=(0, 5)
        )

        sliders = [
            ("色相 H", "target_hue", 0, 179, 1),
            ("色相の許容幅", "hue_tolerance", 0, 40, 1),
            ("彩度 S の下限", "min_saturation", 0, 255, 5),
            ("明度 V の下限", "min_value", 0, 255, 5),
            ("最小面積（px）", "min_area", 10, 50000, 10),
        ]
        for row, (label, key, minimum, maximum, resolution) in enumerate(
            sliders, start=3
        ):
            tk.Label(frame, text=label).grid(row=row, column=0, sticky="e")
            tk.Scale(
                frame,
                variable=variables[key],
                from_=minimum,
                to=maximum,
                resolution=resolution,
                orient="horizontal",
                length=250,
            ).grid(row=row, column=1, padx=5)

    def values(variables):
        return {
            key: variable.get()
            for key, variable in variables.items()
            if key != "status"
        }

    def submit():
        nonlocal result
        result = {
            "marker": values(marker_variables),
            "rotation_center": values(center_variables),
        }
        print(f"[DEBUG] Color Marker Parameters: {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] Color Marker Settings Canceled")
        root.destroy()

    tk.Label(
        root,
        text="追跡するマーカと回転中心マーカを別々に設定してください。",
    ).pack(padx=15, pady=(12, 5))
    marker_frames = tk.Frame(root)
    marker_frames.pack(padx=10, pady=5)
    add_marker_frame(marker_frames, "追跡マーカ", marker_variables)
    add_marker_frame(marker_frames, "回転中心マーカ", center_variables)

    buttons = tk.Frame(root)
    buttons.pack(pady=12)
    tk.Button(buttons, text="決定", command=submit, width=10).pack(
        side="left", padx=5
    )
    tk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)
    print("[DEBUG] Open Color Marker Dialog")
    root.mainloop()
    print("[DEBUG] Close Color Marker Dialog")
    return result
