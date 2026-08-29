import tkinter as tk
from tkinter import messagebox, ttk


def rtmpose_get_parameters():
    """RTMPose/MMPoseの推論設定をGUIから取得する。"""
    root = tk.Tk()
    root.title("RTMPose 設定")
    root.resizable(False, False)

    model = tk.StringVar(value="human")
    detector = tk.StringVar(value="auto")
    max_instances = tk.IntVar(value=1)
    bbox_threshold = tk.DoubleVar(value=0.30)
    nms_threshold = tk.DoubleVar(value=0.30)
    keypoint_threshold = tk.DoubleVar(value=0.30)
    device = tk.StringVar(value="AUTO")
    cuda_index = tk.IntVar(value=0)
    draw_bbox = tk.BooleanVar(value=False)
    radius = tk.IntVar(value=4)
    thickness = tk.IntVar(value=2)
    result = None

    def submit():
        nonlocal result
        try:
            values = {
                "model": model.get().strip(),
                "detector": detector.get().strip(),
                "max_instances": max_instances.get(),
                "bbox_threshold": bbox_threshold.get(),
                "nms_threshold": nms_threshold.get(),
                "keypoint_threshold": keypoint_threshold.get(),
                "device": device.get(),
                "cuda_index": cuda_index.get(),
                "draw_bbox": draw_bbox.get(),
                "radius": radius.get(),
                "thickness": thickness.get(),
            }
        except tk.TclError:
            messagebox.showwarning(
                "RTMPose 設定", "数値項目を正しく入力してください。", parent=root
            )
            return

        if not values["model"] or not values["detector"]:
            messagebox.showwarning(
                "RTMPose 設定", "モデルと人物検出器を指定してください。", parent=root
            )
            return
        if values["max_instances"] < 1:
            messagebox.showwarning(
                "RTMPose 設定", "検出人数は1人以上にしてください。", parent=root
            )
            return

        result = values
        print(f"[DEBUG] RTMPose Parameters: {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] RTMPose Settings Canceled")
        root.destroy()

    padding = {"padx": 12, "pady": 5}
    ttk.Label(root, text="姿勢モデル").grid(row=0, column=0, sticky="e", **padding)
    ttk.Combobox(
        root,
        textvariable=model,
        values=[
            "human",
            "body26",
            "rtmpose-m_8xb256-420e_body8-256x192",
            "rtmpose-m_8xb512-700e_body8-halpe26-256x192",
        ],
        width=39,
    ).grid(row=0, column=1, columnspan=3, sticky="w", **padding)
    ttk.Label(root, text="人物検出器").grid(row=1, column=0, sticky="e", **padding)
    ttk.Combobox(root, textvariable=detector, values=["auto"], width=39).grid(
        row=1, column=1, columnspan=3, sticky="w", **padding
    )
    ttk.Label(
        root,
        text="モデル名・設定ファイルのパスを直接入力できます",
        foreground="#555555",
    ).grid(row=2, column=1, columnspan=3, sticky="w", padx=12)

    ttk.Label(root, text="検出する人数（上限）").grid(
        row=3, column=0, sticky="e", **padding
    )
    tk.Spinbox(root, from_=1, to=20, textvariable=max_instances, width=6).grid(
        row=3, column=1, sticky="w", **padding
    )

    sliders = [
        ("人物検出の信頼度", bbox_threshold),
        ("BBox NMS閾値", nms_threshold),
        ("キーポイント描画閾値", keypoint_threshold),
    ]
    for row, (label, variable) in enumerate(sliders, start=4):
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="e", **padding)
        tk.Scale(
            root,
            variable=variable,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            length=250,
        ).grid(row=row, column=1, columnspan=3, sticky="w", padx=8)

    ttk.Label(root, text="処理デバイス").grid(row=7, column=0, sticky="e", **padding)
    device_frame = ttk.Frame(root)
    device_frame.grid(row=7, column=1, columnspan=3, sticky="w", **padding)
    for label, value in [
        ("自動", "AUTO"),
        ("CPU", "CPU"),
        ("NVIDIA GPU (CUDA)", "CUDA"),
        ("Apple GPU (MPS)", "MPS"),
    ]:
        ttk.Radiobutton(
            device_frame, text=label, variable=device, value=value
        ).pack(side="left", padx=(0, 10))

    ttk.Label(root, text="CUDA GPU番号").grid(row=8, column=0, sticky="e", **padding)
    tk.Spinbox(root, from_=0, to=15, textvariable=cuda_index, width=6).grid(
        row=8, column=1, sticky="w", **padding
    )

    ttk.Checkbutton(root, text="人物BBoxを描画", variable=draw_bbox).grid(
        row=9, column=1, sticky="w", **padding
    )
    ttk.Label(root, text="点の半径").grid(row=10, column=0, sticky="e", **padding)
    tk.Spinbox(root, from_=1, to=20, textvariable=radius, width=6).grid(
        row=10, column=1, sticky="w", **padding
    )
    ttk.Label(root, text="線の太さ").grid(row=10, column=2, sticky="e", **padding)
    tk.Spinbox(root, from_=1, to=10, textvariable=thickness, width=6).grid(
        row=10, column=3, sticky="w", **padding
    )

    buttons = ttk.Frame(root)
    buttons.grid(row=11, column=0, columnspan=4, pady=12)
    ttk.Button(buttons, text="決定", command=submit, width=10).pack(
        side="left", padx=5
    )
    ttk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)
    print("[DEBUG] Open RTMPose Dialog")
    root.mainloop()
    print("[DEBUG] Close RTMPose Dialog")
    return result
