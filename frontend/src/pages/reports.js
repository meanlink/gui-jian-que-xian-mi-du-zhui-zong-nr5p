import {jobs,reports} from '../api/entities.js';
import {download} from '../api/client.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,date,notify} from '../utils/dom.js';
import {DeliveryStatus} from '../constants/enums.js';
import {submit} from '../hooks/forms.js';
const scopeText=s=>(s||[]).map(r=>r.from_km+'-'+r.to_km).join(', ');
const scopeLabel=s=>s&&s.length?s.map(r=>r.from_km+' ~ '+r.to_km+' km').join('，'):'未设置（外协简报为空）';
function parseScope(text){
 const t=(text||'').trim();
 if(!t)return [];
 return t.split(/[,，;；\n]+/).map(part=>{
  const m=part.trim().match(/^(\d+(?:\.\d+)?)\s*[-~—]\s*(\d+(?:\.\d+)?)$/);
  if(!m)throw new Error('公开范围格式须为「起点-终点」，多段用逗号分隔');
  const a=Number(m[1]),b=Number(m[2]);
  if(!(a<b))throw new Error('公开范围每段起点须小于终点');
  return {from_km:a,to_km:b};
 });
}
function deliveryRow(d,versions){
 const ready=d.status==='ready',stale=ready&&d.scope_version!==versions[d.report_id];
 const btn=(side,format,ok)=>'<button class="text-button" data-download="'+d.id+'" data-side="'+side+'" data-format="'+format+'"'+(ok?'':' disabled')+'>'+(side==='internal'?'内部':'外协')+' '+format.toUpperCase()+' ↓</button>';
 return '<div class="delivery"><div><strong>'+esc(d.filename)+'</strong><p>'+esc(d.destination)+' · '+date(d.created_at)+' · '+esc(DeliveryStatus[d.status]||d.status)+'</p><small>SHA256 '+esc((d.checksum||'').slice(0,24))+'… · 范围版本 v'+d.scope_version+'</small>'+(d.stop_reason?'<p class="warning">停发原因：'+esc(d.stop_reason)+'</p>':'')+'</div><div>'+btn('internal','csv',ready)+btn('internal','json',ready)+btn('external','csv',ready&&!stale)+btn('external','json',ready&&!stale)+'</div></div>';
}
function externalRow(d){
 return '<div class="delivery"><div><strong>'+esc(d.ext_filename)+'</strong><p>'+esc(d.destination)+' · '+date(d.created_at)+'</p><small>SHA256 '+esc((d.ext_checksum||'').slice(0,24))+'…</small></div><div><button class="text-button" data-download="'+d.id+'" data-side="external" data-format="csv">外协 CSV ↓</button><button class="text-button" data-download="'+d.id+'" data-side="external" data-format="json">外协 JSON ↓</button></div></div>';
}
export async function reportPage(){
 if(session.user.role==='external'){
  const deliveries=await reports.deliveries();
  return heading('05 / DISTRIBUTION','外协简报下载','仅含获准里程的外协简报，CSV 与 JSON 各一份。','<button class="button" id="refresh-reports">刷新收件箱 ↻</button>')+'<section class="panel inbox"><div class="section-title"><h2>可下载的外协简报</h2><span>'+deliveries.length+' 份</span></div>'+deliveries.map(externalRow).join('')+(!deliveries.length?'<p class="empty">暂无可下载的外协简报。新一轮分发完成后，请刷新查看。</p>':'')+'</section>';
 }
 const [list,deliveries,allJobs]=await Promise.all([reports.list(),reports.deliveries(),jobs.list()]);workspace.reports=list;
 const approved=allJobs.filter(j=>j.approved&&j.status==='completed'),admin=session.user.role==='admin';
 const versions=Object.fromEntries(list.map(r=>[r.id,r.scope_version]));
 return heading('05 / DISTRIBUTION','定时分发与归档','批准后每次分发生成内部与外协两份简报，文件齐备才开放下载；外协简报只含公开范围内的获准里程。','<button class="button" id="refresh-reports">刷新收件箱 ↻</button>')+'<div class="report-grid"><section class="panel"><div class="section-title"><h2>创建分发计划</h2></div><form id="report-form"><label>简报名称<input name="name" required minlength="2" value="日间业务复核简报"></label><label>已批准分析<select name="job_id" required>'+approved.map(j=>'<option value="'+j.id+'">'+esc(j.name)+'</option>').join('')+'</select></label><label>业务接收组<input name="destination" value="业务复核组 · 本地收件箱" required></label><div class="parameter-grid"><label>分发周期<select name="interval_seconds"><option value="86400">每日</option><option value="604800">每周</option><option value="60">每分钟（验收）</option></select></label><label>首次执行<select name="delay_seconds"><option value="0">立即</option><option value="60">1 分钟后</option><option value="3600">1 小时后</option></select></label></div><button type="submit" class="primary" '+(session.user.role!=='admin'||!approved.length?'disabled':'')+'>保存分发计划</button></form><p class="hint">由后台 worker 按到期时间生成文件。仅负责人可创建、暂停或调整公开范围；接收组为本地标签。</p></section><section><div class="section-title"><h2>运行中的计划</h2><span>'+list.filter(r=>r.enabled).length+' 条已启用</span></div><div class="schedule-list">'+list.map(r=>'<article><div><strong>'+esc(r.name)+'</strong><p>'+esc(r.destination)+'</p><small>下次 '+date(r.next_run)+' · 周期 '+r.interval_seconds+' 秒 · 范围版本 v'+r.scope_version+'</small><p class="hint">公开范围：'+esc(scopeLabel(r.public_scope))+'</p>'+(admin?'<form class="scope-form" data-report="'+r.id+'"><label>设置公开范围（公里，多段用逗号分隔）<input name="scope" value="'+esc(scopeText(r.public_scope))+'" placeholder="如 12.0-13.2, 47.6-49.0；留空则不公开"></label><button type="submit" class="button small">保存公开范围</button></form>':'')+'</div><button class="button small" data-toggle="'+r.id+'" '+(admin?'':'disabled')+'>'+(r.enabled?'暂停':'启用')+'</button></article>').join('')+'</div><section class="panel inbox"><div class="section-title"><h2>本地收件箱</h2><span>'+deliveries.length+' 份归档</span></div>'+deliveries.map(d=>deliveryRow(d,versions)).join('')+(!deliveries.length?'<p class="empty">计划执行后，文件会出现在此处。等待片刻后刷新。</p>':'')+'</section></section></div>';
}
export function bindReports(refresh){
 document.querySelector('#refresh-reports').onclick=refresh;
 const form=document.querySelector('#report-form');
 if(form)submit(form,async f=>{await reports.create({name:f.get('name'),job_id:Number(f.get('job_id')),destination:f.get('destination'),interval_seconds:Number(f.get('interval_seconds')),delay_seconds:Number(f.get('delay_seconds'))});notify('计划已保存，后台将按到期时间归档');await refresh();});
 document.querySelectorAll('.scope-form').forEach(f=>submit(f,async d=>{await reports.setScope(f.dataset.report,{public_scope:parseScope(d.get('scope'))});notify('公开范围已保存；收窄里程会停发旧外协简报');await refresh();}));
 document.querySelectorAll('[data-toggle]').forEach(b=>b.onclick=async()=>{try{await reports.toggle(b.dataset.toggle);await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>download(b.dataset.download,b.dataset.format,b.dataset.side).catch(e=>notify(e.message,true)));
}
