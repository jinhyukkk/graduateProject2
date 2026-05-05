#!/usr/bin/env bash
# HRDB n=257 본 실험 자동 실행 스크립트.
#
# 5개 condition 직렬 실행:
#   1. sc_tsql:none       (Full + SC k=5)
#   2. sc_tsql:no_sc      (k=1 강제 — SC 단독 기여 분리)
#   3. zeroshot           (기준선)
#   4. dail_sql           (ICL 패러다임 비교군)
#   5. mac_sql            (멀티에이전트 비교군)
#   6. din_sql            (분해+자기수정 비교군, 신규)
#
# 사용:
#   bash scripts/run_hrdb_main.sh
# BIRD SC 실험이 진행 중이면 끝난 뒤 직렬 실행:
#   until ! pgrep -f "evaluate.py.*--dataset bird" > /dev/null; do sleep 30; done; bash scripts/run_hrdb_main.sh

set -uo pipefail
cd "$(dirname "$0")/.."

CONFIG="configs/config_gpt4o.yaml"
SEED=42
SAMPLE=257  # dev_combined.json 전체

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

LOG_DIR="outputs/run_logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

declare -a CONDITIONS=(
  "sc_tsql:none"
  "sc_tsql:no_sc"
  "zeroshot:-"
  "dail_sql:-"
  "din_sql:-"
  "mac_sql:-"
)

echo "=== HRDB main run start: $(date) ==="
for cond in "${CONDITIONS[@]}"; do
  IFS=':' read -r model ablation <<< "$cond"
  tag="${model}${ablation:+_$ablation}"

  echo ""
  echo ">>> [$tag] $(date +%H:%M:%S)"
  log="${LOG_DIR}/hrdb_${tag}_${TS}.log"

  if [[ "$model" == "sc_tsql" ]]; then
    PYTHONPATH=. python -u evaluate.py \
      --config "$CONFIG" --dataset hrdb --model sc_tsql \
      --sample "$SAMPLE" --seed "$SEED" --ablation "$ablation" \
      > "$log" 2>&1
  else
    PYTHONPATH=. python -u evaluate.py \
      --config "$CONFIG" --dataset hrdb --model "$model" \
      --sample "$SAMPLE" --seed "$SEED" \
      > "$log" 2>&1
  fi
  rc=$?
  echo "    exit=$rc  log=$log"
done

echo ""
echo "=== HRDB main run done: $(date) ==="
