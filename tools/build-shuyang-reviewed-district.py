"""Convert individually observed roof runs, retaining image dates and uncertainty.

No lot subdivision or random building generation. Every roof run is a manually
reviewed observation in wuyue-roof-traces.json; existing source wins overlaps.
"""
import hashlib,json,math,runpy
from pathlib import Path
from shapely.geometry import Polygon,mapping

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'tools/data/shuyang'
frame=runpy.run_path(str(Path(__file__).with_name('enrich-shuyang-buildings.py')))

def main():
    inp=DATA/'wuyue-roof-traces.json';data=json.loads(inp.read_bytes());ref=data['reference']
    x0,y0,x1,y1=ref['extent3857'];width,height=ref['imageSize']
    def wgs(p):
        x=x0+p[0]/width*(x1-x0);y=y1-p[1]/height*(y1-y0)
        return [math.degrees(x/6378137),math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)]
    def world(p):
        lon,lat=wgs(p);return [(lon-frame['LON'])*frame['KX'],-(lat-frame['LAT'])*frame['KY']]
    features=[]
    for group in data['groups']:
        observations=[]
        for i,(ax,ay,bx,by,depth) in enumerate(group.get('runs',[])):
            length=math.hypot(bx-ax,by-ay);nx=-(by-ay)/length*depth;ny=(bx-ax)/length*depth
            pixels=[[ax,ay],[bx,by],[bx+nx,by+ny],[ax+nx,ay+ny]]
            observations.append((f'{i+1:03d}',pixels,'manually-reviewed-roof-run'))
        for outline in group.get('outlines',[]):
            observations.append((outline['id'],outline['pixels'],'manually-reviewed-roof-outline'))
        for ident,pixels,method in observations:
            g=Polygon([wgs(p) for p in pixels]);assert g.is_valid
            features.append({'type':'Feature','geometry':mapping(g),'properties':{
                'id':f"reviewed/wuyue/{group['id']}/{ident}",'communityContext':group['neighborhood'],
                'building':'apartments','height':group['heightEstimate'],'heightSource':'estimate',
                'levelsEstimate':group['levelsEstimate'],'roof:shape':group['roofShape'],'roof:height':group['roofHeightEstimate'],
                'referenceImageDate':ref['imageAcquired'],'geometrySource':method,
                'geometryAccuracyNote':'Approximate observed roofprint; roof lean and source accuracy limit ground alignment.',
                'referencePixels':pixels,'heightNote':group.get('heightNote','Conservative photo-typology/display estimate, not a measured height or official floor count.')}})
    runpy.run_path(str(Path(__file__).with_name('build-shuyang-online-district.py')))['main']()
    online=json.loads((DATA/'online-reviewed-buildings.geojson').read_bytes())
    features.extend(online['features'])
    online_refs=[online['reference'],*online.get('additionalReferences',[])]
    # 万顺·帝景天成: imagery-inferred villa rows expanded from a manual satellite
    # reading (tools/build-wanshun-imagery.py). Kept in its own file so the
    # block/row reconstruction stays auditable and never masquerades as survey.
    wanshun_path=DATA/'reviewed-wanshun-buildings.geojson'
    wanshun_refs=[]
    if wanshun_path.exists():
        wanshun=json.loads(wanshun_path.read_bytes())
        features.extend(wanshun['features'])
        wanshun_refs=[wanshun['reference'],*wanshun.get('additionalReferences',[])]
    trace_bytes=inp.read_bytes()+(DATA/'online-district-traces.json').read_bytes()
    if wanshun_path.exists():
        trace_bytes+=(DATA/'wanshun-imagery-traces.json').read_bytes()
    # Ring-by-ring imagery reading around 万顺·帝景天成 (tools/build-imagery-districts.py).
    # Same discipline as the villa rows: inferred footprints, existing records win overlaps.
    rings_path=DATA/'reviewed-imagery-districts.geojson'
    rings_surfaces=DATA/'imagery-districts-surfaces.json'
    rings_refs=[]
    if rings_path.exists():
        rings=json.loads(rings_path.read_bytes())
        features.extend(rings['features'])
        rings_refs=[rings['reference'],*rings.get('additionalReferences',[])]
        trace_bytes+=(DATA/'imagery-districts-traces.json').read_bytes()
    # 批1 城市骨架：医院/商业/门户设施的影像复核（tools/build-batch1-facilities.py）。
    # 独立文件保留来源、日期与误差，避免与既有街区重建混写。
    batch1_path=DATA/'reviewed-batch1-buildings.geojson'
    batch1_refs=[];batch1_superseded=[];batch1_reasons={};batch1_nonbuilding=[]
    if batch1_path.exists():
        batch1=json.loads(batch1_path.read_bytes())
        features.extend(batch1['features'])
        batch1_refs=[batch1['reference'],*batch1.get('additionalReferences',[])]
        batch1_superseded=batch1.get('supersededSourceIds',[])
        batch1_reasons=batch1.get('supersededReasons',{})
        batch1_nonbuilding=batch1.get('nonBuildingExclusionIds',[])
        trace_bytes+=(DATA/'batch1-facility-traces.json').read_bytes()
    # 批2 未渲染设施：场站铺装与可核实建筑（tools/build-batch1-facilities.py batch2）。
    # 与批1 同一套字段约定，独立文件存放，避免两个批次互相覆盖。
    batch2_path=DATA/'reviewed-batch2-buildings.geojson'
    batch2_refs=[];batch2_superseded=[];batch2_reasons={};batch2_nonbuilding=[]
    if batch2_path.exists():
        batch2=json.loads(batch2_path.read_bytes())
        features.extend(batch2['features'])
        batch2_refs=[batch2['reference'],*batch2.get('additionalReferences',[])]
        batch2_superseded=batch2.get('supersededSourceIds',[])
        batch2_reasons=batch2.get('supersededReasons',{})
        batch2_nonbuilding=batch2.get('nonBuildingExclusionIds',[])
        trace_bytes+=(DATA/'batch2-facility-traces.json').read_bytes()
    # 批2 空地补全：12 个整片空地小区 + 3 所空地学校的影像重建
    # （tools/build-blank-plots-imagery.py）。地块边界沿用 OSM 原值，体量全部为推断。
    blank_path=DATA/'reviewed-blank-plots.geojson'
    blank_refs=[]
    if blank_path.exists():
        blank=json.loads(blank_path.read_bytes())
        features.extend(blank['features'])
        blank_refs=[blank['reference'],*blank.get('additionalReferences',[])]
        trace_bytes+=(DATA/'blank-plots-imagery-traces.json').read_bytes()
    # 来源文件可能因并发重建出现同 ID 候选；重复 ID 会破坏来源顺序索引，
    # 保留首条并显式报告条数，不静默重复。
    deduped=[];seen_ids=set()
    for f in features:
        ident=f['properties']['id']
        if ident in seen_ids:
            continue
        seen_ids.add(ident);deduped.append(f)
    if len(deduped)!=len(features):
        print(json.dumps({'droppedDuplicateFeatureIds':len(features)-len(deduped)}))
    features=deduped
    output={'type':'FeatureCollection','reference':ref,'additionalReferences':online_refs+wanshun_refs+rings_refs+batch1_refs+batch2_refs+blank_refs,
        'traceSha256':hashlib.sha256(trace_bytes).hexdigest(),'features':features,
        'supersededSourceIds':batch1_superseded+batch2_superseded,
        'supersededReasons':batch1_reasons|batch2_reasons,
        'nonBuildingExclusionIds':batch1_nonbuilding+batch2_nonbuilding}
    (DATA/'reviewed-buildings.geojson').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
    contexts=[]
    for n in data['neighborhoods']:
        points=[world(p) for p in n['pixels']];g=Polygon(points);q=g.representative_point()
        contexts.append({'id':n['id'],'name':n['name'],'source':'ReviewedImagery','scope':'approximate-context',
            'boundarySource':'User map labels + dated imagery street-block approximation, not an official estate boundary',
            'referenceImageDate':ref['imageAcquired'],'x':round(q.x,1),'z':round(q.y,1),
            'polygons':[{'outer':[round(v,1) for p in points for v in p],'holes':[]}],
            'photoTypology':n['photoTypology']})
    contexts.extend(json.loads((DATA/'online-reviewed-context.json').read_bytes())['neighborhoods'])
    (DATA/'reviewed-district-context.json').write_text(json.dumps({'reference':ref,'additionalReferences':online_refs,'neighborhoods':contexts},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    surfaces=[]
    for s in data.get('surfaces',[]):
        rings=[[world(p) for p in r] for r in s['rings']]
        curved=s['kind'] in ('running-track','infield') or s['id'].endswith('/infield-apron')
        if curved:
            # The photograph shows smooth track curves. Round the reviewed
            # samples consistently on both sides of shared rings; keep the raw
            # source pixels above, and never turn court rectangles into curves.
            for _ in range(2):
                rings=[[[a[0]*t+b[0]*(1-t),a[1]*t+b[1]*(1-t)]
                        for a,b in zip(r,r[1:]+r[:1]) for t in (.75,.25)] for r in rings]
        g=Polygon(rings[0],rings[1:]);assert g.is_valid, s['id']
        surfaces.append({k:s[k] for k in ('id','kind','name','sourceSiteId')}|{'rings':rings,
            'geometryMethod':'reviewed-pixel-boundary; 2-pass corner rounding of observed curved edges' if curved else 'reviewed-pixel-boundary'})
    surfaces.extend(json.loads((DATA/'online-reviewed-surfaces.json').read_bytes())['surfaces'])
    wanshun_surfaces=DATA/'wanshun-reviewed-surfaces.json'
    if wanshun_surfaces.exists():
        surfaces.extend(json.loads(wanshun_surfaces.read_bytes())['surfaces'])
    if rings_surfaces.exists():
        surfaces.extend(json.loads(rings_surfaces.read_bytes())['surfaces'])
    batch1_surfaces=DATA/'batch1-facility-surfaces.json'
    if batch1_surfaces.exists():
        surfaces.extend(json.loads(batch1_surfaces.read_bytes())['surfaces'])
    batch2_surfaces=DATA/'batch2-facility-surfaces.json'
    if batch2_surfaces.exists():
        surfaces.extend(json.loads(batch2_surfaces.read_bytes())['surfaces'])
    blank_surfaces=DATA/'blank-plots-surfaces.json'
    if blank_surfaces.exists():
        surfaces.extend(json.loads(blank_surfaces.read_bytes())['surfaces'])
    (DATA/'reviewed-district-surfaces.json').write_text(json.dumps({'reference':ref,'additionalReferences':online_refs+wanshun_refs+rings_refs,'reviewNote':data.get('surfaceReview',''),
        'surfaces':surfaces},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
    print(json.dumps({'observedRoofCandidates':len(features),'reviewedSurfaces':len(surfaces),'approximateNamedContexts':len(contexts),'imageAcquired':ref['imageAcquired']}))

if __name__=='__main__':main()
