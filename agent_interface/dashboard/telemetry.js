(()=>{
 document.addEventListener('DOMContentLoaded',()=>{
  const bar=document.createElement('section');bar.className='telemetry-bar';bar.setAttribute('aria-label','Live GPU telemetry');
  bar.innerHTML='<div class="telemetry-heading"><span class="eyebrow">GPU telemetry</span><span class="telemetry-state" role="status">Connecting…</span><a href="/gpu">Details ↗</a></div><div class="telemetry-dials"></div>';
  const definitions=[['GPU utilization','GPU busy time'],['Memory controller','Memory read/write activity'],['GPU memory allocated','Compute allocations / shared RAM'],['GPU temperature','Display scale: 0–100°C'],['GPU power draw','Display limit: 140 W']];
  const dials=definitions.map(([label,note])=>{
   const d=document.createElement('div');d.className='telemetry-item';
   d.innerHTML='<div class="telemetry-ring" role="img"><svg viewBox="0 0 100 100" aria-hidden="true"><circle class="dial-track" cx="50" cy="50" r="43"/><circle class="dial-fill" cx="50" cy="50" r="43" pathLength="100"/></svg><strong>—</strong></div><div class="dial-caption"><b></b><small></small></div>';
   d.querySelector('b').textContent=label;d.querySelector('small').textContent=note;bar.querySelector('.telemetry-dials').append(d);return d;
  });
  document.body.append(bar);document.body.classList.add('has-telemetry');
  const details=document.createElement('details');details.className='telemetry-processes';
  details.innerHTML='<summary>GPU processes · loading…</summary><div class="telemetry-process-scroll"><table><thead><tr><th>Process</th><th>PID</th><th>Type</th><th>GPU memory</th></tr></thead><tbody></tbody></table></div><small>Reported process allocations include compute and graphics. They do not represent all driver or shared-system memory.</small>';
  bar.append(details);
  new ResizeObserver(()=>{document.body.style.paddingBottom=(Math.ceil(bar.getBoundingClientRect().height)+20)+'px'}).observe(bar);
  function renderProcesses(processes){
   const tbody=details.querySelector('tbody');tbody.replaceChildren();
   details.querySelector('summary').textContent=Array.isArray(processes)?'GPU processes · '+processes.length+' · show details':'GPU processes · unavailable';
   if(!Array.isArray(processes)||!processes.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.textContent=Array.isArray(processes)?'No active GPU processes':'Process telemetry unavailable';tr.append(td);tbody.append(tr);return}
   for(const p of processes){const tr=document.createElement('tr');const kind={C:'Compute',G:'Graphics','C+G':'Compute + graphics'}[p.type]||p.type;
    const memory=typeof p.memory_mib==='number'?(p.memory_mib>=1024?(p.memory_mib/1024).toFixed(2)+' GiB':p.memory_mib.toFixed(0)+' MiB'):'Unavailable';
    for(const value of [p.name,p.pid,kind,memory]){const td=document.createElement('td');td.textContent=value;tr.append(td)}tbody.append(tr)
   }
  }
  const status=bar.querySelector('.telemetry-state');let busy=false;
  function set(index,value,unit,percent,note){
   const d=dials[index],valid=typeof value==='number'&&Number.isFinite(value);
   const text=valid?value.toFixed(index===2||index===4?1:0)+unit:'Unavailable';
   d.querySelector('strong').textContent=text;
   const ring=d.querySelector('.telemetry-ring');ring.setAttribute('aria-label',definitions[index][0]+': '+text+'. '+(note||definitions[index][1]));
   d.querySelector('.dial-fill').style.strokeDasharray=valid&&Number.isFinite(percent)?Math.max(0,Math.min(100,percent))+' 100':'0 100';
   d.classList.toggle('unavailable',!valid);
   d.querySelector('small').textContent=note||definitions[index][1];
  }
  async function refresh(){
   if(busy)return;busy=true;
   try{
    const response=await fetch('/api/gpu',{cache:'no-store'});if(!response.ok)throw Error('Telemetry unavailable');
    const r=await response.json(),g=r.gpus?.[0];if(r.error||!g)throw Error('Telemetry unavailable');
    renderProcesses(r.gpu_processes);
    set(0,g.utilization,'%',g.utilization);set(1,g.memory_utilization,'%',g.memory_utilization);
    const direct=Number.isFinite(g.memory_used_mib)&&g.memory_total_mib>0;
    const used=direct?g.memory_used_mib/1024:r.compute_memory_used_gib,total=direct?g.memory_total_mib/1024:r.system_ram_total_gib;
    set(2,used,' GiB',typeof used==='number'&&total>0?used/total*100:NaN,
     direct?'GPU memory used / total':(typeof used==='number'&&total>0?(used/total*100).toFixed(1)+'% shared RAM · compute only':'Compute allocations unavailable'));
    set(3,g.temperature,'°C',g.temperature);
    set(4,g.power,' W',typeof g.power==='number'?g.power/140*100:NaN,'Limit: 140 W'+(typeof g.power==='number'?' · '+(g.power/140*100).toFixed(1)+'%':''));
    status.textContent=g.name+' · '+new Date(r.timestamp*1000).toLocaleTimeString();status.classList.remove('error');
   }catch{renderProcesses(null);dials.forEach((_,i)=>set(i,null,'',NaN));status.textContent='Telemetry unavailable · retrying';status.classList.add('error')}
   finally{busy=false}
  }
  refresh();setInterval(refresh,2000);
 });
})();
