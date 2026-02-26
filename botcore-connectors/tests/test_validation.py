"""Tests for input validation — spec 04."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from botcore_connectors.validation import (
    MAX_BODY_SIZE,
    MAX_IDENTIFIER_LENGTH,
    MAX_ITEMS_DEFAULT,
    InputValidationResult,
    check_max_body_size,
    check_max_items,
    check_max_length,
    check_no_path_traversal,
    check_owner_repo,
    validate_inputs,
)

# ---------------------------------------------------------------------------
# check_max_length
# ---------------------------------------------------------------------------


class TestCheckMaxLength:
    def test_within_limit(self) -> None:
        assert check_max_length("short", field_name="name") == []

    def test_at_limit(self) -> None:
        value = "a" * MAX_IDENTIFIER_LENGTH
        assert check_max_length(value, field_name="name") == []

    def test_over_limit(self) -> None:
        value = "a" * (MAX_IDENTIFIER_LENGTH + 1)
        violations = check_max_length(value, field_name="name")
        assert len(violations) == 1
        assert "name" in violations[0]
        assert str(MAX_IDENTIFIER_LENGTH) in violations[0]

    def test_custom_limit(self) -> None:
        assert check_max_length("abcde", field_name="x", limit=5) == []
        violations = check_max_length("abcdef", field_name="x", limit=5)
        assert len(violations) == 1

    def test_custom_field_name(self) -> None:
        violations = check_max_length("a" * 10, field_name="my_field", limit=5)
        assert "my_field" in violations[0]

    def test_empty_string(self) -> None:
        assert check_max_length("", field_name="name") == []


# ---------------------------------------------------------------------------
# check_max_body_size
# ---------------------------------------------------------------------------


class TestCheckMaxBodySize:
    def test_small_string(self) -> None:
        assert check_max_body_size("hello", field_name="body") == []

    def test_bytes_input(self) -> None:
        assert check_max_body_size(b"hello", field_name="body") == []

    def test_at_limit(self) -> None:
        value = "a" * MAX_BODY_SIZE
        assert check_max_body_size(value, field_name="body") == []

    def test_over_limit(self) -> None:
        value = "a" * (MAX_BODY_SIZE + 1)
        violations = check_max_body_size(value, field_name="body")
        assert len(violations) == 1
        assert "body" in violations[0]

    def test_utf8_multibyte(self) -> None:
        # Each emoji is 4 bytes in UTF-8; 3 chars = 12 bytes
        value = "\U0001f600" * 3
        violations = check_max_body_size(value, field_name="body", limit=10)
        assert len(violations) == 1
        assert "12" in violations[0]


# ---------------------------------------------------------------------------
# check_max_items
# ---------------------------------------------------------------------------


class TestCheckMaxItems:
    def test_under_limit(self) -> None:
        assert check_max_items([1, 2, 3], field_name="ids") == []

    def test_at_limit(self) -> None:
        items = list(range(MAX_ITEMS_DEFAULT))
        assert check_max_items(items, field_name="ids") == []

    def test_over_limit(self) -> None:
        items = list(range(MAX_ITEMS_DEFAULT + 1))
        violations = check_max_items(items, field_name="ids")
        assert len(violations) == 1
        assert "ids" in violations[0]

    def test_custom_limit(self) -> None:
        assert check_max_items([1, 2], field_name="x", limit=2) == []
        violations = check_max_items([1, 2, 3], field_name="x", limit=2)
        assert len(violations) == 1

    def test_empty_list(self) -> None:
        assert check_max_items([], field_name="ids") == []


# ---------------------------------------------------------------------------
# check_no_path_traversal
# ---------------------------------------------------------------------------


class TestCheckNoPathTraversal:
    def test_clean_path(self) -> None:
        assert check_no_path_traversal("src/main.py", field_name="path") == []

    def test_dot_dot_slash(self) -> None:
        violations = check_no_path_traversal("../etc/passwd", field_name="path")
        assert len(violations) == 1
        assert "path traversal" in violations[0]

    def test_dot_dot_backslash(self) -> None:
        violations = check_no_path_traversal("..\\windows\\system32", field_name="path")
        assert len(violations) == 1

    def test_middle_traversal(self) -> None:
        violations = check_no_path_traversal("foo/../bar", field_name="path")
        assert len(violations) == 1

    def test_bare_dot_dot(self) -> None:
        violations = check_no_path_traversal("..", field_name="path")
        assert len(violations) == 1

    def test_single_dot_ok(self) -> None:
        assert check_no_path_traversal(".", field_name="path") == []

    def test_file_with_double_dot_in_name_ok(self) -> None:
        assert check_no_path_traversal("file..name.txt", field_name="path") == []


# ---------------------------------------------------------------------------
# check_owner_repo
# ---------------------------------------------------------------------------


class TestCheckOwnerRepo:
    def test_valid(self) -> None:
        assert check_owner_repo("octocat/hello-world", field_name="repo") == []

    def test_missing_slash(self) -> None:
        violations = check_owner_repo("octocat", field_name="repo")
        assert len(violations) == 1
        assert "owner/repo" in violations[0]

    def test_empty(self) -> None:
        violations = check_owner_repo("", field_name="repo")
        assert len(violations) == 1

    def test_multiple_slashes(self) -> None:
        violations = check_owner_repo("a/b/c", field_name="repo")
        assert len(violations) == 1

    def test_special_chars_in_segments(self) -> None:
        assert check_owner_repo("my-org/my_repo.v2", field_name="repo") == []


# ---------------------------------------------------------------------------
# validate_inputs
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_all_valid(self) -> None:
        result = validate_inputs(
            repo=check_owner_repo("a/b", field_name="repo"),
            path=check_no_path_traversal("src/x.py", field_name="path"),
        )
        assert result.valid is True
        assert result.violations == []

    def test_single_violation(self) -> None:
        result = validate_inputs(
            repo=check_owner_repo("bad", field_name="repo"),
        )
        assert result.valid is False
        assert len(result.violations) == 1

    def test_multiple_aggregated(self) -> None:
        result = validate_inputs(
            repo=check_owner_repo("bad", field_name="repo"),
            path=check_no_path_traversal("../x", field_name="path"),
        )
        assert result.valid is False
        assert len(result.violations) == 2

    def test_empty_checks(self) -> None:
        result = validate_inputs()
        assert result.valid is True
        assert result.violations == []


# ---------------------------------------------------------------------------
# InputValidationResult — model constraints
# ---------------------------------------------------------------------------


class TestInputValidationResult:
    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            InputValidationResult(valid=True, extra_field="nope")
