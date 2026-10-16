"""Task 3 Pipeline: Prompt -> LLM -> Parse -> Pedagogical Guard -> Compliant Output."""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

from src.task3.pedagogical_guard import audit_feedback, sanitize_feedback
from src.task3.prompts import build_task3_messages
from src.utils.json_extractor import extract_json_objects


def parse_task3_output(
    text: str,
    target_level: str,
    input_taxonomy_error: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Parse LLM output for Task 3, extract feedback & taxonomy_error,
    and enforce Pedagogical Guard constraints.
    """
    text = text.strip()
    extracted_taxonomy = list(input_taxonomy_error) if input_taxonomy_error is not None else []
    extracted_feedback = ""

    # Attempt 1: Extract structured JSON object
    json_objs = extract_json_objects(text)
    if json_objs:
        json_obj = json_objs[0]
        if "feedback" in json_obj and isinstance(json_obj["feedback"], str):
            extracted_feedback = json_obj["feedback"]
        if "taxonomy_error" in json_obj and isinstance(json_obj["taxonomy_error"], list):
            if input_taxonomy_error is None:
                extracted_taxonomy = [str(x) for x in json_obj["taxonomy_error"]]


    # Attempt 2: If no valid JSON feedback, fallback to full text
    if not extracted_feedback:
        # Strip markdown fences if wrapped in ```text ... ```
        cleaned = re.sub(r"^```(?:json|text)?\s*", "", text)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        extracted_feedback = cleaned

    # Audit with Pedagogical Guard
    report = audit_feedback(
        feedback=extracted_feedback,
        target_level=target_level,
        taxonomy_error=extracted_taxonomy,
    )

    return {
        "taxonomy_error": extracted_taxonomy,
        "feedback": report.sanitized_feedback,
        "is_compliant": report.is_compliant,
        "raw_feedback": extracted_feedback,
        "violations": report.violations,
    }


class Task3Pipeline:
    """End-to-end pipeline for generating pedagogical feedback."""

    def __init__(self, backend, cfg: dict | None = None):
        self.backend = backend
        self.cfg = cfg or {}
        self.gen_cfg = self.cfg.get("generation", {})

    def build_request(
        self,
        exam_id: str,
        exam_type: str,
        exam_statement: str,
        code: str,
        target_level: str,
        taxonomy_error: Sequence[str] | None = None,
        compile_log: str | None = None,
    ) -> dict[str, Any]:
        """Build chat messages and request payload for LLM backend."""
        messages = build_task3_messages(
            exam_id=exam_id,
            exam_type=exam_type,
            exam_statement=exam_statement,
            code=code,
            target_level=target_level,
            taxonomy_error=taxonomy_error,
            compile_log=compile_log,
        )
        return {
            "messages": messages,
            "target_level": target_level,
            "taxonomy_error": taxonomy_error,
        }

    def process_single(
        self,
        exam_id: str,
        exam_type: str,
        exam_statement: str,
        code: str,
        target_level: str,
        taxonomy_error: Sequence[str] | None = None,
        compile_log: str | None = None,
    ) -> dict[str, Any]:
        """Generate and guard feedback for a single submission."""
        # Short-circuit: If errors are known and empty, immediately return empty feedback
        if taxonomy_error is not None and len(taxonomy_error) == 0:
            return {
                "taxonomy_error": [],
                "feedback": "",
                "is_compliant": True,
                "raw_feedback": "",
                "violations": [],
            }

        req = self.build_request(
            exam_id=exam_id,
            exam_type=exam_type,
            exam_statement=exam_statement,
            code=code,
            target_level=target_level,
            taxonomy_error=taxonomy_error,
            compile_log=compile_log,
        )

        outputs = self.backend.generate([req], self.gen_cfg)
        raw_text = outputs[0][0] if outputs and outputs[0] else ""

        return parse_task3_output(
            text=raw_text,
            target_level=target_level,
            input_taxonomy_error=taxonomy_error,
        )
