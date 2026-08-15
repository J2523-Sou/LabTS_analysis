import tkinter as tk
from tkinter import ttk


class ProgressWindow:
    def __init__(self, total, title="解析中"):
        self.total = max(int(total), 1)
        self.is_canceled = False
        self.is_closed = False

        self.root = tk.Tk()
        self.root.title(title)
        self.root.resizable(False, False)

        self.status_label = tk.Label(self.root, text="処理を開始します")
        self.status_label.pack(padx=20, pady=(15, 5))

        self.progress_bar = ttk.Progressbar(
            self.root,
            maximum=self.total,
            length=350,
            mode="determinate",
        )
        self.progress_bar.pack(padx=20, pady=5)

        self.count_label = tk.Label(self.root, text=f"0/{self.total} (0.0%)")
        self.count_label.pack(pady=5)

        self.cancel_button = tk.Button(
            self.root, text="キャンセル", command=self.cancel, width=12
        )
        self.cancel_button.pack(pady=(5, 15))

        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.root.update()
        print("[DEBUG] Open Progress Window")

    def update(self, current, message=""):
        if self.is_closed:
            return

        current = max(0, min(int(current), self.total))
        percent = current / self.total * 100

        self.progress_bar["value"] = current
        self.count_label.config(text=f"{current}/{self.total} ({percent:.1f}%)")

        if message:
            self.status_label.config(text=message)

        self.root.update()

    def cancel(self):
        if self.is_closed:
            return

        self.is_canceled = True
        self.status_label.config(text="キャンセルしています...")
        self.cancel_button.config(state="disabled")
        self.root.update_idletasks()
        print("[DEBUG] Processing Canceled")

    def close(self):
        if self.is_closed:
            return

        self.is_closed = True
        self.root.destroy()
        print("[DEBUG] Close Progress Window")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
