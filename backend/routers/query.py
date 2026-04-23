"""
Router: /api/databases, /api/query
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas.query import (
    DatabaseListResponse,
    QueryRequest,
    QueryResponse,
)
from backend.services.tsql_service import scan_databases, run_query, run_query_stream

router = APIRouter(prefix="/api", tags=["query"])


@router.get("/databases", response_model=DatabaseListResponse)
async def get_databases():
    """Return list of available SQLite databases."""
    try:
        databases = scan_databases()
        return {"databases": databases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan database directories: {e}")


@router.post("/query", response_model=QueryResponse)
async def execute_query(req: QueryRequest):
    """Execute SC-TSQL pipeline for a single natural-language query."""
    try:
        history = [t.model_dump() for t in req.conversation_history]
        result = run_query(
            query=req.query,
            db_id=req.db_id,
            dataset=req.dataset,
            conversation_history=history,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")


@router.post("/query/stream")
async def stream_query(req: QueryRequest):
    """
    SC-TSQL 파이프라인을 실행하면서 Server-Sent Events로 단계별 진행상황을 스트리밍한다.

    이벤트 종류:
      step        — 파이프라인 단계 전환 {stage, round?}
      sql_generated — SQL 생성 완료 {sql, confidence}
      validated   — 실행 검증 결과 {success, error_type}
      verified    — 의미 검증 결과 {score, is_consistent, back_translation}
      corrected   — 교정 완료 {round, error_type, original_sql, corrected_sql, semantic_score}
      explanation — 자연어 설명 {text}
      result      — 최종 완성 결과 (QueryResponse 형태)
      error       — 오류 {message}
    """
    history = [t.model_dump() for t in req.conversation_history]

    async def event_generator():
        try:
            async for chunk in run_query_stream(
                query=req.query,
                db_id=req.db_id,
                dataset=req.dataset,
                conversation_history=history,
            ):
                yield chunk
        except Exception as e:
            import json as _json
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
