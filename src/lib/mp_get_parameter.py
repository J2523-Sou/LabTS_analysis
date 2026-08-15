import tkinter as tk


def mp_get_parameters():
    root = tk.Tk()
    root.title("MediaPipe Pose 設定")
    root.resizable(False, False)

    num_poses = tk.IntVar(value=1)
    detection = tk.DoubleVar(value=0.5)
    presence = tk.DoubleVar(value=0.5)
    tracking = tk.DoubleVar(value=0.5)
    segmentation = tk.BooleanVar(value=False)
    delegate = tk.StringVar(value="CPU")
    model = tk.StringVar(value="lite")
    result = None

    def submit():
        nonlocal result
        result = {
            "num_poses": num_poses.get(),
            "min_pose_detection_confidence": detection.get(),
            "min_pose_presence_confidence": presence.get(),
            "min_tracking_confidence": tracking.get(),
            "output_segmentation_masks": segmentation.get(),
            "delegate": delegate.get(),
            "model": model.get(),
        }
        print(f"[DEBUG] Pose Parameters: {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] Pose Settings Canceled")
        root.destroy()

    tk.Label(root, text="検出する人数").grid(row=0, column=0, padx=15, pady=10)
    tk.Spinbox(root, from_=1, to=10, textvariable=num_poses, width=5).grid(
        row=0, column=1, sticky="w"
    )

    slider_items = [
        ("姿勢検出の信頼度", detection),
        ("姿勢存在の信頼度", presence),
        ("追跡の信頼度", tracking),
    ]

    for row, (label, variable) in enumerate(slider_items, start=1):
        tk.Label(root, text=label).grid(row=row, column=0, padx=15, pady=5)
        tk.Scale(
            root,
            variable=variable,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            length=250,
        ).grid(row=row, column=1, padx=10)

    tk.Checkbutton(
        root,
        text="セグメンテーションマスクを出力する",
        variable=segmentation,
    ).grid(row=4, column=0, columnspan=2, pady=10)

    model_frame = tk.Frame(root)
    model_frame.grid(row=5, column=0, columnspan=2, pady=5)
    tk.Label(model_frame, text="モデル").pack(side="left", padx=5)
    for label, value in [
        ("Lite（高速）", "lite"),
        ("Full（標準）", "full"),
        ("Heavy（精度重視）", "heavy"),
    ]:
        tk.Radiobutton(
            model_frame, text=label, variable=model, value=value
        ).pack(side="left")

    delegate_frame = tk.Frame(root)
    delegate_frame.grid(row=6, column=0, columnspan=2, pady=5)
    tk.Label(delegate_frame, text="処理デバイス").pack(side="left", padx=5)
    tk.Radiobutton(
        delegate_frame, text="CPU", variable=delegate, value="CPU"
    ).pack(side="left")
    tk.Radiobutton(
        delegate_frame, text="GPU（対応環境のみ）", variable=delegate, value="GPU"
    ).pack(side="left")

    buttons = tk.Frame(root)
    buttons.grid(row=7, column=0, columnspan=2, pady=10)
    tk.Button(buttons, text="決定", command=submit, width=10).pack(side="left", padx=5)
    tk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)

    print("[DEBUG] Open Dialog")
    root.mainloop()
    print("[DEBUG] Close Dialog")

    return result
