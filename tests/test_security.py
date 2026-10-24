import pytest
from repositories.students import StudentRepository
from repositories.db_pool import db_pool

class TestSecurity:

    def test_sql_injection_in_search_does_not_break(self):
        """
        Inject classic SQL injection payloads into search parameter:
        ' OR '1'='1
        ' UNION SELECT ...
        '; DROP TABLE student; --
        """
        payloads = [
            "' OR '1'='1",
            "admin' --",
            "'; DROP TABLE student; --",
            "' UNION SELECT user_id, username, password_hash, '1', '1', '1', '1', '1', '1', '1', '1', '1', 1, 1, 1 FROM app_user --"
        ]

        for payload in payloads:
            # Query must execute cleanly without SQL syntax error or leaking data
            res = StudentRepository.get_all(search=payload)
            # The search parameter is treated literally, so it matches 0 records
            assert res["total"] == 0, f"Payload {payload} was not treated as literal search string!"

    def test_sql_injection_in_sort_column_rejected(self):
        """
        Sort column is validated against server-side allowlist.
        Malicious column names must fallback safely to default (roll_no).
        """
        malicious_cols = [
            "roll_no; DROP TABLE student; --",
            "s.status; SELECT * FROM app_user;",
            "(SELECT password_hash FROM app_user LIMIT 1)"
        ]

        for col in malicious_cols:
            res = StudentRepository.get_all(sort_col=col)
            # Must not crash and must return paginated list sorted by default
            assert res["total"] > 0
            assert len(res["items"]) > 0

    def test_parameterized_query_neutralizes_apostrophes(self):
        """Names containing apostrophes (e.g. O'Connor, D'Souza) must be safely handled without SQL errors."""
        res = StudentRepository.get_all(search="O'Connor")
        assert res["total"] == 0
