from io import BytesIO

from reportlab.pdfgen import canvas
from fastapi.testclient import TestClient
from app.main import app
from app.services.analysis import extract_domain_entities

client = TestClient(app)


def test_domain_entities_include_ai_engineering_concepts():
    entities = extract_domain_entities(
        "Built an NLP system with an LLM using retrieval augmented generation for data science."
    )

    assert entities["concepts"] == [
        "data science",
        "large language model",
        "natural language processing",
        "retrieval augmented generation",
    ]


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
        "job_description_text": "Requirements\nPython\nMachine learning model development\nSQL experience",
        "supplemental_text": "Built SQL data pipelines for analytics.",
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert "analysis" in data
    assert "improvements" in data
    assert isinstance(data["analysis"]["matched_skills"], list)
    assert isinstance(data["analysis"]["underrepresented_skills"], list)
    assert isinstance(data["analysis"]["missing_skills"], list)
    assert isinstance(data["analysis"]["alignment_score"], float)
    assert data["analysis"]["resume_entities"]["languages"] == ["python"]
    assert data["analysis"]["job_description_entities"]["languages"] == ["python"]
    assert data["analysis"]["supplemental_entities"]["databases"] == []
    assert data["analysis"]["alignment_evidence"]
    assert {
        item["source"] for item in data["analysis"]["alignment_evidence"]
    } <= {"ner", "keybert", "bulletpoints"}
    assert all(
        item["requirement"] in {
            "Python",
            "Machine learning model development",
            "SQL experience",
        }
        for item in data["analysis"]["alignment_evidence"]
    )
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
    assert response.json()["analysis"]["alignment_evidence"]