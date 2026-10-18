const $ = id => document.getElementById(id);
let revision = 0, jobs = null, filename = '', lookupRevision = 0;
function status(id, message, error = false) { $(id).textContent = message; $(id).classList.toggle('error', error); }
async function post(path, payload) {
  const response = await fetch(`/api/v1/${path}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  let data;
  try { data = await response.json(); } catch { throw new Error('서버 응답을 읽지 못했습니다. 서버 상태를 확인해 주세요.'); }
  if (!response.ok) throw new Error([data.error?.message || '요청 실패', ...(data.error?.details || [])].join('\n'));
  return data;
}
function showSequence(info) {
  $('sequence-title').textContent = `${info.query} → ${info.accession} · ${info.length} aa`;
  $('sequence-text').textContent = info.sequence; $('sequence-panel').hidden = false;
  $('sequence-panel').scrollIntoView({block:'nearest'});
}
function table(id, headers, rows) {
  const t = document.createElement('table'), head = t.createTHead().insertRow();
  headers.forEach(text => { const th = document.createElement('th'); th.scope='col'; th.textContent=text; if (['길이', '복제수', '토큰', '잡 토큰'].includes(text)) th.className='numeric'; head.append(th); });
  const body = t.createTBody();
  rows.forEach(row => { const tr=body.insertRow(); row.forEach(value => {
    const td=tr.insertCell();
    if (typeof value === 'number') td.className='numeric';
    if (value instanceof Node) td.append(value);
    else if (['포함','제외','정상','병합됨','형식 오류','조회 오류','찾을 수 없음','폐기됨'].includes(value)) {
      const state=document.createElement('span');
      state.className=`state-text ${['포함','정상','병합됨'].includes(value)?'state-success':'state-error'}`;
      state.textContent=value; td.append(state);
    } else td.textContent=String(value ?? '—');
  }); });
  $(id).replaceChildren(t);
}
function sequenceButton(info) {
  const button = document.createElement('button'); button.type='button'; button.textContent='서열 보기'; button.disabled=!info.sequence;
  button.addEventListener('click',()=>showSequence(info)); return button;
}
function invalidate() {
  revision++; jobs=null; $('download').disabled=true; $('sequence-panel').hidden=true;
  status('jobs-status', '입력이 변경되었습니다. 미리보기를 다시 만들어 주세요.');
  $('jobs-results').hidden=true; $('jobs-empty').hidden=false;
}
$('jobs-form').addEventListener('input',invalidate);
for (const mode of ['jobs','lookup']) $('tab-'+mode).addEventListener('click',()=>{
  for (const name of ['jobs','lookup']) { $(name+'-panel').hidden=name!==mode; $('tab-'+name).setAttribute('aria-pressed',String(name===mode)); }
  $('sequence-panel').hidden=true;
});
$('close-sequence').addEventListener('click',()=>{$('sequence-panel').hidden=true;});
$('jobs-form').addEventListener('submit',async event=>{
  event.preventDefault(); const current=++revision; jobs=null; $('download').disabled=true; $('generate').disabled=true;
  $('jobs-results').hidden=true; $('jobs-empty').hidden=true; $('sequence-panel').hidden=true;
  status('jobs-status','UniProt 조회 및 입력 검증 중…');
  try {
    const data=await post('jobs/preview',{target_text:$('target').value,candidate_text:$('candidates').value,target_label:$('label').value,token_limit:Number($('limit').value),use_cache:$('jobs-cache').checked});
    if(current!==revision) return;
    jobs=data.jobs; filename=`${data.target_label}_jobs.json`; $('jobs-results').hidden=false; $('metrics').replaceChildren();
    for (const [label,value] of [['전체 후보',data.summary.total],['잡 생성',data.summary.included],['제외',data.summary.excluded]]) {
      const box=document.createElement('div'); box.className='metric'; box.textContent=label; const n=document.createElement('strong');n.textContent=value;box.append(n);$('metrics').append(box);
    }
    $('warnings').textContent=data.warnings.join('\n');
    table('targets-table',['입력 ID → 현재 ID','단백질 / 유전자 / 종','길이','복제수','토큰','전체 서열'],data.targets.map(t=>[`${t.query} → ${t.accession}`,`${t.name}\n${t.gene || '—'} / ${t.organism}`,t.length,t.count,t.tokens,sequenceButton(t)]));
    table('plans-table',['결과','입력 ID → 현재 ID','단백질 / 종','잡 토큰','잡 이름','사유','전체 서열'],data.plans.map(p=>[p.included?'포함':'제외',`${p.candidate.query} → ${p.candidate.accession || '—'}`,`${p.candidate.name}\n${p.candidate.organism}`,p.tokens,p.name,p.note || '—',sequenceButton(p.candidate)]));
    $('json-preview').textContent=data.preview?JSON.stringify(data.preview,null,2):'생성 가능한 잡이 없습니다.';
    $('download').disabled=!jobs.length;
    status('jobs-status',`${data.target_label} · 타겟 ${data.target_tokens} 토큰 · ${jobs.length}개 잡 생성${jobs.length?'':' — 제외 사유를 확인해 주세요.'}`);
  } catch(error) { if(current===revision) status('jobs-status',error.message,true); }
  finally { $('generate').disabled=false; }
});
$('download').addEventListener('click',()=>{
  if(!jobs?.length) return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(jobs,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('lookup-form').addEventListener('input',()=>{lookupRevision++;$('lookup-table').replaceChildren();$('sequence-panel').hidden=true;status('lookup-status','입력이 변경되었습니다. 다시 조회해 주세요.');});
$('lookup-form').addEventListener('submit',async event=>{
  event.preventDefault();const current=++lookupRevision;$('lookup-submit').disabled=true;$('lookup-table').replaceChildren();$('sequence-panel').hidden=true;
  status('lookup-status','UniProt 조회 중…');
  try {
    const data=await post('proteins/lookup',{ids:$('lookup-ids').value,use_cache:$('lookup-cache').checked});
    if(current!==lookupRevision)return;
    table('lookup-table',['입력 ID','상태','현재 ID','유전자','단백질','종','길이','메모','전체 서열'],data.results.map(r=>[r.query,r.status_label,r.accession,r.gene,r.name,r.organism,r.length,r.message,sequenceButton(r)]));
    status('lookup-status',`${data.results.length}개 조회 완료 · 정상/병합 ${data.results.filter(r=>['ok','merged'].includes(r.status)).length}개`);
  } catch(error) {if(current===lookupRevision)status('lookup-status',error.message,true);}
  finally {$('lookup-submit').disabled=false;}
});
