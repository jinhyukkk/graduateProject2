"""
Result Explainer (Section 4.5)
비전문가용 자연어 결과 설명.
"""

import os
from openai import OpenAI

from src.openai_retry import chat_completion


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

        prompt = f"""You are a helpful data assistant explaining database query results to a non-technical user.

## User's Question
{query}

## SQL Query Used
{final_sql}

## Query Results
{result_preview}

{correction_summary}

## Instructions
1. Explain the results in plain, easy-to-understand language (Korean).
2. Directly answer the user's original question based on the results.
3. If corrections were made, briefly mention what was fixed and why, in a reassuring tone.
4. Do NOT include SQL code or technical jargon.
5. Keep the explanation concise but complete.

## 설명"""

        response = chat_completion(
            self.client,
            model=self.llm_model,
            temperature=0.3,  # 약간의 자연스러움을 위해 0.3
            max_completion_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

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
