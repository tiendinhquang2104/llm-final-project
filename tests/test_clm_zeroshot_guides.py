from src.clm_zeroshot import guides
from src.data.loader import DIM_MAX
from src.task2.labels import LABELS

DIMS = ["io_format", "logic", "edge_case", "complexity", "code_quality"]


def _all_texts():
    yield from guides.LABEL_QUESTIONS.values()
    yield from guides.RUBRIC_QUESTIONS.values()
    for levels in guides.RUBRIC_LEVELS.values():
        yield from levels
    yield guides.PROBLEM_QUESTION
    yield from guides.EVIDENCE.values()


def test_label_questions_cover_all_labels():
    assert set(guides.LABEL_QUESTIONS) == set(LABELS)
    for lab, q in guides.LABEL_QUESTIONS.items():
        assert q.startswith(f"Bài nộp trên có mắc {lab} không?")


def test_rubric_keys_and_levels():
    assert set(guides.RUBRIC_QUESTIONS) == set(DIMS)
    assert set(guides.RUBRIC_LEVELS) == set(DIMS)
    for d in DIMS:
        assert guides.RUBRIC_QUESTIONS[d].startswith(f"Chấm chiều {d}")
        levels = guides.RUBRIC_LEVELS[d]
        assert len(levels) == DIM_MAX[d] + 1
        for i, text in enumerate(levels):
            assert text.startswith(f"{i} điểm: ")


def test_evidence_covers_labels_and_dims():
    assert set(guides.EVIDENCE) == set(LABELS) | set(DIMS)
    assert all(v.strip() for v in guides.EVIDENCE.values())


def test_problem_question_formats():
    q = guides.PROBLEM_QUESTION.format(pid="P1", prototype="x")
    assert "P1" in q and "(x)" in q


def test_no_feedback_and_texts_are_short():
    for t in _all_texts():
        assert "feedback" not in t.lower()
    for t in list(guides.LABEL_QUESTIONS.values()) + list(guides.RUBRIC_QUESTIONS.values()):
        assert len(t.split()) <= 70
    for levels in guides.RUBRIC_LEVELS.values():
        assert all(len(t.split()) <= 60 for t in levels)


def test_label_questions_have_no_frequency_meta():
    for lab, q in guides.LABEL_QUESTIONS.items():
        low = q.lower()
        for word in ("hiếm", "phổ biến", "chưa gán"):
            assert word not in low, (lab, word)
        assert " Có nếu " in q, lab
