from app.services.analysis import (
    parse_sections,
    preprocess_for_semantic_extraction,
    strip_heading_lines,
    strip_subheader_labels,
)


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


def test_parse_sections_never_treats_bullet_lines_as_headings():
    # A bullet that starts with a heading word is content: before Phase 3
    # the prefix match swallowed it (and lost its text) entirely.
    text = "Experience\n- Experience with Git and CI/CD\n- Skills in demand"

    sections = parse_sections(text)

    assert list(sections) == ["experience"]
    assert "- Experience with Git and CI/CD" in sections["experience"]
    assert "- Skills in demand" in sections["experience"]


def test_parse_sections_requires_whole_line_heading_match():
    # Prefix matching removed: "Requirements for the role" is a sentence,
    # not the "requirements" section.
    sections = parse_sections("Requirements for the role\nPython")

    assert list(sections) == ["summary"]
    assert "Requirements for the role" in sections["summary"]
    assert "Python" in sections["summary"]


def test_strip_subheader_labels_keeps_value_side():
    text = """\
Programming & Tools: Python, SQL, Git, Docker, Copilot
Machine Learning: scikit-learn, TensorFlow, Pytorch
Degree: Bachelor of Science in Data Science
"""

    assert strip_subheader_labels(text) == (
        "Python, SQL, Git, Docker, Copilot\n"
        "scikit-learn, TensorFlow, Pytorch\n"
        "Bachelor of Science in Data Science"
    )


def test_strip_subheader_labels_keeps_plain_and_sentence_lines():
    text = """\
● Designed and implemented end-to-end ML pipelines for noisy data
Built pipelines: the pipeline consumed sensor streams
Sentences with a long label before the colon are left alone: like this one
"""

    assert strip_subheader_labels(text) == (
        "● Designed and implemented end-to-end ML pipelines for noisy data\n"
        "the pipeline consumed sensor streams\n"
        "Sentences with a long label before the colon are left alone: like this one"
    )


def test_strip_subheader_labels_drops_empty_value_lines():
    text = "Skills:\nPython"

    assert strip_subheader_labels(text) == "Python"


def test_strip_heading_lines_removes_only_exact_headings():
    text = """\
SKILLS
Programming & Tools: Python, SQL
WORK EXPERIENCE
● Designed and implemented ML pipelines
- Experience with statistical analysis, visualization, and modeling
"""

    cleaned = strip_heading_lines(text)

    assert "SKILLS" not in cleaned
    assert "WORK EXPERIENCE" not in cleaned
    # Prefix matches must survive: bullets starting with heading words are content.
    assert "Experience with statistical analysis" in cleaned


def test_preprocess_for_semantic_extraction_combines_both_filters():
    text = """\
SKILLS
Programming & Tools: Python, SQL, Git, Docker, Copilot
WORK EXPERIENCE
● Built APIs in Python
"""

    cleaned = preprocess_for_semantic_extraction(text)

    assert cleaned == "Python, SQL, Git, Docker, Copilot\n● Built APIs in Python"


def test_preprocess_for_semantic_extraction_on_reference_resume():
    import pytest

    pdfplumber = pytest.importorskip("pdfplumber")
    from pathlib import Path

    pdf_path = (
        Path(__file__).resolve().parents[1] / "input" / "Bhuvan_Balagar_Resume-1.pdf"
    )
    with pdfplumber.open(pdf_path) as pdf:
        resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    cleaned = preprocess_for_semantic_extraction(resume_text).lower()

    for heading in ("skills", "work experience", "project experience", "education"):
        assert f"\n{heading}\n" not in f"\n{cleaned}\n"
    # The value side of the skills subheaders is preserved.
    assert "python, sql, git, docker, copilot" in cleaned
    assert "scikit-learn, tensorflow, pytorch" in cleaned

