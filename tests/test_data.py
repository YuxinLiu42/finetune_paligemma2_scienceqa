"""Tests for the data module (will be deleted)."""

from project_name.data import COLUMNS_ALWAYS_DROP, COLUMNS_OPTIONAL, COLUMNS_TO_KEEP


def test_columns_to_keep_not_empty():
    """COLUMNS_TO_KEEP should contain required columns."""
    for col in ["image", "question", "choices", "answer", "answer_text"]:
        assert col in COLUMNS_TO_KEEP


def test_columns_always_drop_not_empty():
    """COLUMNS_ALWAYS_DROP should contain solution."""
    assert "solution" in COLUMNS_ALWAYS_DROP


def test_columns_optional_subset_of_keep():
    """COLUMNS_OPTIONAL should all be in COLUMNS_TO_KEEP."""
    for col in COLUMNS_OPTIONAL:
        assert col in COLUMNS_TO_KEEP


def test_no_overlap_between_keep_and_always_drop():
    """No column should appear in both COLUMNS_TO_KEEP and COLUMNS_ALWAYS_DROP."""
    overlap = set(COLUMNS_TO_KEEP) & set(COLUMNS_ALWAYS_DROP)
    assert overlap == set()
