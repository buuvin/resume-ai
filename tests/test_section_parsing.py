from app.services.analysis import parse_sections, extract_section_keywords, extract_job_keywords


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


def test_extract_section_keywords():
    text = """
    Skills
    Python, SQL, pandas

    Experience
    Built ETL pipelines in Python and Postgres
    """

    sk = extract_section_keywords(text)
    assert "skills" in sk
    assert "python" in sk["skills"]
    assert "postgresql" in sk["experience"] or "postgres" in sk["experience"]


def test_extract_job_keywords_with_requirements():
    job = """
    Requirements
    - Python
    - SQL

    Nice to have
    - Docker
    """

    jk = extract_job_keywords(job)
    assert "python" in jk["required"]
    assert "docker" in jk["preferred"]