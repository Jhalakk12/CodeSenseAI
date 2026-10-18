"""
Unit tests for Feature 2: Hybrid Dual-LLM Engine (Cloud Turbo Groq vs. Local Privacy Ollama)
and Automatic Failover Mechanisms.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from rag_engine import CodeSenseEngine, check_ollama_status


def test_check_ollama_status_offline():
    """Verify check_ollama_status gracefully reports offline when daemon is unreachable."""
    status = check_ollama_status(base_url="http://localhost:59999", timeout=0.5)
    assert status["running"] is False
    assert status["models"] == []
    assert status["error"] is not None


def test_check_ollama_status_online_mock():
    """Verify check_ollama_status parses installed models from HTTP response."""
    mock_payload = b'{"models": [{"name": "qwen2.5:1.5b"}, {"name": "smollm2:latest"}]}'
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = mock_payload
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        status = check_ollama_status("http://localhost:11434")
        assert status["running"] is True
        assert "qwen2.5:1.5b" in status["models"]
        assert "smollm2:latest" in status["models"]
        assert status["error"] is None


def test_unsupported_provider_raises_error():
    """Verify that unsupported providers raise an informative ValueError."""
    engine = CodeSenseEngine()
    with pytest.raises(ValueError, match="Unsupported inference provider"):
        engine.query_codebase(
            query="test query",
            api_key="mock_key",
            provider="UnsupportedProvider"
        )


def test_groq_missing_key_raises_error():
    """Verify Groq Cloud mode demands an API key if not provided."""
    engine = CodeSenseEngine()
    with pytest.raises(ValueError, match="Groq API Key is required"):
        engine.query_codebase(
            query="test query",
            api_key="",
            provider="Groq"
        )


def test_ollama_offline_raises_connection_error():
    """Verify selecting Ollama when the daemon is offline raises ConnectionError."""
    engine = CodeSenseEngine()
    with pytest.raises(ConnectionError, match="Local Ollama daemon is not responding"):
        engine.query_codebase(
            query="test query",
            provider="Ollama",
            ollama_base_url="http://localhost:59999"
        )


def test_automatic_failover_from_groq_to_ollama():
    """Verify automatic failover triggers seamlessly when Groq encounters a rate limit or API error."""
    engine = CodeSenseEngine()

    # Mock similarity search to return sample doc
    mock_doc = MagicMock()
    mock_doc.page_content = "def test_func(): return True"
    mock_doc.metadata = {"source": "test.py", "chunk_id": 0}

    # Mock ChatGroq to simulate 429 RateLimit error
    with patch.object(engine.vector_store, "similarity_search_with_score", return_value=[(mock_doc, 0.12)]), \
         patch("rag_engine.ChatGroq") as mock_groq_cls, \
         patch("rag_engine.check_ollama_status") as mock_ollama_status, \
         patch.object(engine, "_create_ollama_chat") as mock_ollama_chat:

        # Groq raises RateLimitException
        mock_groq_instance = MagicMock()
        mock_groq_instance.__or__ = MagicMock()
        mock_groq_cls.return_value = mock_groq_instance

        # Simulate pipeline invocation failing on Groq
        def fail_invoke(*args, **kwargs):
            raise Exception("Rate limit reached: 429 Too Many Requests, OTPM ceiling exceeded")
        
        # When prompt_template | mock_groq_instance | StrOutputParser is invoked:
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = fail_invoke
        
        # Patch ChatPromptTemplate pipeline
        with patch("rag_engine.ChatPromptTemplate.from_messages") as mock_pt:
            mock_pt_instance = MagicMock()
            # First chain (Groq) fails
            # Second chain (Ollama failover) succeeds
            mock_fallback_chain = MagicMock()
            mock_fallback_chain.invoke.return_value = "Fallback answer from local Ollama model"
            
            mock_pt_instance.__or__.side_effect = [
                MagicMock(__or__=MagicMock(return_value=mock_chain)),            # Groq chain
                MagicMock(__or__=MagicMock(return_value=mock_fallback_chain))     # Ollama failover chain
            ]
            mock_pt.return_value = mock_pt_instance

            # Ollama is running with qwen2.5:1.5b
            mock_ollama_status.return_value = {"running": True, "models": ["qwen2.5:1.5b"], "error": None}
            mock_ollama_chat.return_value = MagicMock()

            res = engine.query_codebase(
                query="How does authentication work?",
                api_key="gsk_mock_key",
                provider="Groq",
                enable_failover=True
            )

            assert "Ollama" in res["provider_used"]
            assert res["failover"] is not None
            assert res["failover"]["triggered"] is True
            assert res["failover"]["fallback_model"] == "qwen2.5:1.5b"
            assert "Fallback answer from local Ollama" in res["answer"]
