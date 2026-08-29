#!/bin/sh
set -eu

PYTHON_BIN=".venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    echo ".venvが見つかりません。READMEの手順でPython 3.10の仮想環境を作成してください。" >&2
    exit 1
fi

"$PYTHON_BIN" -m pip install \
    torch==2.13.0 \
    torchvision==0.28.0 \
    openmim==0.3.9

# OpenMIM/MMCV 2.1.0はpkg_resourcesを使うため、setuptools 81未満が必要。
"$PYTHON_BIN" -m pip install \
    setuptools==80.9.0 \
    ninja==1.13.0 \
    wheel==0.48.0 \
    Cython==3.3.0 \
    scipy==1.14.1

# Apple Siliconには対応ホイールがないため、現在の環境を使ってビルドする。
"$PYTHON_BIN" -m pip install --no-build-isolation mmcv==2.1.0
"$PYTHON_BIN" -m pip install --no-build-isolation chumpy==0.70
"$PYTHON_BIN" -m pip install --no-build-isolation xtcocotools==1.14.3

"$PYTHON_BIN" -m pip install \
    mmdet==3.3.0 \
    mmpose==1.3.2

"$PYTHON_BIN" -m pip check
"$PYTHON_BIN" -c 'import torch; print("MPS built:", torch.backends.mps.is_built()); print("MPS available:", torch.backends.mps.is_available())'
