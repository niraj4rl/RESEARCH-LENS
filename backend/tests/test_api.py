import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import SessionLocal
from models import Analysis, Paper, ResearchGap, GapEvidence

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_analyze_endpoint_validation():
    # Empty query should fail
    response = client.post("/api/research/analyze", json={"query": "   "})
    assert response.status_code == 400
    assert "Query must be a non-empty string" in response.text

    # Extremely long query should fail
    long_query = "x" * 600
    response = client.post("/api/research/analyze", json={"query": long_query})
    assert response.status_code == 400
    assert "Query is too long" in response.text

def test_analyze_and_results_flow():
    # Submit search
    res = client.post("/api/research/analyze", json={"query": "recommender systems for cold-start users"})
    assert res.status_code == 202
    data = res.json()
    assert "id" in data
    analysis_id = data["id"]
    assert data["status"] in ["pending", "running"]

    # Check status endpoint
    status_res = client.get(f"/api/research/{analysis_id}")
    assert status_res.status_code == 200
    assert status_res.json()["id"] == analysis_id

    # Check results endpoint
    results_res = client.get(f"/api/research/{analysis_id}/results")
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert results_data["search_id"] == analysis_id
    assert "corpus" in results_data
    assert "gaps" in results_data
    assert isinstance(results_data["gaps"], list)

def test_nonexistent_analysis_returns_404():
    res = client.get("/api/research/non-existent-uuid-1234")
    assert res.status_code == 404

def test_retrieval_provider_failures(monkeypatch):
    """Ensure that when a provider raises an exception, the system catches it gracefully."""
    from providers.openalex import OpenAlexProvider
    from providers.arxiv import ArxivProvider
    
    # Mock OpenAlex to raise a simulated network connection failure
    def failing_search(*args, **kwargs):
        raise ConnectionError("Simulated OpenAlex server outage")
        
    monkeypatch.setattr(OpenAlexProvider, "search_papers", failing_search)
    
    # Analysis should still accept the request and survive provider failure
    res = client.post("/api/research/analyze", json={"query": "quantum computing", "limit": 10})
    assert res.status_code == 202
    data = res.json()
    assert "id" in data

