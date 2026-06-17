from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.reviewer.pipeline import (
    _extract_added_code,
    _extract_new_function_names,
)


# ---------------------------------------------------------------------------
# Helper function tests (pure, no mocks needed)
# ---------------------------------------------------------------------------

def test_extract_added_code_strips_plus_prefix():
    patch = "@@ -1,3 +1,4 @@\n context\n+added line\n-removed line\n another context\n"
    result = _extract_added_code(patch)
    assert "added line" in result
    assert "removed line" not in result
    assert "context" not in result


def test_extract_added_code_ignores_hunk_header():
    patch = "+++ b/file.py\n+def foo(): pass\n"
    result = _extract_added_code(patch)
    assert "def foo(): pass" in result
    assert "+++ b/file.py" not in result


def test_extract_new_function_names_python():
    patch = "+def get_user(user_id):\n+    return user_id\n+async def fetch_data():\n+    pass\n"
    names = _extract_new_function_names(patch)
    assert "get_user" in names
    assert "fetch_data" in names


def test_extract_new_function_names_javascript():
    patch = "+function hashPassword(pw) {\n+    return pw;\n+}\n"
    names = _extract_new_function_names(patch)
    assert "hashPassword" in names


def test_extract_new_function_names_empty_patch():
    names = _extract_new_function_names("")
    assert names == []


def test_extract_added_code_empty_patch():
    result = _extract_added_code("")
    assert result == ""


# ---------------------------------------------------------------------------
# CodeRetriever tests (mocked DB + embedder)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_related_chunks_returns_empty_when_no_results(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    mock_embedder = MagicMock()
    mock_embedder.embed_single.return_value = [0.1] * 1536
    mock_embedder_cls.return_value = mock_embedder

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_col = MagicMock()
    mock_col.aggregate.return_value = mock_cursor
    mock_db.get_collection.return_value = mock_col

    retriever = CodeRetriever()
    results = await retriever.find_related_chunks(
        "def foo(): pass", "owner/repo", "src/foo.py"
    )
    assert results == []


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_related_chunks_filters_by_score_threshold(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    mock_embedder = MagicMock()
    mock_embedder.embed_single.return_value = [0.1] * 1536
    mock_embedder_cls.return_value = mock_embedder

    raw_results = [
        {"chunk_name": "high_score", "score": 0.90, "file_path": "other.py", "chunk_text": "..."},
        {"chunk_name": "low_score", "score": 0.50, "file_path": "other2.py", "chunk_text": "..."},
    ]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=raw_results)
    mock_col = MagicMock()
    mock_col.aggregate.return_value = mock_cursor
    mock_db.get_collection.return_value = mock_col

    retriever = CodeRetriever()
    results = await retriever.find_related_chunks(
        "def foo(): pass", "owner/repo", "src/foo.py"
    )
    assert len(results) == 1
    assert results[0]["chunk_name"] == "high_score"


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_related_chunks_returns_empty_for_blank_query(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    retriever = CodeRetriever()
    results = await retriever.find_related_chunks("   ", "owner/repo", "src/foo.py")
    assert results == []
    mock_db.get_collection.assert_not_called()


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_callers_and_callees_returns_empty_for_anonymous(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    retriever = CodeRetriever()
    results = await retriever.find_callers_and_callees("anonymous", "owner/repo")
    assert results == []
    mock_db.get_collection.assert_not_called()


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_callers_and_callees_queries_db(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    caller_chunk = {
        "chunk_name": "call_site",
        "chunk_text": "result = get_user(123)",
        "file_path": "service.py",
    }
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[caller_chunk])

    # find() returns a cursor with .limit() that also returns the cursor
    mock_find_cursor = MagicMock()
    mock_find_cursor.limit.return_value = mock_cursor
    mock_col = MagicMock()
    mock_col.find.return_value = mock_find_cursor
    mock_db.get_collection.return_value = mock_col

    retriever = CodeRetriever()
    results = await retriever.find_callers_and_callees("get_user", "owner/repo")
    assert len(results) == 1
    assert results[0]["chunk_name"] == "call_site"


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_related_chunks_handles_embedding_error_gracefully(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    mock_embedder = MagicMock()
    mock_embedder.embed_single.side_effect = Exception("OpenAI timeout")
    mock_embedder_cls.return_value = mock_embedder

    retriever = CodeRetriever()
    results = await retriever.find_related_chunks(
        "def foo(): pass", "owner/repo", "src/foo.py"
    )
    assert results == []


# ---------------------------------------------------------------------------
# find_similar_team_comments tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_similar_team_comments_returns_empty_for_blank_query(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    retriever = CodeRetriever()
    results = await retriever.find_similar_team_comments("   ", "owner/repo")
    assert results == []
    mock_db.get_collection.assert_not_called()


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_similar_team_comments_filters_by_score_threshold(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    mock_embedder = MagicMock()
    mock_embedder.embed_single.return_value = [0.1] * 1536
    mock_embedder_cls.return_value = mock_embedder

    raw_results = [
        {"code_context": "x = 1", "comment_body": "Use a constant", "reviewer_login": "alice", "score": 0.85},
        {"code_context": "y = 2", "comment_body": "Magic number", "reviewer_login": "bob", "score": 0.60},
    ]
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=raw_results)
    mock_col = MagicMock()
    mock_col.aggregate.return_value = mock_cursor
    mock_db.get_collection.return_value = mock_col

    retriever = CodeRetriever()
    results = await retriever.find_similar_team_comments("x = 1", "owner/repo")
    assert len(results) == 1
    assert results[0]["comment_body"] == "Use a constant"


@pytest.mark.asyncio
@patch("app.retriever.vector_search.db_client")
@patch("app.retriever.vector_search.EmbeddingGenerator")
async def test_find_similar_team_comments_returns_empty_on_db_error(mock_embedder_cls, mock_db):
    from app.retriever.vector_search import CodeRetriever

    mock_embedder = MagicMock()
    mock_embedder.embed_single.return_value = [0.1] * 1536
    mock_embedder_cls.return_value = mock_embedder

    mock_col = MagicMock()
    mock_col.aggregate.side_effect = Exception("Atlas unavailable")
    mock_db.get_collection.return_value = mock_col

    retriever = CodeRetriever()
    results = await retriever.find_similar_team_comments("def foo(): pass", "owner/repo")
    assert results == []
