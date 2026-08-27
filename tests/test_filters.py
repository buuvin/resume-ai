from app.services.analysis import extract_domain_entities, extract_keywords


def test_domain_entities_are_grouped_and_canonicalized():
    entities = extract_domain_entities(
        "Built ML APIs with PY, FastAPI, AWS, Docker, and Postgres."
    )

    assert entities == {
        "languages": ["python"],
        "frameworks": ["fastapi"],
        "platforms": ["aws"],
        "tools": ["docker"],
        "databases": ["postgresql"],
    }


def test_domain_entities_require_whole_terms():
    entities = extract_domain_entities(
        "Experience with javascript and pandas, not javadoc or rediscovery."
    )

    assert entities["languages"] == ["javascript"]
    assert entities["tools"] == ["pandas"]
    assert entities["databases"] == []


def test_stopword_and_numeric_filtering():
    text = """
    Skills
    Python, the and for 2019 1234
    Experience
    Responsible for leading a team
    """

    kws = extract_keywords(text)
    assert "python" in kws
    assert "2019" not in kws
    assert "1234" not in kws
    assert "responsible for" not in kws
    assert "team" not in kws


def test_phrase_blacklist_removal():
    text = """
    Experience
    Responsible for machine learning projects
    """

    kws = extract_keywords(text)
    # 'responsible for' is blacklisted; machine learning should remain
    assert "machine learning" in kws
    assert "responsible for" not in kws