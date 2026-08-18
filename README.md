# LabTS Analysis

MediaPipe Poseによる骨格推定と、HSV色空間による色マーカ追跡を行う研究用プログラムです。
Tkinterの画面から入力動画、解析条件、出力方法を指定できます。

## 動作環境

- 動作確認済みPython: **3.10.21**
- 対応方針: **Python 3.10.x**を推奨
- GUI: Tkinter（Python標準ライブラリ。ただしTcl/Tkの追加導入が必要な環境があります）
- 対応入力形式: `.mp4`、`.mov`、`.avi`、`.mkv`

動画を読み書きできるかどうかは、OSとOpenCVが利用できる動画コーデックにも依存します。
このプログラムは画面を表示するため、GUIを利用できないサーバーやSSHのヘッドレス環境では
そのまま実行できません。

## ディレクトリ構成

```text
LabTS_analysis/
├── datas/
│   ├── inputs/                 # 解析する動画を置く場所（任意）
│   └── outputs/                # 解析結果
├── src/
│   ├── lib/
│   │   ├── get_filepath.py     # 動画選択
│   │   ├── get_output_settings.py
│   │   ├── mp_get_parameter.py # Pose設定
│   │   ├── get_color_marker_parameters.py # 色マーカ設定
│   │   └── progress_window.py  # 進捗表示
│   ├── models/                 # MediaPipeモデルの保存先
│   ├── color_marker.py          # 色マーカ追跡スクリプト
│   └── mp_pose.py              # 実行スクリプト
├── requirements.txt
└── README.md
```

`datas/`、`.venv/`、`src/models/`はGitの管理対象外です。存在しない場合、
`datas/inputs/`は必要に応じて作成してください。`datas/outputs/`と`src/models/`は
実行時に自動作成されます。

## 1. PythonとTkinterのインストール

Tkinterは`requirements.txt`からはインストールできません。`pip install tkinter`も不要です。
OSに合わせてPython 3.10とTcl/Tkを用意してください。

### macOS（Homebrew）

