import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';

for (const synthetic of [false, true]) test(`dashboard controls and provenance (synthetic=${synthetic})`, async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const dom = new JSDOM(html, {url:'https://example.test/'});
  globalThis.document = dom.window.document;
  const points = [['2025-09-04',100],['2026-09-03',110],['2026-09-04',120]];
  globalThis.fetch = async () => ({ok:true,json:async()=>({schema_version:1,synthetic,simulation:{seed:2502026},generated_at:'2026-09-04T23:00:00Z',catalogue_checked_at:'2026-09-04',instruments:[
    {id:'grg-l',name:'Greggs',symbol:'GRG.L',category:'Shares',currency:'GBP',quote_currency:'GBP',status:'ok',points,adjusted_points:[['2025-09-04',90],['2026-09-03',105],['2026-09-04',120]],actions:[{date:'2026-09-03',dividends:1,capital_gains:0,stock_splits:0}]},
    {id:'dnlm-l',name:'Dunelm Group',symbol:'DNLM.L',category:'Shares',currency:'GBP',quote_currency:'GBP',status:'ok',points,adjusted_points:points,actions:[]},
    {id:'missing',name:'Unavailable example share',symbol:null,category:'Shares',points:[],error:'Mapping unavailable'}
  ]})});
  await import(`./app.mjs?synthetic=${synthetic}`);
  await new Promise(resolve=>setImmediate(resolve));
  const $ = id=>document.getElementById(id);
  assert.equal($('data-notice').hidden, !synthetic);
  assert.equal($('chart').textContent.includes('SYNTHETIC DATA'), synthetic);
  if(synthetic){assert.match($('freshness').textContent,/Synthetic demonstration/);assert.match($('distribution-method').textContent,/fictional/);}
  const change = (id,value) => {$(id).value=value;$(id).dispatchEvent(new dom.window.Event('change'));};
  assert.equal(document.querySelectorAll('.chart-line').length,2);
  assert.equal($('comparison').children.length,2);
  assert.match($('distributions').textContent,/GBP 1/);
  assert.equal(document.querySelectorAll('#investments input:disabled').length,1);
  $('normalise').checked=false;$('normalise').dispatchEvent(new dom.window.Event('change'));
  assert.equal($('base').disabled,true);
  change('return-mode','total');
  assert.equal($('normalise').checked,true);
  assert.equal($('normalise').disabled,true);
  assert.match($('comparison').textContent,/33.33%/);
  change('return-mode','price');
  assert.equal($('normalise').checked,false);
  $('legend').firstElementChild.click();
  assert.equal(document.querySelectorAll('.chart-line').length,1);
  assert.equal($('legend').firstElementChild.getAttribute('aria-pressed'),'false');
  $('legend').firstElementChild.click();
  assert.equal(document.querySelectorAll('.chart-line').length,2);
  $('search').value='Dunelm';$('search').dispatchEvent(new dom.window.Event('input'));
  assert.equal($('investments').children.length,1);
  $('investments').querySelector('input').click();
  assert.equal(document.querySelectorAll('.chart-line').length,1);
  $('normalise').checked=true;
  change('base','2020-01-01');
  assert.equal($('message').hidden,false);
  assert.equal(document.querySelectorAll('.chart-line').length,0);
  $('clear').click();
  assert.equal($('selected-count').textContent,'0 selected');
  assert.equal($('empty').hidden,false);
  dom.window.close();
  delete globalThis.document;delete globalThis.fetch;
});
