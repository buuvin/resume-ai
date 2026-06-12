from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_analyze_endpoint():
    payload = {
        "resume_text": "I built machine learning models using Python and pandas.",
        "job_description_text": "Looking for Python, machine learning, and SQL experience.",
        #"supplemental_text": "Built data pipelines for analytics."
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert "analysis" in data
    assert "improvements" in data
    assert isinstance(data["analysis"]["matched_skills"], list)
    assert isinstance(data["analysis"]["missing_skills"], list)
    assert isinstance(data["analysis"]["alignment_score"], float)
    assert data["improvements"]["rewritten_summary"] == ""
    assert data["improvements"]["rewritten_bullets"] == []
    assert data["improvements"]["explanations"] == [] 