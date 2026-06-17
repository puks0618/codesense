from unittest.mock import MagicMock, patch

import pytest

from app.github.models import ChangedFile, DiffResult
from app.llm.reviewer import LLMReviewer, _extract_addition_lines, _should_skip


SAMPLE_DIFF = """\
@@ -1,3 +1,8 @@
 def get_user(user_id):
+    query = f"SELECT * FROM users WHERE id = {user_id}"
+    cursor.execute(query)
+    return cursor.fetchone()
+
+def delete_user(user_id):
+    os.system(f"rm -rf /data/users/{user_id}")
+    return True
"""

VALID_LLM_RESPONSE = """{
  "comments": [
    {
      "line": 2,
      "severity": "critical",
      "category": "security",
      "title": "SQL injection vulnerability here",
      "body": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"
    },
    {
      "line": 6,
      "severity": "critical",
      "category": "security",
      "title": "Command injection via os.system",
      "body": "Never interpolate user input into shell commands. Use shutil.rmtree with validated paths."
    }
  ],
  "file_summary": "Contains two critical security vulnerabilities.",
  "has_critical_issues": true
}"""


def _make_mock_message(text: str):
    content_block = MagicMock()
    content_block.text = text
    message = MagicMock()
    message.content = [content_block]
    return message


def test_skip_lock_file():
    reviewer = LLMReviewer()
    result = reviewer.review_file("package-lock.json", "diff content", "title", "body")
    assert result["comments"] == []


def test_skip_generated_file():
    reviewer = LLMReviewer()
    result = reviewer.review_file("src/api.generated.ts", "diff", "title", "body")
    assert result["comments"] == []


def test_skip_snapshot_file():
    reviewer = LLMReviewer()
    result = reviewer.review_file("__snapshots__/component.snap", "diff", "title", "body")
    assert result["comments"] == []


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_review_file_parses_valid_json(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message(VALID_LLM_RESPONSE)

    reviewer = LLMReviewer()
    result = reviewer.review_file("service.py", SAMPLE_DIFF, "Fix auth", "")

    assert len(result["comments"]) == 2
    assert result["comments"][0]["severity"] == "critical"
    assert result["has_critical_issues"] is True


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_review_file_handles_malformed_json(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message("not valid json {{{")

    reviewer = LLMReviewer()
    result = reviewer.review_file("service.py", SAMPLE_DIFF, "Fix auth", "")

    assert result["comments"] == []


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_review_file_filters_non_addition_lines(mock_anthropic_cls):
    response_with_invalid_line = """{
      "comments": [
        {"line": 1, "severity": "warning", "category": "style", "title": "context line flagged", "body": "..."},
        {"line": 2, "severity": "critical", "category": "security", "title": "valid addition", "body": "..."}
      ],
      "file_summary": "test",
      "has_critical_issues": true
    }"""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message(response_with_invalid_line)

    reviewer = LLMReviewer()
    result = reviewer.review_file("service.py", SAMPLE_DIFF, "title", "body")

    valid_lines = _extract_addition_lines(SAMPLE_DIFF)
    assert 1 not in valid_lines
    assert 2 in valid_lines
    assert all(c["line"] in valid_lines for c in result["comments"])


def test_generate_summary_request_changes_on_critical():
    reviewer = LLMReviewer()
    comments = [{"severity": "critical", "file_path": "a.py", "line": 1}]
    diff = DiffResult(
        files=[ChangedFile(filename="a.py", status="modified", patch="", additions=5, deletions=2)],
        total_additions=5, total_deletions=2,
    )
    _, verdict = reviewer.generate_summary(comments, diff)
    assert verdict == "REQUEST_CHANGES"


def test_generate_summary_approve_on_empty_comments():
    reviewer = LLMReviewer()
    diff = DiffResult(
        files=[ChangedFile(filename="a.py", status="modified", patch="", additions=3, deletions=1)],
        total_additions=3, total_deletions=1,
    )
    _, verdict = reviewer.generate_summary([], diff)
    assert verdict == "APPROVE"


def test_generate_summary_request_changes_on_many_warnings():
    reviewer = LLMReviewer()
    comments = [{"severity": "warning"} for _ in range(4)]
    diff = DiffResult(files=[], total_additions=0, total_deletions=0)
    _, verdict = reviewer.generate_summary(comments, diff)
    assert verdict == "REQUEST_CHANGES"


def test_generate_summary_comment_on_suggestions_only():
    reviewer = LLMReviewer()
    comments = [{"severity": "suggestion"}, {"severity": "info"}]
    diff = DiffResult(files=[], total_additions=10, total_deletions=0)
    _, verdict = reviewer.generate_summary(comments, diff)
    assert verdict == "COMMENT"


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_review_file_includes_team_style_section(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message(VALID_LLM_RESPONSE)

    team_chunks = [
        {"code_context": "cursor.execute(query)", "comment_body": "Use parameterized queries."}
    ]
    reviewer = LLMReviewer()
    reviewer.review_file("service.py", SAMPLE_DIFF, "Fix auth", "", team_style_chunks=team_chunks)

    call_kwargs = mock_client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "TEAM STYLE EXAMPLES" in prompt
    assert "Use parameterized queries." in prompt


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_respond_to_thread_first_reply_starts_with_user(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message("Here's how to fix it.")

    reviewer = LLMReviewer()
    result = reviewer.respond_to_thread(
        original_code="def foo(): pass",
        original_comment="This function lacks a return type hint.",
        thread_history=[],
        developer_message="How do I fix this?",
    )

    assert result == "Here's how to fix it."
    call_kwargs = mock_client.messages.create.call_args[1]
    messages = call_kwargs["messages"]
    # Must start with user (Anthropic API requirement)
    assert messages[0]["role"] == "user"
    assert messages[-1]["role"] == "user"
    assert "How do I fix this?" in messages[-1]["content"]


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_respond_to_thread_reconstructs_history(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_mock_message("Glad that helps!")

    history = [
        {"role": "developer", "content": "Why is this a security issue?"},
        {"role": "codesense", "content": "Because user input is interpolated directly."},
    ]

    reviewer = LLMReviewer()
    reviewer.respond_to_thread("code", "original comment", history, "OK, I'll fix it.")

    call_kwargs = mock_client.messages.create.call_args[1]
    messages = call_kwargs["messages"]
    # history[0]=user, history[1]=assistant, new_dev_msg=user
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert "OK, I'll fix it." in messages[2]["content"]


@patch("app.llm.reviewer.anthropic.Anthropic")
def test_respond_to_thread_api_error_returns_fallback(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = Exception("API timeout")

    reviewer = LLMReviewer()
    result = reviewer.respond_to_thread("code", "comment", [], "help?")

    assert "error" in result.lower()
