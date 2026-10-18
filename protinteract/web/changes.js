async function loadChanges() {
  const root = document.getElementById('changes-content');
  try {
    const response = await fetch('/api/v1/documents/content?id=CHANGES_FROM_ORIGINAL.md');
    if (!response.ok) throw new Error();
    const data = await response.json();
    // Server renders project Markdown with raw HTML disabled and safe link rules.
    root.innerHTML = data.html;
    root.querySelector('h1')?.remove();
  } catch { root.textContent = '변경사항을 불러오지 못했습니다. Docs 페이지에서 확인해 주세요.'; }
}
loadChanges();
