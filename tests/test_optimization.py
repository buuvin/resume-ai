from types import SimpleNamespace

from app.services.analysis import build_optimization_analysis, normalize_optimization_evidence


def test_build_optimization_analysis_classifies_coverage_and_actions():
    requirements, evidence, coverage, gaps = build_optimization_analysis(
        {
            "embedding_bullets": {"python", "pandas", "sql"},
        },
        {
            "required": {"python", "sql"},
            "preferred": {"docker"},
        },
    )

    assert [(item.keyword, item.priority) for item in requirements] == [
        ("python", "required"),
        ("sql", "required"),
        ("docker", "preferred"),
    ]
    assert coverage[0].status == "covered"
    assert coverage[0].evidence[0].sections == ["embedding_bullets"]
    assert coverage[1].status == "underrepresented"
    assert coverage[2].status == "missing"
    assert {gap.action for gap in gaps} == {"promote", "augment"}
    assert {gap.requirement.keyword for gap in gaps} == {"sql", "docker"}


def test_resume_evidence_does_not_include_job_only_requirements():
    _, evidence, coverage, _ = build_optimization_analysis(
        {"experience": {"python"}},
        {"required": {"python", "kubernetes"}, "preferred": set()},
    )

    assert [item.keyword for item in evidence] == ["python"]
    kubernetes_coverage = next(
        item for item in coverage if item.requirement.keyword == "kubernetes"
    )
    assert kubernetes_coverage.status == "missing"
    assert kubernetes_coverage.evidence == []


def test_normalize_optimization_evidence_uses_high_similarity_bullets():
    result = SimpleNamespace(
        top_matches=[
            SimpleNamespace(
                resume_bullet="Built Python APIs",
                similarity_score=0.8,
            ),
            SimpleNamespace(
                resume_bullet="Unrelated work",
                similarity_score=0.4,
            ),
        ]
    )

    assert normalize_optimization_evidence(
        result,
        keyphrases={"Python APIs"},
        entities={"languages": ["python"], "frameworks": ["fastapi"]},
    ) == {
        "embedding_bullets": {"built", "python", "apis"},
        "keyphrases": {"python", "apis"},
        "entities": {"python", "fastapi"},
    }