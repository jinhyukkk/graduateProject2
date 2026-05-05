#!/bin/bash
set -e

ENV_NAME="sc_tsql_env"
PYTHON_VERSION="3.10"

echo "=============================================="
echo "  SC-TSQL 실험 환경 설치"
echo "  비전문가 환경을 위한 자기교정 Text-to-SQL"
echo "=============================================="
echo "환경 이름: $ENV_NAME"
echo "Python 버전: $PYTHON_VERSION"
echo ""

# 1. conda 환경 생성
echo "[1/5] conda 환경 생성 중..."
if conda info --envs | grep -q "$ENV_NAME"; then
    echo "  기존 환경 '$ENV_NAME' 발견. 재사용합니다."
else
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
    echo "  환경 '$ENV_NAME' 생성 완료."
fi

# conda activate를 스크립트 내에서 사용하기 위한 초기화
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# 2. 패키지 설치
echo ""
echo "[2/5] Python 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt
echo "  패키지 설치 완료."

# 3. 디렉토리 구조 생성
echo ""
echo "[3/5] 디렉토리 구조 생성 중..."
mkdir -p src
mkdir -p data/raw data/processed
mkdir -p configs
mkdir -p outputs/checkpoints outputs/logs

# src 패키지 초기화
touch src/__init__.py

echo "  src/              -- 소스 코드"
echo "  data/raw/         -- 원본 데이터셋 (Spider, BIRD, EnterpriseDB)"
echo "  data/processed/   -- 전처리된 데이터"
echo "  configs/          -- 설정 파일"
echo "  outputs/checkpoints/ -- 체크포인트"
echo "  outputs/logs/     -- 실행 로그"

# 4. GPU 감지
echo ""
echo "[4/5] GPU 환경 확인 중..."
if python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    GPU_STATUS="사용 가능"
    echo "  GPU 사용 가능: $(python -c "import torch; print(torch.cuda.get_device_name(0))")"
else
    GPU_STATUS="사용 불가 (CPU 모드)"
    echo "  경고: GPU 없음. CPU로 실행됩니다."
    echo "  (본 프로젝트는 API 기반 LLM 사용으로 GPU 필수 아님)"
fi

# 5. 환경 검증
echo ""
echo "[5/5] 설치된 패키지 검증 중..."
python -c "
import openai; print(f'  openai:               {openai.__version__}')
import tenacity; print(f'  tenacity:             {tenacity.__version__}')
import dotenv; print(f'  python-dotenv:        OK')
import transformers; print(f'  transformers:         {transformers.__version__}')
import torch; print(f'  torch:                {torch.__version__}')
import sentence_transformers; print(f'  sentence-transformers: {sentence_transformers.__version__}')
import faiss; print(f'  faiss-cpu:            OK')
import sqlparse; print(f'  sqlparse:             {sqlparse.__version__}')
import yaml; print(f'  PyYAML:               OK')
import sklearn; print(f'  scikit-learn:         {sklearn.__version__}')
import loguru; print(f'  loguru:               {loguru.__version__}')
import fastapi; print(f'  fastapi:              {fastapi.__version__}')
import uvicorn; print(f'  uvicorn:              {uvicorn.__version__}')
try:
    import langgraph; print(f'  langgraph:            OK (선택 경로 활성)')
except ImportError:
    print(f'  langgraph:            (미설치 — LangGraph 경로는 비활성, 기본 SCTSQL은 정상)')
"

echo ""
echo "=============================================="
echo "  설치 완료!"
echo "=============================================="
echo ""
echo "활성화 방법:"
echo "  conda activate $ENV_NAME"
echo ""
echo "데이터셋 안내:"
echo "  - HRDB(합성): 저장소에 포함됨 (data/raw/hrdb/)"
echo "  - BIRD:       https://bird-bench.github.io/ 에서 받아 data/raw/bird/dev_databases/ 로"
echo "  - Spider:     (선택) https://yale-lily.github.io/spider"
echo ""
echo "OPENAI_API_KEY 설정:"
echo "  cp .env.example .env"
echo "  # .env 파일에 API 키 입력"
