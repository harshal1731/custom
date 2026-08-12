#!/bin/bash
set -euo pipefail
BASE="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0"
ROOT="/root/.paddlex/official_models"
mkdir -p "$ROOT"
MODELS=(
  PP-DocBlockLayout
  PP-DocLayout_plus-L
  PP-LCNet_x1_0_table_cls
  SLANeXt_wired
  SLANet_plus
  RT-DETR-L_wired_table_cell_det
  RT-DETR-L_wireless_table_cell_det
  PP-Chart2Table
  PP-LCNet_x1_0_doc_ori
  PP-LCNet_x1_0_textline_ori
)
for m in "${MODELS[@]}"; do
  if [ -d "$ROOT/$m" ]; then
    echo "SKIP $m"
    continue
  fi
  echo "GET $m"
  curl -fsSL "$BASE/${m}_infer.tar" -o /tmp/model.tar
  td=$(mktemp -d)
  tar -xf /tmp/model.tar -C "$td"
  sub=$(ls "$td")
  if [ -d "$td/$sub" ]; then
    mv "$td/$sub" "$ROOT/$m"
  else
    mv "$td" "$ROOT/$m"
  fi
  rm -rf "$td" /tmp/model.tar
  echo "OK $m"
done
ls -1 "$ROOT"