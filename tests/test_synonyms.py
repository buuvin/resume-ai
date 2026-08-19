from app.services.analysis import extract_keywords


def test_synonym_canonicalization():
    text = """
    Skills
    ETL, data pipelines, AWS Lambda, ml
    """

    kws = extract_keywords(text)
    assert "data pipeline" in kws
    assert "amazon web services" in kws
    assert "machine learning" in kws
# *** End Patch ***