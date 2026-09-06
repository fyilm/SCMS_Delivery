"""SCMS 供应商绩效查询服务（FastAPI）。

运行：uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
"""
from typing import Optional

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel

from .repo import SupplierRepo

app = FastAPI(title="SCMS 供应商绩效查询服务", version="1.0.0")
repo = SupplierRepo()


class SupplierScore(BaseModel):
    score_rank: int
    vendor: str
    abc: Optional[str] = None
    line_cnt: Optional[int] = None
    asn_cnt: Optional[int] = None
    otd: Optional[float] = None
    avg_late: Optional[float] = None
    late_cnt: Optional[int] = None
    total_value: Optional[float] = None
    score: Optional[float] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/suppliers", response_model=list[SupplierScore])
def list_suppliers(
    limit: int = Query(20, ge=1, le=100),
    otd_lt: Optional[float] = Query(None, ge=0, le=100),
    abc: Optional[str] = Query(None, pattern="^[ABC]$"),
):
    return repo.list_suppliers(limit=limit, otd_lt=otd_lt, abc=abc)


@app.get("/api/v1/suppliers/{name}/score", response_model=SupplierScore)
def supplier_score(name: str = Path(..., min_length=1, max_length=128)):
    if not name.strip():
        raise HTTPException(status_code=422, detail="供应商名不能为空")
    row = repo.get_score(name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"未找到供应商：{name}")
    return row