[Homebrew](https://brew.sh/)を導入済みのターミナルで実行します。

```bash
brew install python@3.10 python-tk@3.10
python3.10 --version
python3.10 -m tkinter
```

最後のコマンドで小さなTkウィンドウが開けば利用できます。Homebrewには
[`python-tk@3.10`](https://formulae.brew.sh/formula/python-tk%403.10)が用意されています。

### Ubuntu 22.04

Ubuntu 22.04では標準のPython 3.10を利用できます。

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-tk libgl1
python3.10 --version
python3.10 -m tkinter
```

Tkウィンドウが開けば利用できます。リモート環境ではデスクトップ表示環境も必要です。

### Windows 10／11

1. [Python 3.10.11公式ダウンロードページ](https://www.python.org/downloads/release/python-31011/)から
   `Windows installer (64-bit)`を取得します。
2. インストーラーで`Add Python to PATH`を有効にします。
3. `Tcl/Tk and IDLE`を含めてインストールします。
4. PowerShellで次を確認します。

```powershell
py -3.10 --version
py -3.10 -m tkinter
```

Tkウィンドウが開けば利用できます。

Python公式ドキュメントでも、`python -m tkinter`でTkinterの導入状態とTcl/Tkの
バージョンを確認する方法が案内されています。

## 2. 仮想環境の作成

リポジトリをダウンロードまたはクローンし、プロジェクト直下へ移動して実行します。
仮想環境は、プロジェクトで使うパッケージを他のPython環境から分離するためのものです。

### macOS／Linux

```bash
cd LabTS_analysis
python3.10 -m venv .venv
source .venv/bin/activate
python --version
```

### Windows PowerShell

```powershell
cd LabTS_analysis
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python --version
```

PowerShellでスクリプト実行が禁止されている場合は、コマンドプロンプトで次を実行します。

```bat
.venv\Scripts\activate.bat
```

有効化されると、通常はターミナルの先頭に`(.venv)`と表示されます。終了するときは
次を実行します。

```bash
deactivate
```

仮想環境の仕組みとOS別の有効化方法は
[Python公式venvドキュメント](https://docs.python.org/3.10/tutorial/venv.html)でも確認できます。

## 3. 依存関係のインストール

仮想環境を有効にした状態で実行します。

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

`No broken requirements found.`と表示されれば、依存関係に矛盾はありません。
`requirements.txt`にはMediaPipe、OpenCV、Matplotlibと間接依存パッケージを
すべて固定バージョンで記載しています。同じ条件を再現するため、導入後に個別パッケージを
無断で更新しないでください。

主要パッケージは次のとおりです。

| パッケージ | 用途 |
| --- | --- |
| `mediapipe` | 姿勢推定 |
| `opencv-contrib-python` | 動画の読み込み、描画、動画出力 |
| `matplotlib` | 座標グラフの出力 |

## 4. mp_pose.pyの実行

仮想環境を有効にして、プロジェクト直下で実行します。

```bash
python src/mp_pose.py
```

仮想環境を有効にせず直接実行する場合は次のとおりです。

macOS／Linux:

```bash
.venv/bin/python src/mp_pose.py
```

Windows:

```powershell
.venv\Scripts\python.exe src\mp_pose.py
```

### 画面操作の流れ

1. **動画選択**
   - `動画を選択`から解析する動画を1本選択します。
   - `datas/inputs 内の先頭の動画を解析する`を有効にすると、対応形式のファイルを
     ファイル名順に並べた先頭の1本を使用します。
2. **MediaPipe Pose設定**
   - 検出人数、3種類の信頼度、セグメンテーションマスク、モデル、CPU／GPUを指定します。
3. **出力設定**
   - CSV、座標グラフ、骨格線入り動画から1つ以上選択します。
   - CSVまたはグラフを選ぶ場合、出力するランドマークも1つ以上選択します。
4. **解析**
   - 動画を1フレームずつ処理し、進捗を表示します。
   - `キャンセル`を押すと、現在のフレーム処理後に終了します。

現在の`mp_pose.py`が一度に解析する動画は1本です。複数選択用のライブラリ関数はありますが、
この実行スクリプトでは使用していません。

## 5. 色マーカ追跡の実行

色の付いたマーカを動画から追跡する場合は、プロジェクト直下で実行します。

```bash
python src/color_marker.py
```

画面操作は次の順番です。

1. 解析する動画を1本選択します。
2. 追跡マーカと回転中心マーカの色を、プリセットまたは動画上のクリックで指定します。
3. CSV、座標グラフ、マーカ追跡動画から1つ以上選択します。
4. 進捗画面を確認しながら解析します。

色マーカ解析にはランドマーク選択画面は表示されません。追跡マーカと回転中心マーカを
それぞれ1個ずつ追跡します。同じ色条件を満たす領域が複数ある場合は、その色で面積が
最大の領域を採用します。

### 色マーカのパラメータ

| 項目 | 初期値 | 説明 |
| --- | ---: | --- |
| 色プリセット | 追跡: 緑、中心: 赤 | 赤、黄、緑、青から基準色を選択 |
| 色相 H | 追跡: `60`、中心: `0` | OpenCVのHSV色相。`0〜179` |
| 色相の許容幅 | `10` | 基準色相から検出する範囲 |
| 彩度 S の下限 | `100` | 値が大きいほど鮮やかな色だけを検出 |
| 明度 V の下限 | `80` | 値が大きいほど明るい色だけを検出 |
| 最小面積 | `100 px` | 小さなノイズをマーカとして採用しないための面積 |

プリセットを選ぶと色相Hが更新されます。その後、実際の照明やカメラの色に合わせてHを
微調整できます。赤色は色相の`0`と`179`をまたぐ範囲にも対応しています。

追跡マーカ側または回転中心マーカ側の`動画から色を選択`を押すと、選択済み動画のフレームが
表示されます。スライダーで各マーカが見やすいフレームへ移動し、マーカ中央をクリックして
ください。周囲7×7ピクセルから代表HSV値を計算し、選択した側の色相と彩度・明度の下限へ
反映します。小さいマーカは拡大倍率を最大5倍まで上げ、縦横のスクロールバーで表示位置を
移動して選択できます。設定画面へ戻った後も、2つのマーカを個別に調整できます。

各フレームでは、2色それぞれについてHSVによる色抽出、5×5カーネルによるノイズ除去、
輪郭抽出、最大輪郭の重心計算を行います。両方を検出したフレームでは、回転中心から
追跡マーカまでの相対座標、半径、回転角度も計算します。追跡動画には両方の輪郭、重心、
直近100点の軌跡、中心と追跡点を結ぶ線を描画します。

結果は`datas/outputs/`へ保存されます。

| ファイル | 内容 |
| --- | --- |
| `<動画名>_marker.csv` | 両マーカの重心、相対座標、半径、回転角度 |
| `<動画名>_marker_coordinates.png` | 両マーカの座標、半径、回転角度のグラフ |
| `<動画名>_marker_tracking.mp4` | 両マーカの輪郭、重心、軌跡、回転情報を描いた動画 |
| `<動画名>_marker_analysis_metadata.json` | 色条件、出力設定、SHA-256、処理時間 |

CSVの1行目は次のヘッダーです。未検出フレームも記録し、座標と面積は空欄になります。

```text
frame,time_seconds,marker_detected,marker_x_pixel,marker_y_pixel,marker_x,marker_y,marker_area_pixels,center_detected,center_x_pixel,center_y_pixel,center_x,center_y,center_area_pixels,relative_x_pixels,relative_y_pixels,relative_x,relative_y,radius_pixels,angle_degrees
```

`marker_*`は追跡マーカ、`center_*`は回転中心マーカです。`x`と`y`は画像幅・高さに対して
`0〜1`へ正規化した座標です。相対y座標は画像上方向を正とし、回転角度は画像右方向を
`0°`、上方向を`90°`として`0〜360°`で出力します。どちらか一方を検出できなかった
フレームでは、相対座標、半径、角度が空欄になります。JSONには各マーカの検出フレーム数、
回転計算フレーム数、処理時間、実効FPSも保存します。

## 6. MediaPipe Poseの解析パラメータ

| 項目 | 初期値 | 説明 |
| --- | ---: | --- |
| 検出する人数 | `1` | 同時に検出する姿勢の最大数 |
| 姿勢検出の信頼度 | `0.5` | 新しい姿勢として採用する最小信頼度 |
| 姿勢存在の信頼度 | `0.5` | 姿勢ランドマークが存在すると判断する最小信頼度 |
| 追跡の信頼度 | `0.5` | 前フレームからの追跡を採用する最小信頼度 |
| セグメンテーションマスク | 無効 | 人物領域マスクの計算を有効化。現在は独立ファイルとして保存しません |
| モデル | Lite | Lite、Full、Heavyから選択 |
| 処理デバイス | CPU | CPUまたはGPUを選択 |

信頼度は`0.0`から`1.0`まで指定できます。高くすると誤検出を減らせる可能性がありますが、
未検出が増える場合があります。

### モデルの違い

| モデル | 特徴 | 主な用途 |
| --- | --- | --- |
| Lite | 最も軽量で高速 | 動作確認、速度重視 |
| Full | 速度と精度のバランス | 通常の解析 |
| Heavy | 最も高精度で低速 | 精度重視の研究解析 |

選択したモデルがない場合は、MediaPipe公式配布先から`src/models/`へ自動ダウンロードします。
初回だけインターネット接続が必要です。各解析で使用したモデル名、URL、ファイルのSHA-256を
メタデータへ記録します。

### CPU／GPU

- 初期値はCPUです。
- macOSではMetal GPU、UbuntuではMediaPipe GPU Delegateの初期化を試みます。
- GPU非対応環境または初期化失敗時は、自動的にCPUへ戻ります。
- WindowsではCPUへ戻ります。
- GPUは推論部分を担当します。動画の読み書き、CSV、描画などはCPU処理のため、
  動画や出力設定によっては大幅に高速化しません。

指定したデバイスは`requested_delegate`、実際に使用したデバイスは`used_delegate`として
メタデータJSONへ保存されます。

## 7. MediaPipe Poseの出力結果

結果は`datas/outputs/`へ保存されます。

| ファイル | 内容 |
| --- | --- |
| `<動画名>_landmark_<番号>.csv` | 選択したランドマーク1個分の座標 |
| `<動画名>_landmark_<番号>_coordinates.png` | x、y、z座標の時系列グラフ |
| `<動画名>_skeleton.mp4` | 全ランドマークの骨格線と主要パラメータを重ねた動画 |
| `<動画名>_analysis_metadata.json` | 解析条件、再現性情報、処理時間 |

同じ名前の入力動画を再解析すると、同名の結果は上書きされます。必要な結果は解析前に
別の場所へ保存してください。

### CSV

選択したランドマークごとに1ファイル作成します。1行目は次の通常ヘッダーです。

```text
frame,time_seconds,pose_id,x,y,z,visibility,presence
```

- `frame`: 0から始まるフレーム番号
- `time_seconds`: 動画内の時刻
- `pose_id`: 同一フレーム内で検出した人物番号（0始まり）
- `x`, `y`: 画像幅・高さに対して正規化された座標
- `z`: MediaPipeが推定した奥行き方向の相対座標
- `visibility`: ランドマークが画面上で見えている確率
- `presence`: ランドマークが存在する確率

姿勢が検出されなかったフレームも残り、座標欄は空になります。CSV内にはメタデータを
埋め込まず、解析条件は対応するJSONを参照します。

### メタデータJSON

研究の再現性を確保するため、次の情報を保存します。

- 解析日時とプラットフォーム
- Python、MediaPipe、OpenCV、Matplotlibのバージョン
- 入力動画、モデル、実行スクリプトのSHA-256
- モデル名と公式ダウンロードURL
- Poseパラメータ、出力設定、選択ランドマーク
- 指定デバイスと実際に使用したデバイス
- 処理フレーム数とキャンセル状態
- 処理開始・終了日時
- `frame_processing_seconds`: フレーム処理ループの時間
- `total_processing_seconds`: モデル準備やグラフ生成などを含む総時間
- `effective_fps`: 処理フレーム数 ÷ フレーム処理時間

初めてモデルを取得する解析では、ダウンロード時間も総処理時間に含まれます。

## 8. Tkinterライブラリの単体利用

### 動画パスを取得する

```python
from lib.get_filepath import get_filepath, get_filepaths

one_video = get_filepath()          # 1件。キャンセル時は ""
multiple_videos = get_filepaths()   # 複数件。キャンセル時は []
```

`src`以外の場所にあるスクリプトから`lib`を読み込む場合は、プロジェクトの`src`を
モジュール検索パスへ追加するか、実行前に`PYTHONPATH`を設定してください。

macOS／Linux:

```bash
PYTHONPATH=src python your_script.py
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python your_script.py
```

### Poseパラメータを取得する

```python
from lib.mp_get_parameter import mp_get_parameters

parameters = mp_get_parameters()  # 決定時はdict、キャンセル時はNone
```

### 色マーカパラメータを取得する

```python
from lib.get_color_marker_parameters import get_color_marker_parameters

parameters = get_color_marker_parameters()
```

### 出力設定を取得する

```python
from lib.get_output_settings import get_output_settings

landmarks = [(0, "鼻"), (11, "左肩"), (12, "右肩")]
settings = get_output_settings(landmarks)
```

色マーカ解析など項目選択が不要な場合は、一覧を渡さずに使用できます。

```python
settings = get_output_settings(video_label="マーカ追跡動画")
```

### 進捗を表示する

```python
from lib.progress_window import ProgressWindow

with ProgressWindow(total=100, title="解析中") as progress:
    for index in range(100):
        if progress.is_canceled:
            break
        progress.update(index + 1, "処理しています")
```

## 9. トラブルシューティング

## 10. MediaPipe + Optical Flow解析

一定フレームごとにMediaPipe Poseで骨格を再推定し、間のフレームではOpenCVのLucas–Kanade
Optical Flow（`calcOpticalFlowPyrLK`）でランドマークを追跡する実行スクリプトも利用できます。

```bash
python src/mp_pose_optical_flow.py
```

動画選択、Pose設定、出力設定、Optical Flow間隔設定は`src/lib/`の共用ライブラリを使用します。
追加で「MediaPipeを実行する間隔（フレーム）」を指定します。例えば`5`なら0、5、10…フレームでMediaPipeを実行し、その他の
フレームをOptical Flowで追跡します。各再推定時に追跡点を補正するため、間隔を大きくしすぎると
追跡誤差が増える一方、処理時間は短くなります。

出力ファイル名には`_optical_flow`が付きます。CSVには推定元を示す`source`列が追加され、
`mediapipe`または`optical_flow`が記録されます。複数人物を検出した場合は、MediaPipeが返す
人物番号をフレーム間で対応付けて追跡します。大きな遮蔽や人物の入れ替わりがある動画では、
再推定間隔を短くしてください。

### `ModuleNotFoundError: No module named '_tkinter'`

Tkinterが入っていないPythonを使用しています。OS別の手順でTcl/Tkを導入し、仮想環境を
作り直してください。仮想環境は作成元PythonのTkinter構成を引き継ぎます。

```bash
python -m tkinter
```

### `ModuleNotFoundError: No module named 'mediapipe'`

仮想環境が有効か確認し、依存関係を導入し直します。

```bash
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
```

表示されたPythonがこのプロジェクトの`.venv`内にあることを確認してください。

### 動画を開けない／骨格動画を出力できない

- 対応拡張子か確認する
- 別の動画プレーヤーで入力動画を再生できるか確認する
- MP4（H.264など）へ変換してから再試行する
- 出力先へ書き込む権限と空き容量を確認する

### GPUを選んでも速くならない

メタデータJSONの`used_delegate`を確認してください。GPUが使われていても、動画デコード、
色変換、骨格描画、CSV書き込み、動画圧縮、進捗画面はCPU側で動くため、速度差が小さい場合があります。

### 色マーカを検出できない／別の物体を検出する

- 実物に近い色プリセットを選ぶ
- 色相Hと許容幅を少しずつ調整する
- 暗い環境では明度Vの下限を下げる
- 白っぽいマーカでは彩度Sの下限を下げる
- 小さいマーカでは最小面積を下げる
- 背景に同色がある場合は背景を変更するか、マーカを大きくして最小面積を上げる

### モデルをダウンロードできない

インターネット接続、プロキシ、ファイアウォールを確認してください。途中で壊れたモデルが
作成された場合は、該当する`src/models/pose_landmarker_<種類>.task`だけを削除して
再実行します。

## 参考資料

- [Python 3.10: 仮想環境とパッケージ](https://docs.python.org/3.10/tutorial/venv.html)
- [Python: tkinter公式ドキュメント](https://docs.python.org/3/library/tkinter.html)
- [MediaPipe Pose Landmarker for Python](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/python)
- [BlazePose GHUM 3D Model Card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf)
