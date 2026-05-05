#!/usr/bin/env bash
# D1 pilot: gpt-4o × BIRD 50 × 7 conditions (main + 3 ablations + 3 baselines)
# Fix A (rollback) + Fix B (threshold 0.7) 반영 후 교정 기여 재검증용.

set -euo pipefail

CONFIG="${1:-configs/config_gpt4o.yaml}"
SEED="${SEED:-42}"
SAMPLE="${SAMPLE:-50}"

LOG_DIR="outputs/run_logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

echo "=== D1 pilot: gpt-4o BIRD $SAMPLE × 7 conditions (seed=$SEED) ==="

run() {
  local model="$1" ablation="$2"
  local tag="bird_${model}${ablation:+_$ablation}_seed${SEED}"
  local log="${LOG_DIR}/${tag}_${TS}.log"
  local abl_arg=""
  [[ -n "$ablation" ]] && abl_arg="--ablation $ablation"
  echo ""
  echo ">>> [$(date +%H:%M:%S)] $tag"
  if python evaluate.py --config "$CONFIG" --dataset bird --model "$model" \
        --seed "$SEED" --sample "$SAMPLE" $abl_arg > "$log" 2>&1; then
    echo "    OK ($(grep -m1 'EX' "$log" | head -1))"
  else
    echo "    FAIL — see $log"
  fi
}

run sc_tsql  none
run sc_tsql  no_nli
run sc_tsql  no_routing
run sc_tsql  no_history
run zeroshot ""
run dail_sql ""
run mac_sql  ""

echo ""
echo "=== D1 완료 ==="
