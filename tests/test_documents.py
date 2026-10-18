from pathlib import Path

from fastapi.testclient import TestClient

from protinteract import documents
from protinteract.main import app


def test_all_project_documents_available():
    client = TestClient(app)
    items = client.get('/api/v1/documents').json()['documents']
    assert len(items) == 3
    keys = {d['id'] for d in items}
    assert {'CHANGES_FROM_ORIGINAL.md', 'README.md', 'docs/USAGE.md'} == keys
    for item in items:
        response = client.get('/api/v1/documents/content', params={'id':item['id']})
        assert response.status_code == 200 and response.json()['html']
        raw = client.get('/api/v1/documents/download', params={'id':item['id']})
        assert raw.status_code == 200
        assert raw.content == (documents.ROOT / item['id']).read_bytes()


def test_unknown_and_traversal_rejected():
    client = TestClient(app)
    for key in ['../README.md', '/etc/passwd', '.git/config', 'protinteract/main.py', 'not-found.md']:
        for endpoint in ['content', 'download']:
            assert client.get(f'/api/v1/documents/{endpoint}', params={'id':key}).status_code == 404


def test_safe_markdown_tables_and_relative_links():
    text = '<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n[guide](README.md)\n\n| a | b |\n|---|---|\n| 1 | 2 |'
    rendered = documents.render_document(text, documents.ROOT / 'CHANGES_FROM_ORIGINAL.md')
    assert '<script>' not in rendered
    assert 'href="javascript:' not in rendered
    assert '/docs?doc=README.md' in rendered
    assert '<table>' in rendered
