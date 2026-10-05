"""Data leakage guard: feedback must never appear in Task 1 / Task 2 prompts."""

from __future__ import annotations

from typing import Iterable

from src.data.schema import ChatMLRecord, UnifiedSample


class DataLeakageError(AssertionError):
    """Raised when teacher feedback leaks into Task 1/2 training inputs."""


def _user_content(record: ChatMLRecord) -> str:
    for m in record.messages:
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _system_content(record: ChatMLRecord) -> str:
    for m in record.messages:
        if m.get("role") == "system":
            return m.get("content") or ""
    return ""


def assert_no_feedback_leakage(
    records: Iterable[ChatMLRecord],
    samples_by_id: dict[str, UnifiedSample] | None = None,
) -> None:
    """
    Hard rules:
      1. Task1/Task2 user+system must not contain the gold `feedback` string.
      2. Task1/Task2 prompts must not contain the literal field name patterns
         that would indicate feedback was injected as a feature.
      3. Task1/Task2 must not contain Task3-only fields (target_feedback_level)
         unless we intentionally shared context (we do not).
    """
    banned_markers = (
        "feedback của giảng viên",
        "teacher_feedback",
        "gold_feedback",
        "## Feedback",
        "target_feedback_level",
    )

    for rec in records:
        if rec.task not in ("task1", "task2"):
            continue

        prompt = _system_content(rec) + "\n" + _user_content(rec)

        for marker in banned_markers:
            if marker.lower() in prompt.lower():
                raise DataLeakageError(
                    f"Leakage marker {marker!r} found in {rec.task} prompt for {rec.sample_id}"
                )

        if samples_by_id is not None:
            sample = samples_by_id.get(rec.sample_id)
            if sample and sample.feedback:
                fb = sample.feedback.strip()
                # Skip ultra-short fragments that could collide with exam text
                if len(fb) >= 20 and fb in prompt:
                    raise DataLeakageError(
                        f"Gold feedback text leaked into {rec.task} prompt for {rec.sample_id}"
                    )

        # Assistant target for task1/2 must be JSON, not free-form feedback essay
        if rec.task in ("task1", "task2") and not rec.target.lstrip().startswith("{"):
            raise DataLeakageError(
                f"{rec.task} target for {rec.sample_id} is not JSON — possible mis-wiring"
            )
