from io import BytesIO

from reportlab.pdfgen import canvas
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def make_pdf(text):
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(72, 720, text)
    document.save()
    buffer.seek(0)
    return buffer

def test_analyze_endpoint():
    payload = {
        "resume_text": "I built machine learning models using Python and pandas.",
        "job_description_text": "Looking for Python, machine learning, and SQL experience.",
        "supplemental_text": "Built SQL data pipelines for analytics.",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert "analysis" in data
    assert "improvements" in data
    assert isinstance(data["analysis"]["matched_skills"], list)
    assert isinstance(data["analysis"]["missing_skills"], list)
    assert isinstance(data["analysis"]["alignment_score"], float)
    assert isinstance(data["analysis"]["resume_keyword_count"], int)
    assert isinstance(data["analysis"]["job_keyword_count"], int)
    assert isinstance(data["analysis"]["supplemental_keyword_count"], int)
    assert isinstance(data["analysis"]["supplemental_used"], bool)
    assert data["analysis"]["supplemental_keyword_count"] > 0
    assert data["analysis"]["supplemental_used"] is True
    assert "sql" in data["analysis"]["matched_skills"]
    assert data["improvements"]["rewritten_summary"]
    assert data["improvements"]["rewritten_bullets"] == []
    assert data["improvements"]["explanations"]


def test_root_serves_frontend():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Resume AI" in response.text


def test_analyze_upload_extracts_pdf_resume():
    response = client.post(
        "/analyze-upload",
        data={"job_description_text": "Requirements\nPython"},
        files={"resume_file": ("resume.pdf", make_pdf("Python developer"), "application/pdf")},
    )

    assert response.status_code == 200
    assert "python" in response.json()["analysis"]["matched_skills"]