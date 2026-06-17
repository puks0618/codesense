import hashlib
from unittest.mock import MagicMock, patch

import pytest

from app.indexer.parser import CodeParser

PYTHON_SAMPLE = '''\
def greet(name: str) -> str:
    return f"Hello, {name}!"

async def fetch_user(user_id: int):
    return {"id": user_id}

class UserService:
    def get_user(self, user_id: int):
        return {"id": user_id}

    def delete_user(self, user_id: int):
        return True
'''

JS_SAMPLE = '''\
class AuthService {
    login(username, password) {
        return true;
    }

    logout(token) {
        return null;
    }
}

function hashPassword(password) {
    return password;
}
'''

UNSUPPORTED_CONTENT = "key: value\nother: stuff\n"


@pytest.fixture
def parser():
    return CodeParser()


def test_parse_python_identifies_functions(parser):
    chunks = parser.parse_file("service.py", PYTHON_SAMPLE)
    names = [c["chunk_name"] for c in chunks]
    assert "greet" in names


def test_parse_python_identifies_async_functions(parser):
    chunks = parser.parse_file("service.py", PYTHON_SAMPLE)
    names = [c["chunk_name"] for c in chunks]
    assert "fetch_user" in names


def test_parse_python_identifies_class(parser):
    chunks = parser.parse_file("service.py", PYTHON_SAMPLE)
    types = {c["chunk_type"] for c in chunks}
    assert "class" in types


def test_parse_javascript_identifies_class(parser):
    chunks = parser.parse_file("auth.js", JS_SAMPLE)
    names = [c["chunk_name"] for c in chunks]
    assert "AuthService" in names or any("login" in n or "logout" in n for n in names)


def test_parse_javascript_identifies_function(parser):
    chunks = parser.parse_file("auth.js", JS_SAMPLE)
    names = [c["chunk_name"] for c in chunks]
    assert "hashPassword" in names


def test_parse_unsupported_file_returns_module_chunk(parser):
    chunks = parser.parse_file("config.yaml", UNSUPPORTED_CONTENT)
    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "module"


def test_parse_unknown_extension_returns_module_chunk(parser):
    chunks = parser.parse_file("Makefile", "all:\n\techo hello\n")
    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "module"


def test_chunk_text_never_exceeds_limit(parser):
    large_source = "def fn_{}():\n    x = {}\n    return x\n\n".join(str(i) for i in range(200))
    large_source += "\ndef extra(): pass\n"
    chunks = parser.parse_file("big.py", large_source)
    for chunk in chunks:
        assert len(chunk["chunk_text"]) <= 6000, f"Chunk {chunk['chunk_name']} exceeds 6000 chars"


def test_get_language_returns_correct_values(parser):
    assert parser.get_language("main.py") == "python"
    assert parser.get_language("app.js") == "javascript"
    assert parser.get_language("util.mjs") == "javascript"
    assert parser.get_language("types.ts") == "typescript"
    assert parser.get_language("component.tsx") == "tsx"
    assert parser.get_language("handler.go") == "go"
    assert parser.get_language("Service.java") == "java"


def test_get_language_unknown_returns_none(parser):
    assert parser.get_language("config.yaml") is None
    assert parser.get_language("README.md") is None
    assert parser.get_language("data.csv") is None


def test_parse_chunks_have_required_fields(parser):
    chunks = parser.parse_file("service.py", PYTHON_SAMPLE)
    for chunk in chunks:
        assert "chunk_type" in chunk
        assert "chunk_name" in chunk
        assert "chunk_text" in chunk
        assert "start_line" in chunk
        assert "end_line" in chunk
        assert chunk["start_line"] >= 1
        assert chunk["end_line"] >= chunk["start_line"]


@patch("app.indexer.embedder.openai.OpenAI")
def test_embed_chunks_batches_correctly_for_over_100(mock_openai_cls):
    from app.indexer.embedder import EmbeddingGenerator

    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    def make_response(model, input):
        r = MagicMock()
        r.data = [MagicMock(embedding=[0.1] * 1536) for _ in input]
        return r

    mock_client.embeddings.create.side_effect = make_response

    gen = EmbeddingGenerator()
    chunks = [{"chunk_name": f"fn_{i}", "chunk_text": f"def fn_{i}(): pass"} for i in range(150)]
    result = gen.embed_chunks(chunks, "large_file.py")

    # 150 chunks / batch_size 100 = 2 API calls
    assert mock_client.embeddings.create.call_count == 2
    assert len(result) == 150
    assert all("embedding" in c for c in result)
    assert all(len(c["embedding"]) == 1536 for c in result)


@patch("app.indexer.embedder.openai.OpenAI")
def test_file_hash_is_consistent(mock_openai_cls):
    from app.indexer.embedder import EmbeddingGenerator

    gen = EmbeddingGenerator()
    source = "def foo(): pass"
    expected = hashlib.sha256(source.encode("utf-8")).hexdigest()

    assert gen.file_hash(source) == expected
    assert gen.file_hash(source) == gen.file_hash(source)


@patch("app.indexer.embedder.openai.OpenAI")
def test_file_hash_changes_when_file_changes(mock_openai_cls):
    from app.indexer.embedder import EmbeddingGenerator

    gen = EmbeddingGenerator()
    source = "def foo(): pass"
    modified = "def foo(): return 1"
    assert gen.file_hash(source) != gen.file_hash(modified)


@patch("app.indexer.embedder.openai.OpenAI")
def test_embed_chunks_adds_embedding_field(mock_openai_cls):
    from app.indexer.embedder import EmbeddingGenerator

    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
    mock_client.embeddings.create.return_value = mock_response

    gen = EmbeddingGenerator()
    chunks = [{"chunk_name": "foo", "chunk_text": "def foo(): pass"}]
    result = gen.embed_chunks(chunks, "test.py")

    assert result[0]["embedding"] == [0.5] * 1536
    assert result[0]["chunk_name"] == "foo"  # original fields preserved
