"""Pydantic schemas matching the official sample_dataset / challenge format."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

RUBRIC_DIMS = (
    "compilable",
    "io_format",
    "logic",
    "edge_case",
    "complexity",
    "code_quality",
)

TAXONOMY_LABELS = (
    "Lỗi biên dịch",
    "Lỗi nhập/xuất",
    "Lỗi logic",
    "Lỗi vòng lặp",
    "Lỗi mảng/chuỗi",
    "Lỗi hàm",
    "Lỗi edge case",
    "Lỗi thuật toán",
    "Lỗi hard-code",
    "Lỗi style",
)

ExamType = Literal["multi_problem", "single_problem"]
TaskId = Literal["task1", "task2", "task3"]


class RubricScores(BaseModel):
    compilable: int = Field(ge=0, le=1)
    io_format: int = Field(ge=0, le=1)
    logic: int = Field(ge=0, le=4)
    edge_case: int = Field(ge=0, le=2)
    complexity: int = Field(ge=0, le=1)
    code_quality: int = Field(ge=0, le=1)


class TestCaseResult(BaseModel):
    input: str
    expected: str
    actual: Optional[str] = None
    passed: Optional[bool] = None


class SharedInput(BaseModel):
    """Fields shared by Task 1 / Task 2 inputs."""

    exam_id: str
    exam_type: ExamType
    language: str = "cpp11"
    code_file: str
    compile_log: Optional[str] = None
    test_report: Optional[list[TestCaseResult]] = None


class Task1Output(BaseModel):
    rubric: RubricScores
    total_score: int = Field(ge=0, le=10)


class Task2Output(BaseModel):
    taxonomy_error: list[str] = Field(default_factory=list)

    @field_validator("taxonomy_error")
    @classmethod
    def labels_in_space(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(TAXONOMY_LABELS)
        if unknown:
            raise ValueError(f"Unknown taxonomy labels: {unknown}")
        return v


class Task3Input(SharedInput):
    taxonomy_error: list[str] = Field(default_factory=list)
    target_feedback_level: str


class Task3Output(BaseModel):
    feedback: str


class ExamProblem(BaseModel):
    pid: str
    max_score: float
    prototype: Optional[str] = None
    is_prerequisite_for: Optional[list[str]] = None
    io_mode: Optional[str] = None
    constraints: Optional[str] = None


class Exam(BaseModel):
    exam_id: str
    exam_type: ExamType
    language: str = "cpp11"
    statement: str
    problems: list[ExamProblem] = Field(default_factory=list)
    grading_policy: Optional[str] = None
    note: Optional[str] = None
    # keep extra metadata without failing
    model_config = {"extra": "allow"}


class UnifiedSample(BaseModel):
    """Joined sample across all three tasks for one submission."""

    sample_id: str
    exam_id: str
    exam_type: ExamType
    language: str
    code_file: str
    code: str
    exam_statement: str
    grading_policy: Optional[str] = None
    compile_log: Optional[str] = None
    test_report: Optional[list[dict[str, Any]]] = None
    # labels
    rubric: RubricScores
    total_score: int
    taxonomy_error: list[str]
    target_feedback_level: str
    feedback: str


class ChatMLRecord(BaseModel):
    """One training example in ChatML format for Unsloth / TRL SFT."""

    sample_id: str
    task: TaskId
    exam_id: str
    split: Optional[str] = None
    messages: list[dict[str, str]]
    # denormalized text for trainers that expect a single text field
    text: str
    # assistant target only (useful for eval)
    target: str
