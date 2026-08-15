from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


INPUTS_DIR = Path(__file__).resolve().parents[2] / "datas" / "inputs"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def get_filepaths(multiple=True):
    root = tk.Tk()
    root.title("解析ファイル選択")
    root.resizable(False, False)

    use_inputs = tk.BooleanVar(value=False)
    selected_files = []
    selection_text = tk.StringVar(value="動画が選択されていません")
    result = []

    def select_files():
        file_types = [
            ("動画ファイル", "*.mp4 *.mov *.avi *.mkv"),
            ("すべてのファイル", "*.*"),
        ]
        if multiple:
            paths = filedialog.askopenfilenames(parent=root, filetypes=file_types)
        else:
            path = filedialog.askopenfilename(parent=root, filetypes=file_types)
            paths = (path,) if path else ()
        if paths:
            selected_files.clear()
            selected_files.extend(paths)
            use_inputs.set(False)
            selection_text.set(f"{len(paths)}件の動画を選択中")

    def submit():
        nonlocal result

        if use_inputs.get():
            result = []
            if INPUTS_DIR.exists():
                result = sorted(
                    str(path)
                    for path in INPUTS_DIR.iterdir()
                    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
                )
                if not multiple:
                    result = result[:1]
        else:
            result = selected_files.copy()

        if not result:
            messagebox.showwarning(
                "ファイル選択", "解析する動画が見つかりません。", parent=root
            )
            return

        print(f"[DEBUG] Selected Files ({len(result)}): {result}")
        root.destroy()

    def cancel():
        print("[DEBUG] File Selection Canceled")
        root.destroy()

    tk.Label(root, text="解析する動画を選択してください").pack(padx=20, pady=10)
    button_text = "動画を複数選択" if multiple else "動画を選択"
    tk.Button(root, text=button_text, command=select_files, width=20).pack(pady=5)
    tk.Label(root, textvariable=selection_text).pack(pady=5)
    inputs_text = (
        "datas/inputs 内の動画をすべて解析する"
        if multiple
        else "datas/inputs 内の先頭の動画を解析する"
    )
    tk.Checkbutton(
        root,
        text=inputs_text,
        variable=use_inputs,
    ).pack(padx=20, pady=10)

    buttons = tk.Frame(root)
    buttons.pack(pady=10)
    tk.Button(buttons, text="決定", command=submit, width=10).pack(side="left", padx=5)
    tk.Button(buttons, text="キャンセル", command=cancel, width=10).pack(
        side="left", padx=5
    )

    root.protocol("WM_DELETE_WINDOW", cancel)

    print("[DEBUG] Open Dialog")
    root.mainloop()
    print("[DEBUG] Close Dialog")

    return result


def get_filepath():
    """解析する動画を1つ選択して返す。"""
    filepaths = get_filepaths(multiple=False)
    return filepaths[0] if filepaths else ""
