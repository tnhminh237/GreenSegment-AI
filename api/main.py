"""FastAPI localhost backend for the GreenSegment AI React website.

Run from the GreenSegment AI project root:
    python -m uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import advisor_service as advisor
from . import data_service as data
from . import market_service as market

app = FastAPI(title="GreenSegment AI API", version="1.0.0", description="K-Means EDGAR Cities 2024 + Gemini advisor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/api/market/parse")
async def market_parse(request: market.ParseRequest):
    return await _market_call(market.parse_request, request)


@app.post("/api/market/search")
def market_search(query: market.MarketQuery):
    return _safe(market.search, query)


@app.post("/api/market/export")
def market_export(request: market.ExportRequest):
    return _safe(market.export_csv, request)


@app.post("/api/market/report")
async def market_report(request: market.ReportRequest):
    try:
        result = await run_in_threadpool(market.generate_report, request)
        return JSONResponse(content=result, headers={"X-Request-ID": result["diagnostics"]["request_id"]})
    except market.ReportError as exc:
        # Existing API clients require a string detail; other fields are safe diagnostics.
        body = {"detail": f"{exc} Mã lỗi: {exc.category}. Mã yêu cầu: {exc.request_id}.",
                "error_code": exc.category, "request_id": exc.request_id, "validator_version": market.VALIDATOR_VERSION}
        if exc.provider_status is not None:
            body["provider_status"] = exc.provider_status
        if exc.validation is not None:
            body["validation"] = exc.validation
            path = exc.validation.get("field_path")
            if path:
                body["detail"] += f" Trường: {path}. Lý do: {exc.validation.get('rule', 'invalid_content')}."
                if "observed" in exc.validation and "expected" in exc.validation:
                    body["detail"] += f" Nhận: {exc.validation['observed']}; Python: {exc.validation['expected']}."
                elif "observed" in exc.validation:
                    body["detail"] += f" Số chưa gắn được với dữ liệu Python: {exc.validation['observed']}."
        return JSONResponse(status_code=exc.status, content=body, headers={"X-Request-ID": exc.request_id})


async def _market_call(callback, request):
    try:
        return await run_in_threadpool(callback, request)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = "Chưa đặt GEMINI_API_KEY trên backend." if "Chưa đặt GEMINI_API_KEY" in str(exc) else "Không thể xử lý bằng Gemini. Kiểm tra kết nối, quota, nội dung phản hồi hoặc thử lại sau."
        raise HTTPException(status_code=503, detail=message) from exc


class AdvisorRequest(BaseModel):
    mode: Literal["city", "cluster"]
    city_id: str | None = None
    cluster_id: int | None = Field(default=None, ge=0, le=2)
    model: str | None = Field(default=None, min_length=1, max_length=100)


def _safe(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _payload(request: AdvisorRequest) -> dict:
    if request.mode == "city" and not request.city_id:
        raise HTTPException(status_code=422, detail="Hãy chọn một đô thị để phân tích.")
    if request.mode == "cluster" and request.cluster_id is None:
        raise HTTPException(status_code=422, detail="Hãy chọn một cụm để phân tích.")
    return request.model_dump(exclude_none=True)


@app.get("/api/health")
def health():
    return data.status()


@app.get("/api/meta")
def metadata():
    return {"year": 2024, "method": "K-Means", "k": 3,
            "sector_labels": data.SECTOR_LABELS, "cluster_colors": data.CLUSTER_COLORS,
            "emission_units_verified": False}


@app.get("/api/overview")
def overview(country: str | None = None, cluster_id: int | None = Query(default=None, ge=0, le=2),
             sector: Literal["agriculture", "energy", "industry", "international", "residential", "transport", "waste"] | None = None):
    return _safe(data.overview, country=country, cluster_id=cluster_id, sector=sector)


@app.get("/api/clusters")
def clusters():
    return _safe(data.all_clusters)


@app.get("/api/cluster-explorer")
def cluster_explorer():
    return _safe(data.cluster_explorer)


@app.get("/api/cluster-explorer/{cluster_id}/preview")
def cluster_interpretation_preview(cluster_id: int = Path(ge=0, le=2)):
    return _safe(advisor.cluster_preview, cluster_id)


@app.post("/api/cluster-explorer/{cluster_id}/interpret")
async def cluster_interpretation(cluster_id: int = Path(ge=0, le=2)):
    try:
        result = await run_in_threadpool(advisor.interpret_cluster, cluster_id)
        return JSONResponse(content=result, headers={"X-Request-ID": result["diagnostics"]["request_id"]})
    except advisor.ClusterReportError as exc:
        return JSONResponse(status_code=exc.status, content={
            "detail": f"{exc} Mã lỗi: {exc.category}. Mã yêu cầu: {exc.request_id}.",
            "error_code": exc.category, "request_id": exc.request_id, **exc.details,
        }, headers={"X-Request-ID": exc.request_id})
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Do not expose provider response bodies, request headers or credentials.
        message = "Chưa đặt GEMINI_API_KEY trên backend." if "Chưa đặt GEMINI_API_KEY" in str(exc) else "Không thể tạo báo cáo Gemini. Kiểm tra kết nối, quota hoặc thử lại sau."
        raise HTTPException(status_code=503, detail=message) from exc


@app.get("/api/countries")
def countries():
    return _safe(data.all_countries)


@app.get("/api/cities")
def cities(search: str | None = Query(default=None, max_length=150), country: str | None = None,
           cluster_id: int | None = Query(default=None, ge=0, le=2),
           sector: Literal["agriculture", "energy", "industry", "international", "residential", "transport", "waste"] | None = None,
           page: int = Query(default=1, ge=1), page_size: int = Query(default=12, ge=1, le=50)):
    selected = _safe(data.filter_cities, search=search, country=country, cluster_id=cluster_id, sector=sector)
    start = (page - 1) * page_size
    return {"total": len(selected), "page": page, "page_size": page_size,
            "items": [data.compact_city(city) for city in selected[start:start + page_size]]}


@app.get("/api/cities/map")
def city_map(country: str | None = None, cluster_id: int | None = Query(default=None, ge=0, le=2),
             sector: Literal["agriculture", "energy", "industry", "international", "residential", "transport", "waste"] | None = None,
             limit: int = Query(default=5000, ge=100, le=12000)):
    return _safe(data.map_points, country, cluster_id, sector, limit)


@app.get("/api/cities/{city_id}")
def city_details(city_id: str):
    result = _safe(data.city_details, city_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đô thị.")
    return result


@app.post("/api/cities/{city_id}/interpret")
async def city_interpretation(city_id: str):
    try:
        result = await run_in_threadpool(advisor.interpret_city, city_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy đô thị.")
        return result
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = "Chưa đặt GEMINI_API_KEY trên backend." if "Chưa đặt GEMINI_API_KEY" in str(exc) else "Không thể tạo báo cáo đô thị bằng Gemini. Kiểm tra kết nối, quota hoặc thử lại sau."
        raise HTTPException(status_code=503, detail=message) from exc


@app.get("/api/catalog")
def catalog():
    return _safe(data.solutions_catalog)


@app.post("/api/advisor/preview")
async def advisor_preview(request: AdvisorRequest):
    try:
        return await run_in_threadpool(advisor.preview, _payload(request))
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/advisor")
async def advisor_analyze(request: AdvisorRequest):
    try:
        return await run_in_threadpool(advisor.analyze, _payload(request))
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Preserve actionable details but never echo the API key.
        message = str(exc)
        status = 503 if "HTTP 503" in message or "HTTP 502" in message else 502
        raise HTTPException(status_code=status, detail=message[:1200]) from exc
