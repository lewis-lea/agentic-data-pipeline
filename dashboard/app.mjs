import { prepareSeries, extent, nearestPoint } from './comparison.mjs';

const $ = id => document.getElementById(id);
const palette = ['#1764d5','#d15c25','#008779','#9452b4','#be3f72','#947209','#426079','#378ac1'];
let data, plotted = [], scales = {}, priceNormalise = true;
const selected = new Set(), hidden = new Set();
const colour = item => palette[data.instruments.indexOf(item) % palette.length];
const format = value => new Intl.NumberFormat('en-GB', {maximumFractionDigits:2}).format(value);
const el = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; };
const svg = (tag, attrs, text) => {const e = document.createElementNS('http://www.w3.org/2000/svg',tag); for (const [k,v] of Object.entries(attrs)) e.setAttribute(k,v); if(text!=null)e.textContent=text; return e;};

function investmentList() {
  const query = $('search').value.toLowerCase(), category = $('category').value;
  const list = $('investments'); list.replaceChildren();
  let count = 0;
  for (const item of data.instruments) {
    if (category !== 'all' && category !== item.category) continue;
    if (!`${item.name} ${item.theme || ''} ${item.symbol || ''}`.toLowerCase().includes(query)) continue;
    count++;
    const available = item.points.length > 0;
    const row = el('label',null,`investment${available ? '' : ' unavailable'}`);
    const check = el('input'); check.type = 'checkbox'; check.checked = selected.has(item.id);
    check.disabled = !available;
    check.addEventListener('change', () => {
      check.checked ? selected.add(item.id) : selected.delete(item.id);
      hidden.delete(item.id); render();
    });
    const body = el('span'); body.append(el('strong',item.theme || item.name));
    body.append(el('small',item.theme ? item.name : `${item.symbol || 'Unmapped'} · ${item.category}`));
    if (item.theme && item.symbol) body.append(el('small',item.symbol));
    if (item.mapping_note) body.append(el('small',item.mapping_note));
    if (!available) body.append(el('small',item.error || 'No Yahoo history available.'));
    else if(item.status === 'stale') body.append(el('small','Refresh failed · showing saved history'));
    row.append(check,body); list.append(row);
  }
  if (!count) list.append(el('p','No investments match your search.','muted'));
  $('selected-count').textContent = `${selected.size} selected`;
}

function legend() {
  $('legend').replaceChildren();
  for (const item of data.instruments.filter(i => selected.has(i.id))) {
    const button = el('button'); button.type='button';
    button.setAttribute('aria-pressed',String(!hidden.has(item.id)));
    button.setAttribute('aria-label',`${hidden.has(item.id) ? 'Show' : 'Hide'} ${item.name}`);
    const dot = el('span',null,'swatch');dot.style.background=colour(item);
    button.append(dot,el('span',item.theme || item.name));
    button.addEventListener('click',()=>{hidden.has(item.id)?hidden.delete(item.id):hidden.add(item.id);render();});
    $('legend').append(button);
  }
}

function render() {
  const total = $('return-mode').value === 'total';
  const options = {normalise:total || $('normalise').checked,mode:total?'total':'price',base:$('base').value,start:$('start').value,end:$('end').value};
  $('normalise').disabled=total;
  $('base').disabled=!options.normalise;
  $('method').textContent=total ? 'Total return = 100 × adjusted close / reference adjusted close. Uses Yahoo’s distribution and split adjustments, approximating reinvestment before personal taxes and fees. Reference dates appear below.' : options.normalise
    ? 'Reference = 100. Uses the last close on or before your date (up to 7 days earlier); actual dates appear below.'
    : 'Daily close in native currency. UK pence converted to pounds. Separate currency axes; no FX conversion.';
  $('chart-title').textContent = total ? 'Total return · indexed to 100' : options.normalise ? 'Price comparison · indexed to 100' : 'Price comparison · native currency';
  const warnings=[];
  plotted=[];
  for(const item of data.instruments.filter(i=>selected.has(i.id)&&!hidden.has(i.id))) {
    const series=prepareSeries(item,options);
    if(series.error)warnings.push(`${item.theme || item.name}: ${series.error}`);
    else {series.colour=colour(item);plotted.push(series);}
    if(item.points.length && Date.parse(data.generated_at)-Date.parse(item.points.at(-1)[0])>7*86400000)warnings.push(`${item.theme || item.name}: history ends ${item.points.at(-1)[0]}.`);
    if(item.status==='stale')warnings.push(`${item.theme || item.name}: refresh failed; saved history is shown.`);
  }
  $('message').hidden=!warnings.length;
  $('message').textContent=warnings.join(' ');
  investmentList();legend();draw(options);comparison(options);distributions(options);
}

