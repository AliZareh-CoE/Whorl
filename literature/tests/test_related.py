import pytest

from literature.related import related_references, tokenize

from .factories import ReferenceFactory

pytestmark = pytest.mark.django_db


class TestRelated:
    def test_topically_similar_ranks_above_unrelated(self):
        target = ReferenceFactory(
            title="Working memory load modulates sustained attention",
            abstract="Dual-task experiments show working memory load changes attention allocation.",
        )
        similar = ReferenceFactory(
            title="Attention allocation under working memory load",
            abstract="We test dual-task interference between memory load and attention.",
        )
        unrelated = ReferenceFactory(
            title="Coral reef bleaching dynamics in warming oceans",
            abstract="Sea surface temperature drives coral symbiont loss.",
        )
        results = related_references(target)
        refs = [ref for ref, _ in results]
        assert similar in refs
        assert unrelated not in refs or refs.index(similar) < refs.index(unrelated)
        assert results[0][0] == similar

    def test_excludes_self_and_respects_limit(self):
        target = ReferenceFactory(title="Memory and attention interplay")
        for i in range(8):
            ReferenceFactory(
                title=f"Memory and attention interplay variant {i}",
                abstract="memory attention interplay",
            )
        results = related_references(target, limit=5)
        assert len(results) == 5
        assert all(ref != target for ref, _ in results)

    def test_no_library_no_suggestions(self):
        target = ReferenceFactory(title="Lonely paper about nothing else")
        assert related_references(target) == []

    def test_min_score_filters_noise(self):
        target = ReferenceFactory(title="Quantum chromodynamics lattice simulations")
        ReferenceFactory(title="Victorian poetry and the sublime")
        assert related_references(target) == []

    def test_tokenize_drops_stopwords_and_short_words(self):
        ref = ReferenceFactory(title="The effect of load on the brain", abstract="")
        tokens = tokenize(ref)
        assert "the" not in tokens
        assert "of" not in tokens
        assert "load" in tokens
        assert "brain" in tokens

    def test_api_related_endpoint(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        target = ReferenceFactory(
            title="Spatial attention and visual working memory",
            abstract="attention memory visual spatial",
        )
        ReferenceFactory(
            title="Visual working memory guides spatial attention",
            abstract="spatial attention visual memory",
        )
        response = client.get(f"/api/v1/references/{target.pk}/related/", HTTP_X_API_KEY="k")
        assert response.status_code == 200
        data = response.json()
        assert data and data[0]["score"] > 0
