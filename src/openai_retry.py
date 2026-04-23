"""
OpenAI API 호출에 대한 공통 retry 래퍼.

모든 SC-TSQL 컴포넌트가 raw client 호출 대신 이 유틸을 사용해
RateLimit/APITimeout/일시적 APIError에서 자동 재시도(지수 백오프)한다.
300+ 샘플 본 실험에서 단일 API 실패로 전체 크래시되는 것을 방지한다.
"""

from openai import APIError, APITimeoutError, RateLimitError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


_RETRYABLE = (APIError, APITimeoutError, RateLimitError, APIConnectionError)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def chat_completion(client, **kwargs):
    """OpenAI chat completion with retry. kwargs는 client.chat.completions.create() 인자."""
    return client.chat.completions.create(**kwargs)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def embeddings(client, **kwargs):
    """OpenAI embeddings with retry. kwargs는 client.embeddings.create() 인자."""
    return client.embeddings.create(**kwargs)