function draw(options) {
  const chart=$('chart');chart.replaceChildren();$('tooltip').hidden=true;
  $('empty').hidden=plotted.length>0;
  if(!plotted.length)return;
  const units=[...new Set(plotted.map(s=>s.unit))];
  const bounds={left:80,right:units.length>2?820:910,top:40,bottom:424};
  const min=Date.parse(options.start),max=Date.parse(options.end);
  const x=d=>bounds.left+(Date.parse(d)-min)/(max-min||86400000)*(bounds.right-bounds.left);
  scales={x,bounds,min,max};
  for(let i=0;i<5;i++) {
    const y=bounds.top+i*(bounds.bottom-bounds.top)/4;
    chart.append(svg('line',{x1:bounds.left,x2:bounds.right,y1:y,y2:y,class:'grid-line'}));
  }
  for(let i=0;i<5;i++) {
    const stamp=new Date(min+(max-min)*i/4);
    chart.append(svg('text',{x:bounds.left+i*(bounds.right-bounds.left)/4,y:457,'text-anchor':'middle',class:'axis-label'},stamp.toLocaleDateString('en-GB',{month:'short',year:'2-digit',timeZone:'UTC'})));
  }
  units.forEach((unit,index)=>{
    const values=plotted.filter(s=>s.unit===unit).flatMap(s=>s.points.map(p=>p[1]));
    const [low,high]=extent(values);
    const y=v=>bounds.bottom-(v-low)/(high-low)*(bounds.bottom-bounds.top);
    scales[unit]=y;
    const ax=index===0?bounds.left-12:bounds.right+12+(index-1)*80;
    const anchor=index===0?'end':'start';
    chart.append(svg('text',{x:ax,y:19,'text-anchor':anchor,class:'axis-label'},unit));
    for(let i=0;i<5;i++)chart.append(svg('text',{x:ax,y:bounds.top+i*(bounds.bottom-bounds.top)/4+4,'text-anchor':anchor,class:'axis-label'},format(high-i*(high-low)/4)));
    if(options.normalise&&low<=100&&high>=100)chart.append(svg('line',{x1:bounds.left,x2:bounds.right,y1:y(100),y2:y(100),stroke:'#8b9fac','stroke-dasharray':'5 5'}));
  });
  for(const s of plotted){
    // Start a new segment across prolonged missing history; never interpolate it.
    let last=null;
    const path=s.points.map(([d,p])=>{const move=last===null||Date.parse(d)-last>7*86400000;last=Date.parse(d);return `${move?'M':'L'}${x(d).toFixed(2)},${scales[s.unit](p).toFixed(2)}`;}).join(' ');
    const line=svg('path',{d:path,stroke:s.colour,class:'chart-line'});
    line.append(svg('title',{},s.name));chart.append(line);
    const lastPoint=s.points.at(-1);
    chart.append(svg('circle',{cx:x(lastPoint[0]),cy:scales[s.unit](lastPoint[1]),r:3,fill:s.colour}));
  }
  chart.setAttribute('aria-label',`${options.normalise?'Normalised':'Native currency'} daily price histories for ${plotted.map(s=>s.name).join(', ')}. Values are also listed in the table below.`);
}

function comparison(options) {
  $('comparison').replaceChildren();
  for(const s of plotted){
    const tr=el('tr'),name=el('td',s.name);name.style.borderLeft=`3px solid ${s.colour}`;
    name.append(el('small',s.symbol));
    const ref=el('td',s.reference?`${s.currency} ${format(s.reference[1])}`:'—');
    if(s.reference)ref.append(el('small',s.reference[0]+(options.mode==='total'?' · adjusted':'')));
    const last=s.points.at(-1),value=el('td',`${options.normalise?'':s.currency+' '}${format(last[1])}`);
    if(options.normalise)value.append(el('small',`${last[1]>=100?'+':''}${format(last[1]-100)}% from reference`));
    tr.append(name,ref,value,el('td',last[0]));$('comparison').append(tr);
  }
}

