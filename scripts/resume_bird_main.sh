#!/usr/bin/env bash
# 본 실험 재개 스크립트.
#
# 작동 방식:
#   1. outputs/checkpoints/ 와 outputs/logs/ 를 보고 미완성 condition을 자동 식별
#   2. 미완성 condition만 직렬로 재가동 (체크포인트에서 이어감)
#   3. 모두 끝나면 EIED + 요약 자동 산출
#
# 사용법:
#   bash scripts/resume_bird_main.sh
#   또는 백그라운드로:
#   nohup bash scripts/resume_bird_main.sh > outputs/run_logs/resume_$(date +%s).log 2>&1 &

set -uo pipefail
cd "$(dirname "$0")/.."

CONFIG="configs/config_gpt4o.yaml"
SEED=42
SAMPLE=300

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# 모든 condition 정의: "model:ablation" (baseline은 ablation=-)
declare -a CONDITIONS=(
  "sc_tsql:none"
  "sc_tsql:no_nli"
  "sc_tsql:no_routing"
  "sc_tsql:no_history"
  "zeroshot:-"
  "dail_sql:-"
  "mac_sql:-"
)

# 어느 condition이 결과 파일 (results_bird_*) 까지 만들었는지 확인
is_done() {
  local model="$1" ablation="$2"
  local pattern
  if [[ "$model" == "sc_tsql" ]]; then
    pattern="outputs/logs/results_bird_sc_tsql_${ablation}_seed${SEED}_*.json"
  else
    pattern="outputs/logs/results_bird_${model}_seed${SEED}_*.json"
  fi
  # 오늘 날짜(20260501) 이후의 결과 파일이 있어야 done
  for f in $pattern; do
    [[ -f "$f" ]] || continue
    if [[ "$f" =~ _([0-9]{8})_ ]]; then
      [[ "${BASH_REMATCH[1]}" -ge 20260501 ]] && return 0
    fi
  done
  return 1
}

LOG_DIR="outputs/run_logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

echo "=== Resume run start: $(date) ==="
for cond in "${CONDITIONS[@]}"; do
  IFS=':' read -r model ablation <<< "$cond"
  tag="${model}${ablation:+_$ablation}"

  if is_done "$model" "$ablation"; then
    echo ""
    echo "[SKIP] $tag — 이미 완료된 결과 파일 존재"
    continue
  fi

  echo ""
  echo ">>> [$tag] $(date +%H:%M:%S) (resume from checkpoint if any)"
  log="${LOG_DIR}/resume_bird300_${tag}_${TS}.log"

  if [[ "$model" == "sc_tsql" ]]; then
    PYTHONPATH=. python evaluate.py \
      --config "$CONFIG" --dataset bird --model sc_tsql \
      --sample "$SAMPLE" --seed "$SEED" --ablation "$ablation" \
      > "$log" 2>&1
  else
    PYTHONPATH=. python evaluate.py \
      --config "$CONFIG" --dataset bird --model "$model" \
      --sample "$SAMPLE" --seed "$SEED" \
      > "$log" 2>&1
  fi
  rc=$?
  echo "    exit=$rc  log=$log"
  [[ $rc -ne 0 ]] && echo "    !! FAILED — 다시 실행하면 체크포인트에서 이어짐"
done

echo ""
echo "=== ALL DONE: $(date) ==="
