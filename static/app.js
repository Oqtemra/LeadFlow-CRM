const stages = [
 {id:'new',name:'Новая',color:'#9d8df0'}, {id:'contact',name:'На связи',color:'#6d9bef'},
 {id:'proposal',name:'Предложение',color:'#f0b96b'}, {id:'negotiation',name:'Переговоры',color:'#ee93aa'},
 {id:'won',name:'Выиграно',color:'#4fc69b'}
];
let leads = [], summary = {}, currentId = null, view = 'overview';
const $ = id => document.getElementById(id);
const money = n => new Intl.NumberFormat('ru-RU').format(n||0)+' ₸';
const escapeHtml = s => String(s??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short = s => String(s||'').trim().slice(0,1).toUpperCase();
function notify(message){$('toast').textContent=message;$('toast').classList.remove('hidden');clearTimeout(window._toastTimer);window._toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),3000)}
async function api(url,options={}){const res=await fetch(url,options);if(!res.ok){let data={};try{data=await res.json()}catch{};throw new Error(typeof data.detail==='string'?data.detail:`Ошибка сервера (${res.status})`)}return res.status===204?null:res.json()}
async function refresh(){try{[leads,summary]=await Promise.all([api('/api/leads'),api('/api/summary')]);render()}catch(e){notify(e.message)}}
function render(){
 $('kpiPipeline').textContent=money(summary.pipeline_amount);$('kpiActive').textContent=summary.active;
 $('kpiConversion').textContent=(summary.conversion_pct||0).toLocaleString('ru-RU')+'%';$('kpiWon').textContent=money(summary.won_amount);
 $('navCount').textContent=summary.total;$('totalCount').textContent=summary.total;renderKanban();renderBars();renderActivity();
}
function renderKanban(){const q=$('searchInput').value.toLowerCase().trim();const matched=leads.filter(x=>[x.company,x.contact,x.service].some(v=>v.toLowerCase().includes(q)));
 $('emptyState').classList.toggle('hidden',matched.length>0);
 $('kanban').innerHTML=stages.map(stage=>{const entries=matched.filter(x=>x.stage===stage.id);const sum=entries.reduce((s,x)=>s+x.amount,0);
 return `<div class="kanban-col" data-stage="${stage.id}"><div class="col-head"><span class="stage-dot" style="background:${stage.color}"></span><strong>${stage.name}</strong><span class="col-count">${entries.length}</span></div><div class="col-total">${money(sum)}</div>${entries.map(x=>`<article class="lead-card" draggable="true" data-id="${x.id}" role="button" tabindex="0" aria-label="Редактировать: ${escapeHtml(x.company)}"><div class="lead-top"><span class="lead-company">${escapeHtml(x.company)}</span><span class="lead-more">···</span></div><div class="lead-service">${escapeHtml(x.service)}</div><div class="lead-bottom"><strong class="lead-amount">${money(x.amount)}</strong><span class="contact-avatar" title="${escapeHtml(x.contact)}">${escapeHtml(short(x.contact))}</span></div></article>`).join('')||'<div class="empty-col">Нет сделок</div>'}</div>`}).join('');
 document.querySelectorAll('.lead-card').forEach(el=>{
  el.addEventListener('click',()=>openModal(Number(el.dataset.id)));el.addEventListener('keydown',e=>{if(e.key==='Enter')openModal(Number(el.dataset.id))});
  el.addEventListener('dragstart',e=>{e.dataTransfer.setData('text/plain',el.dataset.id);e.dataTransfer.effectAllowed='move';el.classList.add('dragging')});
  el.addEventListener('dragend',()=>el.classList.remove('dragging'));
 });
 document.querySelectorAll('.kanban-col').forEach(el=>{
  el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('dropzone')});
  el.addEventListener('dragleave',()=>el.classList.remove('dropzone'));
  el.addEventListener('drop',async e=>{e.preventDefault();el.classList.remove('dropzone');const id=Number(e.dataTransfer.getData('text/plain'));const stage=el.dataset.stage;if(!id||!stage)return;try{await api('/api/leads/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage})});await refresh();notify('Этап сделки обновлён')}catch(error){notify(error.message)}})
 });
}
function renderBars(){const max=Math.max(1,...Object.values(summary.counts||{}));$('stageBars').innerHTML=stages.map(s=>{const n=(summary.counts||{})[s.id]||0;return `<div class="stage-row"><span>${s.name}</span><div class="bar-track"><div class="bar-fill" style="width:${100*n/max}%;background:${s.color}"></div></div><strong>${n}</strong></div>`}).join('')}
function renderActivity(){const a=summary.activities||[];$('activityList').innerHTML=a.length?a.map(item=>`<div class="activity-item"><span class="activity-icon">↗</span><div class="activity-text">${escapeHtml(item.description)}</div><time class="activity-time">${new Date(item.created_at).toLocaleDateString('ru-RU',{day:'numeric',month:'short'})}</time></div>`).join(''):'<div class="empty-col">История пока пуста</div>'}
function openModal(id=null){currentId=id;const item=leads.find(x=>x.id===id);$('leadForm').reset();$('formError').classList.add('hidden');$('deleteLead').classList.toggle('hidden',!item);$('modalTitle').textContent=item?'Редактировать сделку':'Новая сделка';if(item){['company','contact','service','amount','stage','note'].forEach(key=>$(key).value=item[key]??'')} $('modal').classList.remove('hidden');$('company').focus()}
function closeModal(){$('modal').classList.add('hidden');currentId=null}
function setView(next){view=next;document.body.classList.toggle('view-deals',view==='deals');document.body.classList.toggle('view-analytics',view==='analytics');document.querySelectorAll('.nav-link').forEach(x=>x.classList.toggle('active',x.dataset.view===view));const label={overview:'Обзор',deals:'Сделки',analytics:'Аналитика'}[view];$('crumb').textContent=label;$('pageTitle').innerHTML=view==='analytics'?'Цифры, которые<br><em>двигают бизнес.</em>':view==='deals'?'Каждая сделка.<br><em>Под контролем.</em>':'Управляйте сделками.<br><em>Растите быстрее.</em>'; $('pageSubtitle').textContent=view==='analytics'?'Изучайте воронку и историю взаимодействий.':'Все обращения и клиенты на одной доске.'}
$('leadForm').addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget).entries());data.amount=Number(data.amount);$('saveLead').disabled=true;try{const editing=Boolean(currentId);await api(currentId?'/api/leads/'+currentId:'/api/leads',{method:currentId?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});closeModal();await refresh();notify(editing?'Сделка обновлена':'Сделка создана')}catch(err){$('formError').textContent=err.message;$('formError').classList.remove('hidden')}finally{$('saveLead').disabled=false}});
$('deleteLead').addEventListener('click',async()=>{if(!currentId||!confirm('Удалить сделку без возможности восстановления?'))return;try{await api('/api/leads/'+currentId,{method:'DELETE'});closeModal();await refresh();notify('Сделка удалена')}catch(e){notify(e.message)}});
['addLead','sidebarCreate'].forEach(id=>$(id).addEventListener('click',()=>openModal()));
['closeModal','cancelModal'].forEach(id=>$(id).addEventListener('click',closeModal));
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
$('searchInput').addEventListener('input',renderKanban);
$('exportBtn').addEventListener('click',()=>window.location.assign('/api/export.csv'));
document.querySelectorAll('.nav-link').forEach(x=>x.addEventListener('click',()=>setView(x.dataset.view)));
$('dateLabel').textContent=new Date().toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'});
refresh();