function distributions(options) {
  const table=$('distributions');table.replaceChildren();
  const rows=plotted.flatMap(s=>(s.actions || []).filter(e=>e.date>=options.start&&e.date<=options.end).map(e=>({...e,item:s}))).sort((a,b)=>b.date.localeCompare(a.date));
  for(const event of rows){
    const tr=el('tr');
    const cash=value=>value==null?'Unknown':`${event.item.quote_currency} ${new Intl.NumberFormat('en-GB',{maximumFractionDigits:6}).format(value)}`;
    tr.append(el('td',event.item.name),el('td',event.date),el('td',cash(event.dividends)),el('td',cash(event.capital_gains)),el('td',event.stock_splits?`${event.stock_splits}:1`:'—'));
    table.append(tr);
  }
  if(!rows.length){const tr=el('tr'),td=el('td','No reported events in this selection.');td.colSpan=5;tr.append(td);table.append(tr);}
}

$('chart').addEventListener('pointermove',event=>{
  if(!plotted.length)return;
  const rect=$('chart').getBoundingClientRect();
  const coordinate=(event.clientX-rect.left)/rect.width*1000;
  if(coordinate<scales.bounds.left||coordinate>scales.bounds.right){$('tooltip').hidden=true;return;}
  const day=scales.min+(coordinate-scales.bounds.left)/(scales.bounds.right-scales.bounds.left)*(scales.max-scales.min);
  const tip=$('tooltip');tip.replaceChildren();
  tip.append(el('strong',new Date(day).toISOString().slice(0,10)));
  for(const s of plotted.slice(0,10)){
    const [d,p]=nearestPoint(s.points,day);
    // Avoid claiming future or stale observations as the hovered day's price.
    if(Date.parse(d)>day||day-Date.parse(d)>7*86400000)continue;
    tip.append(el('p',`${s.symbol}: ${format(p)} ${s.unit} · ${d}`));
  }
  if(plotted.length>10)tip.append(el('p',`+ ${plotted.length-10} more in the table`));
  tip.style.left=`${Math.max(0,Math.min(event.clientX-rect.left+12,rect.width-280))}px`;
  tip.style.top='20px';tip.hidden=false;
});
$('chart').addEventListener('pointerleave',()=>{$('tooltip').hidden=true;});
for(const id of ['normalise','start','end','base'])$(id).addEventListener('change',()=>{if(data)render();});
$('return-mode').addEventListener('change',()=>{
  if($('return-mode').value==='total'){priceNormalise=$('normalise').checked;$('normalise').checked=true;}
  else $('normalise').checked=priceNormalise;
  if(data)render();
});
for(const id of ['search','category'])$(id).addEventListener('input',()=>{if(data)investmentList();});
$('clear').addEventListener('click',()=>{selected.clear();hidden.clear();if(data)render();});

async function initialise(){
  try {
    const response=await fetch('./prices.json',{cache:'no-cache'});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    data=await response.json();
    if(data.schema_version!==1||!Array.isArray(data.instruments))throw new Error('Unsupported snapshot');
    const available=data.instruments.filter(i=>i.points?.length);
    const days=available.flatMap(i=>[i.points[0][0],i.points.at(-1)[0]]).sort();
    if(!days.length)throw new Error('No available histories');
    const latest=days.at(-1),earliest=days[0];
    const oneYear=new Date(latest);oneYear.setUTCFullYear(oneYear.getUTCFullYear()-1);
    const start=oneYear.toISOString().slice(0,10)>earliest?oneYear.toISOString().slice(0,10):earliest;
    $('start').value=start;$('end').value=latest;$('base').value=start;
    for(const id of ['start','end','base']){$(id).min=earliest;$(id).max=latest;}
    const defaults=['AAPL','MSFT','NVDA'];
    for(const s of defaults){const item=available.find(i=>i.symbol===s);if(item)selected.add(item.id);}
    if(!selected.size)available.slice(0,3).forEach(i=>selected.add(i.id));
    const age=(Date.now()-Date.parse(data.generated_at))/86400000;
    $('freshness').textContent=`Refresh ${data.generated_at.slice(0,10)} · ${available.length}/${data.instruments.length} histories${age>4?' · Refresh overdue':''}`;
    $('count').textContent=String(data.instruments.length);
    $('catalogue-date').textContent=`Range checked ${data.catalogue_checked_at}.`;
    render();
  }catch(error){
    $('freshness').textContent='Price history unavailable';
    $('investments').replaceChildren(el('p','The price snapshot could not be loaded. Please try again after the next refresh.','muted'));
    $('empty').hidden=false;
    $('empty').querySelector('h3').textContent='Waiting for price history';
    $('empty').querySelector('p').textContent='A successful data refresh is needed before investments can be plotted.';
    $('message').hidden=false;$('message').textContent='Could not load the published dataset. No sample prices are shown.';
    console.error('Dashboard load failed:',error);
  }
}
initialise();
