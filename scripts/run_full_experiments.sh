#!/usr/bin/env bash
# 본 실험 전체 일괄 실행 스크립트.
#
# 실행 항목:
#   [BIRD-300] sc_tsql(none) + 3 baselines + 3 ablations(no_nli, no_routing, no_history)
#   [HRDB-30]  sc_tsql(none) + 3 baselines
# 기본 모델: gpt-4o (configs/config_gpt4o.yaml). 비용 절감 시 config 인자 변경.
#
# 사용법:
#   bash scripts/run_full_experiments.sh                     # 기본 (gpt-4o, seed=42)
#   bash scripts/run_full_experiments.sh configs/config.yaml # gpt-4o-mini로 절감
#   SEEDS="42 123 2026" bash scripts/run_full_experiments.sh # 멀티 시드
#
# 체크포인트가 자동 저장되므로 중단 후 같은 명령으로 재실행하면 이어집니다.

set -euo pipefail

CONFIG="${1:-configs/config_gpt4o.yaml}"
SEEDS="${SEEDS:-42}"
BIRD_SAMPLE="${BIRD_SAMPLE:-300}"
HRDB_SAMPLE="${HRDB_SAMPLE:-}"   # 비워두면 전체 30개

LOG_DIR="outputs/run_logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# .env 로드 (OPENAI_API_KEY 등)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "========================================="
echo "  Full Experiment Run"
echo "  Config:  $CONFIG"
echo "  Seeds:   $SEEDS"
echo "  BIRD N:  $BIRD_SAMPLE"
echo "  HRDB N:  ${HRDB_SAMPLE:-all}"
echo "  Started: $TIMESTAMP"
echo "========================================="

run() {
  # run <dataset> <model> <ablation_or_dash> <seed>
  local dataset="$1"
  local model="$2"
  local ablation="$3"
  local seed="$4"
  local sample_arg=""
  if [[ "$dataset" == "bird" && -n "$BIRD_SAMPLE" ]]; then
    sample_arg="--sample $BIRD_SAMPLE"
  elif [[ "$dataset" == "hrdb" && -n "$HRDB_SAMPLE" ]]; then
    sample_arg="--sample $HRDB_SAMPLE"
  fi

  local tag="${dataset}_${model}"
  if [[ "$model" == "sc_tsql" && "$ablation" != "-" ]]; then
    tag="${tag}_${ablation}"
  fi
  tag="${tag}_seed${seed}"

  local log_file="${LOG_DIR}/${tag}_${TIMESTAMP}.log"
  echo ""
  echo ">>> [$(date +%H:%M:%S)] $tag → $log_file"

  local ablation_arg=""
  if [[ "$model" == "sc_tsql" && "$ablation" != "-" ]]; then
    ablation_arg="--ablation $ablation"
  fi

  if python evaluate.py \
        --config "$CONFIG" \
        --dataset "$dataset" \
        --model "$model" \
        --seed "$seed" \
        $sample_arg \
        $ablation_arg \
        > "$log_file" 2>&1; then
    echo "    OK ($(grep -m1 'EX' "$log_file" | head -1))"
  else
    echo "    FAIL — see $log_file"
  fi
}

for seed in $SEEDS; do
  echo ""
  echo "=== seed=$seed ==="

  # BIRD: 메인 + 베이스라인 + 어블레이션
  run bird sc_tsql  none        "$seed"
  run bird zeroshot -           "$seed"
  run bird dail_sql -           "$seed"
  run bird mac_sql  -           "$seed"
  run bird sc_tsql  no_nli      "$seed"
  run bird sc_tsql  no_routing  "$seed"
  run bird sc_tsql  no_history  "$seed"

  # HRDB: 메인 + 베이스라인 (어블레이션은 BIRD로만)
  run hrdb sc_tsql  none        "$seed"
  run hrdb zeroshot -           "$seed"
  run hrdb dail_sql -           "$seed"
  run hrdb mac_sql  -           "$seed"
done

echo ""
echo "========================================="
echo "  완료. 결과: outputs/logs/, 로그: $LOG_DIR/"
echo "========================================="
