"""Extract data from text or binary ``.dat`` files.

Many instruments use the ``.dat`` extension for different formats.  This
module deliberately does not assume one vendor-specific binary layout:
delimited text files are converted to CSV, while binary files are exported as
a readable hexadecimal dump.  The functions are also usable from another
Python program.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Iterable, Sequence


TEXT_ENCODINGS = ("utf-8-sig", "cp932", "shift_jis", "latin-1")
DELIMITERS = ("\t", ",", ";", "|")


def _read_text(path: Path, encoding: str | None = None) -> tuple[str, str] | None:
    """Return decoded text and encoding, or ``None`` when the file is binary."""
    raw = path.read_bytes()
    if b"\x00" in raw:
        return None

    encodings = (encoding,) if encoding else TEXT_ENCODINGS
    for candidate in encodings:
        try:
            return raw.decode(candidate), candidate
        except UnicodeDecodeError:
            continue
    return None


def _detect_delimiter(lines: Sequence[str]) -> str | None:
    sample = "\n".join(line for line in lines if line.strip())[:8192]
    if not sample:
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,;|")
        return dialect.delimiter
    except csv.Error:
        counts = {delimiter: sum(line.count(delimiter) for line in lines) for delimiter in DELIMITERS}
        delimiter, count = max(counts.items(), key=lambda item: item[1])
        return delimiter if count else None


def parse_dat_text(text: str, delimiter: str | None = None) -> list[list[str]]:
    """Parse delimited or whitespace-separated text into rows.

    Blank lines and lines beginning with ``#`` or ``//`` are ignored.  A
    delimiter can be supplied explicitly; otherwise common delimiters are
    detected and plain whitespace is used as a fallback.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith(("#", "//"))]
    if not lines:
        return []

    delimiter = delimiter or _detect_delimiter(lines)
    if delimiter:
        return [next(csv.reader([line], delimiter=delimiter)) for line in lines]
    return [re.split(r"\s+", line) for line in lines]


def filter_force_rows(rows: Iterable[Sequence[str]]) -> list[list[str]]:
    """Return rows whose first field identifies them as a Force row."""
    result = []
    for row in rows:
        if row and row[0].strip().casefold().startswith("force"):
            result.append(list(row))
    return result


def write_hex_dump(data: bytes, output_path: Path, width: int = 16) -> None:
    """Write bytes as offsets, hexadecimal values, and printable text."""
    with output_path.open("w", encoding="ascii", newline="") as output:
        for offset in range(0, len(data), width):
            chunk = data[offset : offset + width]
            hex_part = " ".join(f"{byte:02x}" for byte in chunk).ljust(width * 3 - 1)
            text_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
            output.write(f"{offset:08x}  {hex_part}  |{text_part}|\n")


def extract_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    encoding: str | None = None,
    delimiter: str | None = None,
    mode: str = "auto",
    force_only: bool = False,
) -> str:
    """Extract one DAT file and return ``text`` or ``binary``."""
    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    decoded = _read_text(source, encoding)
    if mode == "binary" or (mode == "auto" and decoded is None):
        write_hex_dump(source.read_bytes(), destination)
        return "binary"
    if decoded is None:
        raise UnicodeError(f"テキストとして読み込めません: {source}")

    text, _ = decoded
    rows = parse_dat_text(text, delimiter)
    if force_only:
        rows = filter_force_rows(rows)
    width = max((len(row) for row in rows), default=0)
    with destination.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerows(row + [""] * (width - len(row)) for row in rows)
    return "text"


