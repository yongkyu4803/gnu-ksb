"""Local FastAPI API and web UI."""
from dataclasses import asdict
from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from protinteract import __version__
from protinteract.documents import router as documents_router
from protinteract.core.uniprot import fetch_many, parse_id_list, validate_info
from protinteract.core.af_json import (
    TOKEN_LIMIT, TargetChain, USABLE, build_jobs, default_target_label,
    merge_targets, parse_target_lines, plan_jobs, safe_name,
    shorten_for_preview, target_tokens,
)

WEB = Path(__file__).parent / "web"
app = FastAPI(title="ProtInteract", version=__version__, docs_url="/api/docs", redoc_url="/api/redoc")
app.include_router(documents_router)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use_cache: bool = True


class LookupInput(Input):
    ids: str = Field(min_length=1, max_length=10000)


class PreviewInput(Input):
    target_text: str = Field(min_length=1, max_length=10000)
    candidate_text: str = Field(min_length=1, max_length=10000)
    target_label: str = Field(default="", max_length=100)
    token_limit: StrictInt = Field(default=TOKEN_LIMIT, ge=1, le=TOKEN_LIMIT)


class DomainError(Exception):
    def __init__(self, message, details=None):
        self.message, self.details = message, details or []


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    return JSONResponse(status_code=422, content={"error": {"message": exc.message, "details": exc.details}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"message": "입력 형식과 범위를 확인해 주세요", "details": [f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors()]}})


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("처리 실패")
    return JSONResponse(status_code=500, content={"error": {"message": "처리 중 오류가 발생했습니다. 다시 시도해 주세요", "details": []}})


def ids_from(text):
    ids = parse_id_list(text)
    if not ids or len(ids) > 100:
        raise DomainError("한 번에 1~100개의 고유 ID를 입력해 주세요")
    return ids


def record(info):
    return {**asdict(info), "status_label": info.status_label}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/api/v1/proteins/lookup")
def lookup(body: LookupInput):
    return {"results": [record(info) for info in fetch_many(ids_from(body.ids), body.use_cache)]}


@app.post("/api/v1/jobs/preview")
def preview(body: PreviewInput):
    entries, errors = parse_target_lines(body.target_text)
    if errors or not entries:
        raise DomainError("타겟 입력을 확인해 주세요", errors or ["타겟을 한 줄 이상 입력해 주세요"])
    if len(entries) > 100:
        raise DomainError("타겟은 최대 100종입니다")
    candidates = ids_from(body.candidate_text)
    infos = fetch_many([uid for uid, _ in entries], body.use_cache)
    bad = [info for info in infos if info.status not in USABLE or validate_info(info)]
    if bad:
        raise DomainError("타겟 조회에 문제가 있어 생성하지 않았습니다", [f"{b.query}: {b.message or validate_info(b)}" for b in bad])
    try:
        target, warnings = merge_targets([TargetChain(info, count) for info, (_, count) in zip(infos, entries)])
        warnings.extend(f"{info.query}: {info.message}" for info in infos if info.message)
        if len(entries) < len([s for s in body.target_text.splitlines() if s.strip()]):
            warnings.append("동일 입력 ID의 타겟 복제수를 합산했습니다. 최종 구성표를 확인해 주세요")
        label = safe_name(body.target_label) or default_target_label(target)
        if body.target_label.strip() and label != body.target_label.strip():
            warnings.append(f"타겟 이름을 파일명에 맞게 정리했습니다: {label}")
        plans = plan_jobs(target, fetch_many(candidates, body.use_cache), label, body.token_limit)
        jobs = build_jobs(plans, target)
    except ValueError as exc:
        raise DomainError(str(exc)) from exc
    return {
        "target_label": label,
        "targets": [{**record(c.info), "count": c.count, "tokens": c.info.length * c.count} for c in target],
        "target_tokens": target_tokens(target),
        "plans": [{"candidate": record(p.candidate), "name": p.name, "tokens": p.tokens, "included": p.included, "note": p.note} for p in plans],
        "summary": {"total": len(plans), "included": len(jobs), "excluded": len(plans) - len(jobs)},
        "jobs": jobs, "preview": shorten_for_preview(jobs[0]) if jobs else None,
        "warnings": warnings,
    }


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/docs", include_in_schema=False)
def documents_page():
    return FileResponse(WEB / "docs.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
