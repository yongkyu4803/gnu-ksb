"""Read only project Markdown files; never expose arbitrary filesystem paths."""
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent / "manual"
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
renderer = MarkdownIt("commonmark", {"html": False}).enable("table")


def available():
    paths = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]
    return {p.relative_to(ROOT).as_posix(): p for p in paths if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(ROOT.resolve())}


def file_for(key):
    path = available().get(key)
    if path is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return path


def render_document(text, path):
    tokens = renderer.parse(text)
    known = available()
    for token in tokens:
        for child in token.children or []:
            if child.type != "link_open":
                continue
            href = child.attrGet("href") or ""
            url = urlsplit(href)
            if url.scheme or url.netloc or not url.path:
                continue
            destination = (path.parent / unquote(url.path)).resolve()
            if destination.is_relative_to(ROOT.resolve()):
                key = destination.relative_to(ROOT.resolve()).as_posix()
                if key in known:
                    fragment = f"#{url.fragment}" if url.fragment else ""
                    child.attrSet("href", f"/docs?doc={quote(key, safe='')}{fragment}")
    return renderer.renderer.render(tokens, renderer.options, {})


@router.get("")
def list_documents():
    result = []
    for key, path in sorted(available().items()):
        text = path.read_text(encoding="utf-8")
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        category = "사용 안내" if key.startswith("docs/") else "프로젝트 안내"
        result.append({"id": key, "title": title, "category": category})
    return {"documents": result}


@router.get("/content")
def document_content(id: str):
    path = file_for(id)
    text = path.read_text(encoding="utf-8")
    return {"id": id, "html": render_document(text, path)}


@router.get("/download")
def download_document(id: str):
    path = file_for(id)
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)
