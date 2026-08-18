import tkinter as tk


def get_optical_flow_parameters():
    """Optical Flowの追跡間隔をGUIから取得する。キャンセル時はNoneを返す。"""
    root = tk.Tk()
    root.title("Optical Flow 設定")
    root.resizable(False, False)

    interval = tk.IntVar(value=5)
    result = None

    def submit():
        nonlocal result
        result = {"mediapipe_interval_frames": max(1, interval.get())}
        print(f"[DEBUG] Optical Flow Parameters: {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] Optical Flow Settings Canceled")
        root.destroy()

    tk.Label(root, text="MediaPipeを実行する間隔（フレーム）").pack(
        padx=20, pady=(15, 5)
    )
    tk.Spinbox(
        root,
        from_=1,
        to=300,
        textvariable=interval,
        width=8,
    ).pack(pady=5)
    tk.Label(
        root,
        text="間隔が大きいほど高速ですが、追跡誤差が増える場合があります。",
    ).pack(padx=20, pady=5)

    buttons = tk.Frame(root)
    buttons.pack(pady=(5, 15))
    tk.Button(buttons, text="決定", command=submit, width=10).pack(
        side="left", padx=5
    )
    tk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)
    print("[DEBUG] Open Optical Flow Settings")
    root.mainloop()
    print("[DEBUG] Close Optical Flow Settings")
    return result
