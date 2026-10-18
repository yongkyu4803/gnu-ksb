const $ = id => document.getElementById(id);
let documents = [], current = '', requestId = 0;
function renderList() {
  const query = $('doc-search').value.toLocaleLowerCase();
  const filtered = documents.filter(d => `${d.title} ${d.id}`.toLocaleLowerCase().includes(query));
  $('doc-count').textContent = `${filtered.length} / ${documents.length}개 문서`;
  $('document-list').replaceChildren();
  for (const category of ['프로젝트 안내', '사용 안내']) {
    const items = filtered.filter(d => d.category === category);
    if (!items.length) continue;
    const heading = document.createElement('h2'); heading.textContent = category;
    $('document-list').append(heading);
    for (const item of items) {
      const a = document.createElement('a'); a.href = `/docs?doc=${encodeURIComponent(item.id)}`;
      a.textContent = item.title; a.setAttribute('aria-current', item.id === current ? 'page' : 'false');
      const small = document.createElement('small'); small.textContent = item.id; a.append(small);
      a.addEventListener('click', event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault(); history.pushState(null, '', a.href); loadDocument(item.id);
      });
      $('document-list').append(a);
    }
  }
}
async function loadDocument(id) {
  const revision = ++requestId; current = id; renderList();
  $('document-content').replaceChildren(); $('doc-download').hidden = true;
  $('doc-status').textContent = '문서를 불러오는 중…'; $('doc-path').textContent = id;
  try {
    const response = await fetch(`/api/v1/documents/content?id=${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error('문서를 찾거나 읽을 수 없습니다. 목록에서 다시 선택해 주세요.');
    const data = await response.json(); if (revision !== requestId) return;
    $('document-content').innerHTML = data.html;
    $('document-content').querySelectorAll('table').forEach(table => { const wrap = document.createElement('div'); wrap.className = 'table-wrap'; table.replaceWith(wrap); wrap.append(table); });
    $('doc-status').textContent = '';
    $('doc-download').href = `/api/v1/documents/download?id=${encodeURIComponent(id)}`;
    $('doc-download').hidden = false;
    document.title = `${documents.find(d => d.id === id)?.title || id} · ProtInteract Docs`;
  } catch (error) { if (revision === requestId) $('doc-status').textContent = error.message; }
}
function selection() { return new URLSearchParams(location.search).get('doc') || 'CHANGES_FROM_ORIGINAL.md'; }
$('doc-search').addEventListener('input', renderList);
window.addEventListener('popstate', () => loadDocument(selection()));
try {
  const response = await fetch('/api/v1/documents');
  if (!response.ok) throw new Error('문서 목록을 불러올 수 없습니다.');
  documents = (await response.json()).documents; await loadDocument(selection());
} catch (error) { $('doc-status').textContent = error.message; }
