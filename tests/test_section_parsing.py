from app.services.analysis import parse_sections


def test_parse_sections_basic():
    text = """
    Summary
    Experienced engineer with Python.

    Skills
    Python, SQL, pandas

    Experience
    Worked at Acme Corp.
    """

    sections = parse_sections(text)
    assert "summary" in sections
    assert "skills" in sections
    assert "experience" in sections
    assert "Python" in sections["summary"] or "python" in sections["summary"].lower()

