import tkinter as tk
from tkinter import messagebox


def get_output_settings(
    landmarks=None,
    item_label="ランドマーク",
    video_label="骨格線入り動画",
):
    landmarks = landmarks or []
    root = tk.Tk()
    root.title("出力設定")
    root.resizable(False, False)

    csv_output = tk.BooleanVar(value=False)
    graph_output = tk.BooleanVar(value=False)
    video_output = tk.BooleanVar(value=False)
    result = None
    landmark_list = None

    def select_all():
        landmark_list.selection_set(0, tk.END)

    def clear_all():
        landmark_list.selection_clear(0, tk.END)

    def submit():
        nonlocal result
        selected_landmarks = (
            [landmarks[index][0] for index in landmark_list.curselection()]
            if landmark_list is not None
            else []
        )

        result = {
            "csv": csv_output.get(),
            "coordinate_graph": graph_output.get(),
            "landmarks": selected_landmarks,
        }
        video_key = "skeleton_video" if landmarks else "video"
        result[video_key] = video_output.get()

        if not any((result["csv"], result["coordinate_graph"], video_output.get())):
            messagebox.showwarning(
                "出力設定", "出力方法を1つ以上選択してください。", parent=root
            )
            result = None
            return

        if (
            landmarks
            and (result["csv"] or result["coordinate_graph"])
            and not selected_landmarks
        ):
            messagebox.showwarning(
                "出力設定",
                f"出力する{item_label}を1つ以上選択してください。",
                parent=root,
            )
            result = None
            return

        print(f"[DEBUG] Output Settings: {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] Output Settings Canceled")
        root.destroy()

    tk.Label(root, text="出力方法").pack(padx=20, pady=(10, 5))
    tk.Checkbutton(root, text="CSV", variable=csv_output).pack(anchor="w", padx=30)
    tk.Checkbutton(root, text="座標グラフ", variable=graph_output).pack(
        anchor="w", padx=30
    )
    tk.Checkbutton(root, text=video_label, variable=video_output).pack(
        anchor="w", padx=30
    )

    if landmarks:
        tk.Label(root, text=f"出力する{item_label}（複数選択可）").pack(
            padx=20, pady=(15, 5)
        )

        list_frame = tk.Frame(root)
        list_frame.pack(padx=20)
        landmark_list = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            width=32,
            height=14,
            exportselection=False,
        )
        scrollbar = tk.Scrollbar(list_frame, command=landmark_list.yview)
        landmark_list.config(yscrollcommand=scrollbar.set)
        landmark_list.pack(side="left", fill="both")
        scrollbar.pack(side="right", fill="y")

        for landmark_id, landmark_name in landmarks:
            landmark_list.insert(tk.END, f"{landmark_id}: {landmark_name}")

        selection_buttons = tk.Frame(root)
        selection_buttons.pack(pady=5)
        tk.Button(selection_buttons, text="すべて選択", command=select_all).pack(
            side="left", padx=5
        )
        tk.Button(selection_buttons, text="選択解除", command=clear_all).pack(
            side="left", padx=5
        )

    buttons = tk.Frame(root)
    buttons.pack(pady=10)
    tk.Button(buttons, text="決定", command=submit, width=10).pack(
        side="left", padx=5
    )
    tk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)
    print("[DEBUG] Open Dialog")
    root.mainloop()
    print("[DEBUG] Close Dialog")
    return result