def _input_files(input_path: Path, recursive: bool) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
    elif input_path.is_dir():
        pattern = "**/*.dat" if recursive else "*.dat"
        yield from sorted(path for path in input_path.glob(pattern) if path.is_file())
    else:
        raise FileNotFoundError(f"入力が見つかりません: {input_path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=".dat ファイルを CSV または16進ダンプへ抽出します")
    parser.add_argument("input", type=Path, help=".dat ファイル、または格納ディレクトリ")
    parser.add_argument("-o", "--output", type=Path, help="出力ファイル／出力ディレクトリ（省略時: datas/outputs）")
    parser.add_argument("--encoding", help="テキストの文字コード（例: cp932）")
    parser.add_argument("--delimiter", choices=["tab", "comma", "semicolon", "pipe"], help="区切り文字")
    parser.add_argument("--mode", choices=["auto", "text", "binary"], default="auto")
    parser.add_argument("--force-only", action="store_true", help="Forceで始まる行だけを抽出")
    parser.add_argument("-r", "--recursive", action="store_true", help="ディレクトリを再帰的に検索")
    args = parser.parse_args(argv)

    delimiter = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|"}.get(args.delimiter)
    files = list(_input_files(args.input, args.recursive))
    if not files:
        print(".dat ファイルが見つかりません", file=sys.stderr)
        return 1

    default_output = Path(__file__).resolve().parents[1] / "datas" / "outputs"
    output = args.output or default_output
    single_file = len(files) == 1 and (not args.input.is_dir()) and output.suffix
    for source in files:
        if single_file:
            destination = output
        else:
            output.mkdir(parents=True, exist_ok=True)
            is_binary = args.mode == "binary" or (
                args.mode == "auto" and _read_text(source, args.encoding) is None
            )
            suffix = ".hex" if is_binary else ".csv"
            destination = output / f"{source.stem}_extracted{suffix}"
        kind = extract_file(
            source,
            destination,
            encoding=args.encoding,
            delimiter=delimiter,
            mode=args.mode,
            force_only=args.force_only,
        )
        print(f"{source} -> {destination} ({kind})")
    return 0


def gui_main() -> None:
    """Launch the file-selection GUI."""
    root = tk.Tk()
    root.title("DATファイル抽出")
    root.resizable(False, False)

    selected: list[Path] = []
    files_text = tk.StringVar(value="ファイルが選択されていません")
    output_text = tk.StringVar(value="datas/outputs")
    encoding_text = tk.StringVar(value="自動判定")
    mode_text = tk.StringVar(value="auto")
    delimiter_text = tk.StringVar(value="自動判定")
    force_only = tk.BooleanVar(value=True)

    def choose_files() -> None:
        paths = filedialog.askopenfilenames(
            parent=root,
            title="抽出するDATファイルを選択",
            filetypes=[("DATファイル", "*.dat"), ("すべてのファイル", "*.*")],
        )
        if paths:
            selected[:] = [Path(path) for path in paths]
            files_text.set(f"{len(selected)}件選択中: {selected[0].name}")

    def choose_directory() -> None:
        path = filedialog.askdirectory(parent=root, title="出力先フォルダを選択")
        if path:
            output_text.set(path)

    def extract() -> None:
        if not selected:
            messagebox.showwarning("DATファイル抽出", "DATファイルを選択してください。", parent=root)
            return
        output = Path(output_text.get())
        if not output.is_absolute():
            output = Path(__file__).resolve().parents[1] / output
        delimiter = {"タブ": "\t", "カンマ": ",", "セミコロン": ";", "パイプ": "|"}.get(delimiter_text.get())
        encoding = None if encoding_text.get() == "自動判定" else encoding_text.get()
        try:
            output.mkdir(parents=True, exist_ok=True)
            results = []
            for source in selected:
                is_binary = mode_text.get() == "binary" or (
                    mode_text.get() == "auto" and _read_text(source, encoding) is None
                )
                suffix = ".hex" if is_binary else ".csv"
                destination = output / f"{source.stem}_extracted{suffix}"
                kind = extract_file(
                    source,
                    destination,
                    encoding=encoding,
                    delimiter=delimiter,
                    mode=mode_text.get(),
                    force_only=force_only.get(),
                )
                results.append(f"{source.name} → {destination.name} ({kind})")
        except (OSError, UnicodeError, csv.Error) as exc:
            messagebox.showerror("抽出エラー", str(exc), parent=root)
            return
        messagebox.showinfo("抽出完了", "\n".join(results), parent=root)

    frame = ttk.Frame(root, padding=16)
    frame.grid()
    ttk.Label(frame, text="DATファイルを選択してください").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Button(frame, text="ファイルを選択", command=choose_files).grid(row=1, column=0, pady=8, sticky="w")
    ttk.Label(frame, textvariable=files_text, width=42).grid(row=1, column=1, padx=(10, 0), sticky="w")
    ttk.Label(frame, text="出力先").grid(row=2, column=0, sticky="w")
    ttk.Entry(frame, textvariable=output_text, width=34).grid(row=2, column=1, sticky="w")
    ttk.Button(frame, text="参照", command=choose_directory).grid(row=2, column=2, padx=(6, 0))
    ttk.Label(frame, text="文字コード").grid(row=3, column=0, pady=(10, 0), sticky="w")
    ttk.Combobox(frame, textvariable=encoding_text, values=["自動判定", "utf-8", "cp932", "shift_jis"], state="readonly", width=15).grid(row=3, column=1, pady=(10, 0), sticky="w")
    ttk.Label(frame, text="区切り文字").grid(row=4, column=0, sticky="w")
    ttk.Combobox(frame, textvariable=delimiter_text, values=["自動判定", "タブ", "カンマ", "セミコロン", "パイプ"], state="readonly", width=15).grid(row=4, column=1, sticky="w")
    ttk.Label(frame, text="形式").grid(row=5, column=0, sticky="w")
    ttk.Combobox(frame, textvariable=mode_text, values=["auto", "text", "binary"], state="readonly", width=15).grid(row=5, column=1, sticky="w")
    ttk.Checkbutton(frame, text="Force行のみ抽出", variable=force_only).grid(row=6, column=0, columnspan=2, pady=(8, 0), sticky="w")
    ttk.Button(frame, text="抽出開始", command=extract).grid(row=7, column=0, columnspan=3, pady=(16, 0))
    root.mainloop()


if __name__ == "__main__":
    # 引数があればCLI、なければGUIとして起動する。
    if len(sys.argv) > 1:
        raise SystemExit(main())
    gui_main()
