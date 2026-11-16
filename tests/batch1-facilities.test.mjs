import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {GEO} from '../js/shuyang-geodata.js';

// 批1 城市骨架：医院/商业/门户设施的影像复核（tools/build-batch1-facilities.py）。
// 只补影像可核实的体量与场地；推断项必须带来源、日期与误差，实测记录不被推断取代。
const load=name=>JSON.parse(readFileSync(new URL('../tools/data/shuyang/'+name,import.meta.url)));
const records=JSON.parse(gunzipSync(readFileSync(new URL('../tools/data/shuyang/buildings-enriched.json.gz',import.meta.url)))).buildings;
const traces=load('batch1-facility-traces.json');
const marker=traces.reference.id;
const BY_ID=new Map(records.map(b=>[b.id,b]));

test('the batch-1 imagery reference keeps its unknown capture date and stated limits',()=>{
  assert.equal(marker,'amap-satellite-z18-20261115');
  assert.match(traces.reference.provider,/高德/);
  assert.equal(traces.reference.imageAcquired,null,'检索日期不是拍摄日期');
  assert.match(traces.reference.retrievedAt,/^2026-11-15/);
  assert.match(traces.reference.limitations,/0\.5 m\/px/);
  assert.match(traces.reference.limitations,/不是逐栋实测/);
});

test('the reviewed stadium ring replaces the park landuse polygon without deleting its record',()=>{
  const stands=GEO.mapBuildings.find(p=>p.id==='reviewed/batch1/sports-center/stadium-stands');
  assert.ok(stands,'stadium stands render');
  assert.equal(stands.s,'ReviewedImagery');assert.equal(stands.h,16);assert.equal(stands.sup,undefined);
  const record=BY_ID.get(stands.id);
  assert.equal(record.heightSource,'estimate');
  assert.equal(record.geometrySource,'imagery-reviewed-stadium-ring');
  assert.equal(record.geometryReference.referenceId,marker);
  assert.equal(record.geometryReference.imageDate,null);
  assert.match(record.geometryReference.accuracyNote,/±5 m/);
  // 被替代的 OSM 体育公园用地仍是来源记录，只是在渲染层隐藏。
  const excluded=GEO.buildingAudit.reviewedImagery.nonBuildingExclusionIds;
  assert.deepEqual(excluded,['way/1455053507']);
  assert.ok(BY_ID.get('way/1455053507'),'the landuse record stays in the extract');
  const index=records.findIndex(b=>b.id==='way/1455053507');
  assert.ok(GEO.supersededSourceIndices.includes(index));
  assert.equal(GEO.mapBuildings.find(p=>p.id==='way/1455053507').sup,1,'map and scene hide the same record');
});

test('the track and infield enter as reviewed surfaces with the same imagery reference',()=>{
  const surfaces=GEO.urban.surfaces.filter(s=>String(s.id).startsWith('reviewed/batch1/sports-center/'));
  assert.deepEqual(surfaces.map(s=>s.kind).sort(),['infield','running-track']);
  for(const s of surfaces){
    assert.equal(s.source,'ReviewedImagery');
    assert.equal(s.sourceSiteId,'reviewed/batch1/sports-center');
    assert.equal(s.referenceId,marker);assert.equal(s.imageAcquired,null);
    assert.match(s.geometryMethod,/imagery-inferred/);
    assert.ok(s.polygons.length&&s.polygons[0].outer.length>=6);
  }
  const track=surfaces.find(s=>s.kind==='running-track');
  assert.ok(track.polygons[0].holes.length,'the track is a ring, not a filled oval');
  assert.ok(track.widthEstimate>=8);
});

test('name and floor-count corrections keep the surveyed geometry and mark inferred heights',()=>{
  const zhongshan=BY_ID.get('d06b6242-c893-4547-a90e-83db000e0947');
  assert.equal(zhongshan.name,'中山医院门诊病房综合楼');
  assert.equal(zhongshan.category,'civic');
  assert.equal(zhongshan.height,82);assert.equal(zhongshan.levels,24);
  assert.equal(zhongshan.heightSource,'reviewed-floor-count');
  assert.match(zhongshan.heightNote,/3\.4/);
  assert.equal(zhongshan.source,'Overture','geometry is untouched, only the massing height is corrected');
  for(const [id,name] of [['way/995943344','沭阳站'],['way/1371978209','沭阳中兴医院'],
      ['way/1456180593','沭阳县中医院南关院区'],['7338d927-ec19-430a-9e3d-2e75f29d9c2b','沭阳仁慈医院'],
      ['494c7985-f93b-43de-ab6a-64c795b9e7fa','沭阳医院城西院区'],
      ['3d4e35b3-8abc-49c0-9f4e-a99150cac09e','沭阳脑科医院']]){
    const b=BY_ID.get(id);
    assert.ok(b,id+' stays in the source extract');
    assert.equal(b.name,name);assert.equal(b.category,'civic');
    assert.notEqual(b.heightSource,'reviewed-floor-count','no invented floor counts for unread facades');
  }
});

test('the bus depot yard is a reviewed surface and its sheds keep surveyed geometry',()=>{
  const yard=GEO.urban.surfaces.find(s=>s.id==='reviewed/batch1/chengbei-bus/chengbei-yard');
  assert.ok(yard);assert.equal(yard.kind,'parking');
  assert.equal(yard.referenceId,marker);assert.equal(yard.imageAcquired,null);
  assert.equal(BY_ID.get('way/1265743025').name,'城北公交停保场调度楼');
  assert.equal(BY_ID.get('way/1265743026').category,'industrial');
});

test('facilities that imagery or data could not resolve stay declared, not invented',()=>{
  const notDone=traces.notDoneFacilities.map(f=>f.name);
  assert.ok(notDone.includes('沭阳海洋馆'),'an under-construction site is not massed from imagery');
  for(const fac of traces.facilities){
    for(const note of fac.notDone||[])assert.ok(note.length>10);
  }
  assert.equal(GEO.mapBuildings.filter(p=>p.id.startsWith('reviewed/batch1/')).length,
    traces.facilities.reduce((n,f)=>n+f.buildings.length,0),'no footprint is generated outside the traces');
});
