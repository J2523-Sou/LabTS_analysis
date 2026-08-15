import tkinter as tk
from tkinter import filedialog


def select_file_path():
    root = tk.Tk()
    root.withdraw()

    file_types = [
        ("動画ファイル", "*.mp4 *.mov *.avi *.mkv"),
        ("CSVファイル", "*.csv"),
        ("Excelファイル", "*.xlsx"),
        ("すべてのファイル", "*.*"),
    ]

    print("[DEBUG] Open Dialog")

    file_path = filedialog.askopenfilename(filetypes=file_types)

    print("[DEBUG] Close Dialog")

    root.destroy()
    return file_path
