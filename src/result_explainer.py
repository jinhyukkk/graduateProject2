"""
Result Explainer (Section 4.5)
비전문가용 자연어 결과 설명.
"""

import os
from typing import Callable

from openai import OpenAI

from src.openai_retry import chat_completion, chat_completion_streaming


class ResultExplainer:
    """
    Section 4.5: 최종 SQL + 실행 결과 → 비전문가용 자연어 설명.
    교정 이력이 있으면 수정 내용을 투명하게 안내한다.
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.llm_model = config["llm"]["model"]

    def explain(
        self,
        query: str,
        final_sql: str,
        results: list[tuple],
        correction_history: list[dict],
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """
        Section 4.5: 쿼리 결과를 비전문가가 이해할 수 있는 자연어로 설명한다.

        Args:
            query: 원래 자연어 질의
            final_sql: 최종 SQL
            results: 실행 결과 (행 리스트)
            correction_history: 교정 이력 리스트, 각 항목은
                {"round": int, "error_type": str, "original_sql": str, "corrected_sql": str}

        Returns:
            비전문가용 자연어 설명 문자열
        """
        # 결과 요약 (최대 10행)
        result_preview = self._format_results(results)
        correction_summary = self._format_correction_history(correction_history)

        had_correction = bool(correction_history)
        correction_block = correction_summary if had_correction else "(no corrections — first attempt succeeded)"

        prompt = f"""You are a friendly data assistant. Reply to a non-technical user in **Korean**.

## User's Question
{query}

## Query Results
{result_preview}

## Correction status
{correction_block}

## Style guidelines (시연 폴리시)
- 1~2문장. 메신저 답변 톤. 불필요한 인사·결말 멘트 금지.
- 핵심 수치를 먼저 제시, 그 다음 짧은 부연. (예: "재직 중인 직원은 20명입니다.")
- "쿼리", "SQL", "데이터베이스" 같은 기술 용어 금지.
- **교정이 있었던 경우에만** 한 문장으로 가볍게 언급 (예: "처음 결과가 비어 있어 조건을 다시 잡았어요.").
- 교정이 없었으면 교정 관련 멘트를 절대 추가하지 말 것.
- 결과가 비어 있으면 사용자에게 "데이터가 없습니다"라고 솔직히 답하고, 가능한 원인을 한 문장으로만 짚어줄 것.

## 답변"""

        if on_token is None:
            response = chat_completion(
                self.client,
                model=self.llm_model,
                temperature=0.3,
                max_completion_tokens=180,  # 1-2문장 강제
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()

        # 시연 폴리시: 최종 답변 정리 단계의 LLM 출력을 토큰 단위로 흘려보낸다.
        return chat_completion_streaming(
            self.client,
            on_token,
            model=self.llm_model,
            temperature=0.3,
            max_completion_tokens=180,
            messages=[{"role": "user", "content": prompt}],
        ).strip()

    def _format_results(self, results: list[tuple]) -> str:
        """결과를 텍스트로 포맷한다."""
        if not results:
            return "결과 없음 (0행)"
        preview = results[:10]
        lines = [str(row) for row in preview]
        text = "\n".join(lines)
        if len(results) > 10:
            text += f"\n... (총 {len(results)}행 중 상위 10행)"
        else:
            text += f"\n(총 {len(results)}행)"
        return text

    def _format_correction_history(self, correction_history: list[dict]) -> str:
        """교정 이력을 포맷한다."""
        if not correction_history:
            return ""
        lines = ["## Correction History"]
        for entry in correction_history:
            lines.append(
                f"- Round {entry['round']}: {entry.get('error_type', 'unknown')} 오류 수정"
            )
        return "\n".join(lines)
