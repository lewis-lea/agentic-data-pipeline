import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareSeries, validDate, extent, nearestPoint } from './comparison.mjs';

const item={id:'a',currency:'GBP',points:[['2026-01-02',200],['2026-01-05',220],['2026-01-06',180]]};
const options={normalise:true,base:'2026-01-02',start:'2026-01-02',end:'2026-01-06'};
test('normalisation rebases each investment independently to 100',()=>{
  assert.deepEqual(prepareSeries(item,options).points,[['2026-01-02',100],['2026-01-05',110],['2026-01-06',90]]);
  assert.equal(prepareSeries({...item,points:[['2026-01-02',5],['2026-01-05',6]]},options).points[1][1],120);
});
test('native prices retain currency and ignore the unused reference date',()=>{
  const result=prepareSeries(item,{...options,normalise:false,base:''});
  assert.deepEqual(result.points,item.points);assert.equal(result.unit,'GBP');assert.equal(result.reference,null);
});
test('weekend uses prior close; reference can lie outside displayed range',()=>{
  const result=prepareSeries(item,{...options,base:'2026-01-04',start:'2026-01-05'});
  assert.deepEqual(result.reference,['2026-01-02',200]);assert.equal(result.points[0][1],110);
});
test('rejects missing, future and stale reference prices without future filling',()=>{
  assert.match(prepareSeries(item,{...options,base:'2026-01-01'}).error,/on or before/);
  assert.match(prepareSeries(item,{...options,base:'2026-01-07'}).error,/after/);
  assert.match(prepareSeries({...item,points:[['2025-12-01',200],['2026-01-06',180]]},options).error,/seven days/);
  assert.match(prepareSeries(item,{...options,base:''}).error,/reference date/);
});
test('rejects invalid ranges and handles empty or invalid data',()=>{
  for(const range of [{start:''},{end:'2025-12-01'},{start:'2026-02-30'}])assert.match(prepareSeries(item,{...options,...range}).error,/date range/);
  assert.match(prepareSeries({...item,points:[]},options).error,/No price history/);
  assert.match(prepareSeries({...item,points:[['invalid',2],['2026-01-02',NaN],['2026-01-03',0]]},options).error,/No price history/);
  assert.match(prepareSeries(item,{...options,start:'2026-02-01',end:'2026-03-01'}).error,/No observations/);
});
test('sorts data, filters nonfinite values and includes both range endpoints',()=>{
  const result=prepareSeries({...item,points:[['2026-01-06',180],['2026-01-03',Infinity],['2026-01-02',200]]},options);
  assert.deepEqual(result.points,[['2026-01-02',100],['2026-01-06',90]]);
});
test('total returns use adjusted closes; cash dividends are not counted twice',()=>{
  const payout={...item,points:[['2026-01-02',100],['2026-01-05',99]],adjusted_points:[['2026-01-02',99],['2026-01-05',99]],actions:[{date:'2026-01-05',dividends:1}]};
  assert.equal(prepareSeries(payout,options).points[1][1],99);
  const result=prepareSeries(payout,{...options,mode:'total',normalise:false});
  assert.equal(result.points[1][1],100);assert.equal(result.unit,'Index');
  assert.match(prepareSeries(item,{...options,mode:'total'}).error,/Adjusted history unavailable/);
});
test('date validation rejects impossible calendar dates',()=>{
  assert.equal(validDate('2024-02-29'),true);assert.equal(validDate('2026-02-29'),false);
  assert.equal(validDate('2026-99-99'),false);assert.equal(validDate('not-a-date'),false);
});
test('chart extents support flat series and all investments without spread overflow',()=>{
  assert.deepEqual(extent([100,100]),[94,106]);assert.deepEqual(extent([0]),[-.06,.06]);
  assert.deepEqual(extent([1,3]),[.88,3.12]);assert.deepEqual(extent(Array(300000).fill(100)),[94,106]);
});
test('hover lookup uses preceding observations',()=>{
  assert.deepEqual(nearestPoint(item.points,Date.parse('2026-01-04')),item.points[0]);
  assert.deepEqual(nearestPoint(item.points,Date.parse('2026-01-06')),item.points[2]);
  assert.deepEqual(nearestPoint(item.points,Date.parse('2025-01-01')),item.points[0]);
});
