"""FastAPI 查询服务测试：覆盖三类输入（正常 / 不存在 / 非法），不依赖真实数据库。"""
from fastapi.testclient import TestClient

from api.main import app, repo

client = TestClient(app)

FIXTURE = {
    "score_rank": 1, "vendor": "SCMS from RDC", "abc": "A",
    "line_cnt": 6681, "asn_cnt": 900, "otd": 86.7, "avg_late": 8.2,
    "late_cnt": 300, "total_value": 6.8e7, "score": 86.74,
}


class TestSupplierScore:
    def test_normal(self, monkeypatch):
        monkeypatch.setattr(repo, "get_score", lambda name: FIXTURE)
        r = client.get("/api/v1/suppliers/SCMS%20from%20RDC/score")
        assert r.status_code == 200
        body = r.json()
        assert body["vendor"] == "SCMS from RDC"
        assert body["score"] == 86.74
        assert "abc" in body

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(repo, "get_score", lambda name: None)
        r = client.get("/api/v1/suppliers/NotExistVendor/score")
        assert r.status_code == 404

    def test_invalid_blank_name(self):
        r = client.get("/api/v1/suppliers/%20/score")
        assert r.status_code == 422

    def test_invalid_overlong_name(self):
        r = client.get("/api/v1/suppliers/" + "A" * 200 + "/score")
        assert r.status_code == 422


class TestSupplierList:
    def test_list_ok(self, monkeypatch):
        monkeypatch.setattr(repo, "list_suppliers", lambda **kw: [FIXTURE])
        r = client.get("/api/v1/suppliers?limit=5")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_invalid_limit(self):
        r = client.get("/api/v1/suppliers?limit=-1")
        assert r.status_code == 422

    def test_invalid_abc(self):
        r = client.get("/api/v1/suppliers?abc=D")
        assert r.status_code == 422
