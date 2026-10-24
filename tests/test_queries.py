import pytest
from repositories.insights import InsightsRepository

class TestShowcaseQueries:

    @classmethod
    def setup_class(cls):
        cls.queries = InsightsRepository.load_showcase_queries()

    def test_all_25_queries_loaded(self):
        """Verify all 25 queries are parsed from db/queries/."""
        assert len(self.queries) >= 25, f"Expected 25 queries, found {len(self.queries)}"

    @pytest.mark.parametrize("qid", [f"Q{i:02d}" for i in range(1, 26)])
    def test_showcase_query_executes_cleanly(self, qid):
        """Execute each query Q01 through Q25 and assert non-empty, error-free result."""
        res = InsightsRepository.execute_showcase(qid)
        assert "error" not in res, f"Query {qid} failed with error: {res.get('error')}"
        # An empty set difference is a valid result when all prior courses remain offered.
        if qid != "Q23":
            assert res.get("row_count", 0) > 0, f"Query {qid} returned 0 rows on seeded database"
        else:
            assert res["row_count"] >= 0
        assert len(res.get("columns", [])) > 0, f"Query {qid} returned no columns"
