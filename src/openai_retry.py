"""
OpenAI API 호출에 대한 공통 retry 래퍼.

모든 SC-TSQL 컴포넌트가 raw client 호출 대신 이 유틸을 사용해
RateLimit/APITimeout/일시적 APIError에서 자동 재시도(지수 백오프)한다.
300+ 샘플 본 실험에서 단일 API 실패로 전체 크래시되는 것을 방지한다.

추가 기능: 응답의 usage 필드(prompt_tokens, completion_tokens, total_tokens)를
모듈 전역 누적기 _USAGE_TOTALS에 합산한다. 비용 추정 파일럿용이며 평가
런이 끝난 뒤 evaluate.py에서 get_usage_totals()로 회수한다.
"""

from threading import Lock

from openai import APIError, APITimeoutError, RateLimitError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


_RETRYABLE = (APIError, APITimeoutError, RateLimitError, APIConnectionError)

_USAGE_LOCK = Lock()
_USAGE_TOTALS = {
    "chat_calls": 0,
    "chat_prompt_tokens": 0,
    "chat_completion_tokens": 0,
    "chat_total_tokens": 0,
    "embedding_calls": 0,
    "embedding_total_tokens": 0,
    "by_model": {},  # model -> {calls, prompt_tokens, completion_tokens}
}


def _accumulate_chat(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    tt = getattr(usage, "total_tokens", pt + ct) or (pt + ct)
    model = getattr(response, "model", "unknown")
    with _USAGE_LOCK:
        _USAGE_TOTALS["chat_calls"] += 1
        _USAGE_TOTALS["chat_prompt_tokens"] += pt
        _USAGE_TOTALS["chat_completion_tokens"] += ct
        _USAGE_TOTALS["chat_total_tokens"] += tt
        bucket = _USAGE_TOTALS["by_model"].setdefault(
            model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        )
        bucket["calls"] += 1
        bucket["prompt_tokens"] += pt
        bucket["completion_tokens"] += ct


def _accumulate_embedding(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    tt = getattr(usage, "total_tokens", 0) or 0
    with _USAGE_LOCK:
        _USAGE_TOTALS["embedding_calls"] += 1
        _USAGE_TOTALS["embedding_total_tokens"] += tt


def get_usage_totals():
    """현재까지 누적된 토큰 사용량 스냅샷."""
    with _USAGE_LOCK:
        return {
            **{k: v for k, v in _USAGE_TOTALS.items() if k != "by_model"},
            "by_model": {m: dict(b) for m, b in _USAGE_TOTALS["by_model"].items()},
        }


def reset_usage_totals():
    with _USAGE_LOCK:
        _USAGE_TOTALS["chat_calls"] = 0
        _USAGE_TOTALS["chat_prompt_tokens"] = 0
        _USAGE_TOTALS["chat_completion_tokens"] = 0
        _USAGE_TOTALS["chat_total_tokens"] = 0
        _USAGE_TOTALS["embedding_calls"] = 0
        _USAGE_TOTALS["embedding_total_tokens"] = 0
        _USAGE_TOTALS["by_model"] = {}


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def chat_completion(client, **kwargs):
    """OpenAI chat completion with retry. kwargs는 client.chat.completions.create() 인자."""
    response = client.chat.completions.create(**kwargs)
    _accumulate_chat(response)
    return response


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def chat_completion_streaming(client, on_token, **kwargs):
    """Streaming chat completion.

    `on_token(delta)` 콜백으로 사용자 표시용 *프로즈* 토큰만 흘려보낸다. 응답에 포함된
    fenced code block(```...```)은 SQL/JSON이 추론 패널에 새는 것을 막기 위해
    on_token으로 보내지 않는다 (raw 반환값에는 그대로 남는다).

    Returns:
        full raw text (코드 블록 포함).
    """
    kwargs = dict(kwargs)
    kwargs["stream"] = True
    kwargs.setdefault("stream_options", {"include_usage": True})

    accumulator = ""
    emit_pos = 0
    inside_code = False
    last_usage = None
    last_model = kwargs.get("model", "unknown")

    stream = client.chat.completions.create(**kwargs)
    for event in stream:
        usage = getattr(event, "usage", None)
        if usage is not None:
            last_usage = usage
            last_model = getattr(event, "model", last_model)
        try:
            delta = event.choices[0].delta.content or ""
        except (AttributeError, IndexError):
            delta = ""
        if not delta:
            continue
        accumulator += delta

        # 누적 텍스트에서 emit_pos 부터 ``` 마커를 추적해 코드 블록을 건너뛴다.
        pos = emit_pos
        while pos < len(accumulator):
            if not inside_code:
                idx = accumulator.find("```", pos)
                if idx == -1:
                    # 다음 청크에 들어올 가능성에 대비해 끝 2글자는 보류
                    safe_end = len(accumulator) - 2
                    if safe_end > pos:
                        on_token(accumulator[pos:safe_end])
                        emit_pos = safe_end
                    break
                if idx > pos:
                    on_token(accumulator[pos:idx])
                emit_pos = idx + 3
                pos = idx + 3
                inside_code = True
            else:
                idx = accumulator.find("```", pos)
                if idx == -1:
                    emit_pos = len(accumulator)
                    break
                emit_pos = idx + 3
                pos = idx + 3
                inside_code = False

    # 스트림 종료 — 보류된 마지막 2글자를 포함해 잔여를 flush
    if not inside_code and emit_pos < len(accumulator):
        on_token(accumulator[emit_pos:])

    if last_usage is not None:
        class _Resp:
            pass
        _resp = _Resp()
        _resp.usage = last_usage
        _resp.model = last_model
        _accumulate_chat(_resp)

    return accumulator


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def embeddings(client, **kwargs):
    """OpenAI embeddings with retry. kwargs는 client.embeddings.create() 인자."""
    response = client.embeddings.create(**kwargs)
    _accumulate_embedding(response)
    return response
