髙橋湊研究（室）　自転車プロジェクト解析プログラム

使用方法

```python
from src.lib.tkinter_lib import select_file_path

file_path = select_file_path()

if file_path:
    print(file_path)
```

ファイル選択をキャンセルした場合は、空文字列 (`""`) が返ります。
