import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {GEO} from '../js/shuyang-geodata.js';

// 万顺·帝景天成：OSM 在该地块没有建筑，渲染曾因此呈现为空地。
// 补录全部来自高德卫星影像判读，必须保持“影像推断”标注，不能当成实测。
const load=name=>JSON.parse(readFileSync(new URL('../tools/data/shuyang/'+name,import.meta.url)));
const records=JSON.parse(gunzipSync(readFileSync(new URL('../tools/data/shuyang/buildings-enriched.json.gz',import.meta.url)))).buildings;
const traces=load('wanshun-imagery-traces.json');
const reviewed=load('reviewed-buildings.geojson');
const plot=traces.district.boundary;
const inside=(ring,x,z)=>{let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const [xi,zi]=ring[i],[xj,zj]=ring[j];
  if((zi>z)!==(zj>z)&&x<(xj-xi)*(z-zi)/(zj-zi)+xi)yes=!yes;}return yes;};
const added=records.filter(b=>b.id.startsWith('reviewed/wanshun/'));
const marker=traces.reference.id;

test('the supplemental footprints keep the imagery reference, unknown capture date and stated limits',()=>{
  assert.equal(marker,'amap-satellite-z18-20261115');
  assert.match(traces.reference.provider,/高德/);
  assert.equal(traces.reference.imageAcquired,null,'检索日期不是拍摄日期');
  assert.match(traces.reference.retrievedAt,/^2026-11-15/);
  assert.match(traces.reference.limitations,/0\.5 m\/px/);
  assert.match(traces.reference.limitations,/不是逐栋实测/);
  const ref=reviewed.additionalReferences.find(r=>r.id===marker);
  assert.ok(ref,'reviewed-buildings.geojson carries the imagery reference');
  assert.equal(ref.imageAcquired,null);
  assert.equal(ref.coordinateNote,traces.reference.coordinateNote);
});

test('no OSM building existed in the plot; every supplemental footprint stays inside the OSM boundary',()=>{
  assert.match(traces.district.boundarySource,/OSM landuse=residential/);
  assert.match(traces.district.boundarySource,/沿用/);
  const osm=records.filter(b=>b.source==='OSM'&&inside(plot,b.polygons[0].outer[0][0],b.polygons[0].outer[0][1]));
  assert.equal(osm.length,0,'the gap was an OSM data gap, not a clipping or layer omission');
  assert.equal(added.length,51);assert.equal(added.filter(b=>b.id.includes('/villa/')).length,50);
  for(const b of added){assert.equal(b.source,'ReviewedImagery');
    for(const p of b.polygons[0].outer)assert.ok(inside(plot,p[0],p[1]),b.id+' corner leaves the OSM plot');}
});

test('villa rows and the southern canopy are labelled as imagery reconstruction, not survey',()=>{
  for(const b of added){
    assert.equal(b.heightSource,'estimate');assert.equal(b.heightMatch,undefined);
    assert.equal(b.geometryReference.referenceId,marker);
    assert.equal(b.geometryReference.imageDate,null);
    assert.match(b.geometryReference.accuracyNote,/不是逐栋实测/);
    assert.ok(GEO.mapBuildings.some(p=>p.id===b.id&&p.s==='ReviewedImagery'&&!p.sup),'map and 3D share one list');
  }
  const villas=added.filter(b=>b.id.includes('/villa/'));
  for(const b of villas){assert.equal(b.height,12.4);assert.equal(b.levels,3);assert.equal(b.roofShape,'hipped');
    assert.equal(b.geometrySource,'imagery-reconstructed-villa-row');
    assert.match(b.heightNote,/推断/);assert.match(b.heightNote,/不是测量高度/);}
  const market=added.find(b=>b.geometrySource==='imagery-reviewed-outline');
  assert.equal(market.id,'reviewed/wanshun/south-canopy');assert.equal(market.category,'commercial');
  assert.equal(market.height,9);assert.equal(market.levels,0);
});

test('coarse Overture massing replaced by the reconstruction is hidden on both the map and the 3D scene',()=>{
  const superseded=GEO.supersededSourceIndices.map(i=>records[i]);
  const coarse=superseded.filter(b=>b.source==='Overture');
  assert.equal(coarse.length,30);
  for(const b of coarse)assert.ok(inside(plot,b.polygons[0].outer[0][0],b.polygons[0].outer[0][1]),b.id+' sits in the reconstructed plot');
  // 批1：体育公园用地多边形是 OSM 实测的用地而非建筑，排除出建筑层；记录保留、仅隐藏渲染。
  const exclusions=GEO.buildingAudit.reviewedImagery.nonBuildingExclusionIds;
  for(const b of superseded.filter(b=>b.source!=='Overture'))
    assert.ok(exclusions.includes(b.id),b.id+' must be a declared non-building exclusion');
  for(const b of superseded)assert.ok(GEO.mapBuildings.some(p=>p.id===b.id&&p.sup===1),'map hides the same records as the scene');
  assert.equal(GEO.supersededSourceIndices.every(i=>records[i]),true);
});

test('internal lanes and green strips enter GEO as reviewed surfaces with the same imagery reference',()=>{
  const surfaces=GEO.urban.surfaces.filter(s=>s.id.startsWith('reviewed/wanshun/'));
  assert.equal(surfaces.filter(s=>s.kind==='community-path').length,15);
  assert.equal(surfaces.filter(s=>s.kind==='green').length,12);
  for(const s of surfaces){
    assert.equal(s.source,'ReviewedImagery');assert.equal(s.sourceSiteId,'reviewed/wanshun');
    assert.equal(s.referenceId,marker);assert.equal(s.imageAcquired,null);
    assert.match(s.geometryMethod,/imagery-inferred/);assert.ok(s.polygons.length);
    for(const poly of s.polygons)for(let i=0;i<poly.outer.length;i+=2)
      assert.ok(inside(plot,poly.outer[i],poly.outer[i+1]),s.id+' leaves the OSM plot');
  }
  for(const s of surfaces.filter(s=>s.kind==='community-path'))assert.ok(s.widthEstimate>=5);
});
