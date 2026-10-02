const REPO="1993velezpadilla-source/config-old-3";
const WORKFLOW="hayuya-queue.yml";
const BRANCH="art/hayuya-monster-v1";
const API=`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?branch=${encodeURIComponent(BRANCH)}&per_page=40`;

let jobs=[];
let activeFilter="all";

function parseTitle(run){
  let text=(run.display_title||"").replace(/^HAYUYA\s*•\s*/i,"").trim();
  const match=text.match(/^HAYUYA_JOB\s+(.+?)\s*::\s*([^:]+?)\s*::\s*(.+)$/i);
  if(match) return {owner:match[1].trim(),jobId:match[2].trim(),title:match[3].trim()};
  return {owner:"HAYUYA",jobId:`run-${run.run_number}`,title:text||"Model job"};
}
function stateOf(run){
  if(run.status==="queued"||run.status==="waiting"||run.status==="pending") return "waiting";
  if(run.status==="in_progress"||run.status==="requested") return "running";
  if(run.status==="completed"&&run.conclusion==="success") return "done";
  if(run.status==="completed") return "failed";
  return "waiting";
}
function age(iso){
  const sec=Math.max(0,(Date.now()-new Date(iso).getTime())/1000);
  if(sec<60)return `${Math.floor(sec)}s ago`;
  if(sec<3600)return `${Math.floor(sec/60)}m ago`;
  if(sec<86400)return `${Math.floor(sec/3600)}h ago`;
  return `${Math.floor(sec/86400)}d ago`;
}
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function render(){
  const list=document.getElementById("jobs");
  const counts={running:0,waiting:0,done:0,failed:0};
  jobs.forEach(j=>counts[j.state]++);
  Object.keys(counts).forEach(k=>document.getElementById(k+"Count").textContent=counts[k]);

  const visible=jobs.filter(j=>activeFilter==="all"||j.state===activeFilter);
  list.innerHTML=visible.length?visible.map(j=>`
    <a class="job" href="${j.url}" target="_blank" rel="noopener">
      <div class="job-top">
        <div style="min-width:0">
          <div class="owner">${esc(j.owner)}</div>
          <div class="title">${esc(j.title)}</div>
          <div class="jobid">${esc(j.jobId)}</div>
        </div>
        <span class="badge ${j.state}">${j.state==="done"?"GENERATED":j.state.toUpperCase()}</span>
      </div>
      <div class="meta">
        <span>Action #${j.runNumber}</span>
        <span>${age(j.createdAt)}</span>
      </div>
    </a>`).join(""):`<div class="empty">No hay trabajos en esta vista.</div>`;
}
async function load(){
  const btn=document.getElementById("refresh");
  btn.disabled=true;
  try{
    const res=await fetch(API,{headers:{"Accept":"application/vnd.github+json"},cache:"no-store"});
    if(!res.ok) throw new Error(`GitHub API ${res.status}`);
    const data=await res.json();
    jobs=(data.workflow_runs||[])
      .filter(r=>(r.event==="push"||r.event==="workflow_dispatch") && /HAYUYA_JOB/i.test(r.display_title||""))
      .map(r=>{
        const meta=parseTitle(r);
        return {...meta,state:stateOf(r),url:r.html_url,runNumber:r.run_number,createdAt:r.created_at};
      });
    document.getElementById("updated").textContent="Updated "+new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
    render();
  }catch(err){
    document.getElementById("jobs").innerHTML=`<div class="empty">No pude leer GitHub ahora mismo: ${esc(err.message)}</div>`;
  }finally{btn.disabled=false}
}
document.getElementById("refresh").addEventListener("click",load);
document.getElementById("filters").addEventListener("click",e=>{
  const b=e.target.closest("button[data-filter]");if(!b)return;
  activeFilter=b.dataset.filter;
  document.querySelectorAll("#filters button").forEach(x=>x.classList.toggle("active",x===b));
  render();
});
load();
setInterval(load,120000);
