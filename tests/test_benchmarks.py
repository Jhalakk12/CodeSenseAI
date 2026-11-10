"""
Unit tests for Feature 4: Quantitative Benchmarking Dashboard (RAG Triad & Latency Benchmarks)
Validates Context Relevance, Groundedness (hallucination defense), Answer Relevance,
composite Triad scoring, latency profiler, and benchmark report generation.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pytest
except ImportError:
    pass
from scripts.benchmark_engine import BenchmarkEngine


def test_standard_eval_suite_structure():
    """Verify standard evaluation queries have complete metadata."""
    suite = BenchmarkEngine.STANDARD_EVAL_SUITE
    assert len(suite) >= 5
    for item in suite:
        assert "id" in item
        assert "category" in item
        assert "query" in item
        assert "target_file" in item
        assert len(item["ground_truth_tokens"]) >= 3


def test_dynamic_repo_adaptation():
    """Verify BenchmarkEngine dynamically inspects AST of any custom repo."""
    # Test with sample_repo -> returns STANDARD_EVAL_SUITE
    suite_sample = BenchmarkEngine.get_eval_suite_for_repo("sample_repo")
    assert suite_sample == BenchmarkEngine.STANDARD_EVAL_SUITE

    # Test with scripts directory as custom repository
    suite_custom = BenchmarkEngine.get_eval_suite_for_repo("scripts")
    assert len(suite_custom) >= 3
    for item in suite_custom:
        assert "query" in item
        assert len(item["ground_truth_tokens"]) >= 1


def test_context_relevance_calculation():
    """Verify Context Relevance accurately scores token matches and distance."""
    retrieved_chunks = [
        {
            "source": "sample_repo/auth/jwt_handler.py",
            "score": 0.45,  # Low distance = high similarity
            "snippet": "def create_access_token(data, expires_delta): SECRET_KEY = 'codesense' ALGORITHM = 'HS256' return jwt.encode()"
        },
        {
            "source": "sample_repo/auth/jwt_handler.py",
            "score": 0.50,
            "snippet": "def verify_token(token): return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])"
        }
    ]
    expected_tokens = ["create_access_token", "SECRET_KEY", "HS256", "jwt.encode"]
    
    score = BenchmarkEngine.calculate_context_relevance(retrieved_chunks, expected_tokens)
    assert 0.0 <= score <= 1.0
    # Both expected tokens and low distance are present, score should be >= 0.80
    assert score >= 0.80

    # Irrelevant chunks test
    irrelevant_chunks = [
        {"source": "misc/unknown.py", "score": 1.8, "snippet": "print('hello world')"}
    ]
    irrelevant_score = BenchmarkEngine.calculate_context_relevance(irrelevant_chunks, expected_tokens)
    assert irrelevant_score < score


def test_groundedness_faithfulness():
    """Verify Groundedness detects hallucinations and rewards strictly supported answers."""
    context_chunks = [
        {
            "source": "sample_repo/auth/jwt_handler.py",
            "snippet": "def create_access_token(data, expires_delta): SECRET_KEY = 'codesense' ALGORITHM = 'HS256' return jwt.encode()"
        }
    ]

    # Grounded answer
    grounded_answer = "The function create_access_token uses SECRET_KEY with ALGORITHM HS256 to call jwt.encode."
    score_grounded = BenchmarkEngine.calculate_groundedness(grounded_answer, context_chunks)
    assert score_grounded >= 0.80

    # Hallucinated answer (claiming non-existent functions and classes)
    hallucinated_answer = "The system calls OAuthProviderFederationGateway and invokeDistributedKerberosTicketValidation."
    score_hallucinated = BenchmarkEngine.calculate_groundedness(hallucinated_answer, context_chunks)
    assert score_hallucinated < score_grounded


def test_answer_relevance():
    """Verify Answer Relevance scores query alignment and structural completeness."""
    query = "How is the JWT access token signed?"
    relevant_answer = "The JWT access token is signed using `create_access_token` with the `HS256` algorithm and secret key."
    score_rel = BenchmarkEngine.calculate_answer_relevance(query, relevant_answer)
    assert score_rel >= 0.70

    # Empty or off-topic answer
    empty_score = BenchmarkEngine.calculate_answer_relevance(query, "")
    assert empty_score == 0.0


def test_calibrated_baseline_metrics():
    """Verify baseline model matrix contains Groq, Ollama, and legacy Grep comparative data."""
    engine = BenchmarkEngine()
    data = engine.get_calibrated_baseline_metrics()
    assert "models" in data
    assert len(data["models"]) >= 4

    groq_model = next((m for m in data["models"] if "Groq" in m["name"]), None)
    assert groq_model is not None
    assert groq_model["tokens_per_sec"] > 200

    ollama_model = next((m for m in data["models"] if "Ollama" in m["name"]), None)
    assert ollama_model is not None
    assert "0.00" in ollama_model["cost_per_10k"]


def test_generate_markdown_report():
    """Verify Markdown report generation compiles proper GitHub Flavored Markdown."""
    engine = BenchmarkEngine()
    sample_suite_data = {
        "summary": {
            "total_queries_tested": 2,
            "context_relevance": 0.95,
            "groundedness": 0.97,
            "answer_relevance": 0.94,
            "triad_score": 0.953,
            "avg_retrieval_ms": 42.1,
            "avg_llm_ms": 460.0,
            "avg_total_ms": 502.1,
            "timestamp": "2026-11-09 21:00:00"
        },
        "queries": [
            {
                "id": "BENCH-01",
                "category": "Authentication",
                "context_relevance": 0.95,
                "groundedness": 0.98,
                "answer_relevance": 0.94,
                "triad_score": 0.956,
                "total_latency_ms": 490.5
            }
        ]
    }
    report = engine.generate_markdown_report(sample_suite_data)
    assert "# 📊 CodeSense AI — Quantitative Benchmarking" in report
    assert "Context Relevance" in report
    assert "BENCH-01" in report
    assert "Groq LPU" in report
