from __future__ import annotations

import sys

from scripts import cleanup_tenantless_customer_data as cleanup_script


class _FakeResult:
    def __init__(self, value=0):
        self._value = value

    def scalar(self):
        return self._value

    def fetchall(self):
        return []


class _FakeSession:
    def __init__(self):
        self.statements: list[str] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        if sql.startswith("SELECT count(*)"):
            return _FakeResult(0)
        return _FakeResult([])

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _SessionLocalFactory:
    def __init__(self, session: _FakeSession):
        self.session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_cleanup_script_retains_payments(monkeypatch, capsys):
    session = _FakeSession()
    monkeypatch.setattr(cleanup_script, "SessionLocal", _SessionLocalFactory(session))
    monkeypatch.setattr(sys, "argv", ["cleanup_tenantless_customer_data.py", "--execute"])

    exit_code = cleanup_script.main()

    assert exit_code == 0
    assert session.committed is True
    assert session.rolled_back is False
    assert not any("DELETE FROM payments" in statement for statement in session.statements)
    assert any("DELETE FROM reports" in statement for statement in session.statements)
    assert any("DELETE FROM assessments" in statement for statement in session.statements)
    assert any("DELETE FROM access_windows" in statement for statement in session.statements)

    output = capsys.readouterr().out
    assert "- payments: retained" in output