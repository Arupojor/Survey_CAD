"""True-scale DXF/DWG output and auditable quantity schedules."""
from pathlib import Path
import csv, json, math, os, subprocess, tempfile, time, sys
from dataclasses import asdict
import ezdxf
from engine import InputError, poly_area
from long_profile import ATTRIBUTION

LAYERS={'PRE_WORK':3,'POST_WORK':1,'FILL_BOUNDARY':2,'CUT_BOUNDARY':6,'FILL_HATCH':8,'CUT_HATCH':4,'TABLES':7,'NOTES':7,'GRID':9}

def text(ms,x,y,value,height=.55,layer='NOTES'):
    # CAD text control syntax must not be interpreted from workbook/source labels.
    value=str(value).replace('%%','% %').replace('\n',' ').replace('\r',' ')
    ms.add_text(value,dxfattribs={'insert':(x,y),'height':height,'layer':layer})

def table(ms,x,y,headers,rows,widths,h=1.65,th=.52):
    xx=[x]
    for w in widths: xx.append(xx[-1]+w)
    yy=[y-i*h for i in range(len(rows)+2)]
    for xxv in xx: ms.add_line((xxv,yy[0]),(xxv,yy[-1]),dxfattribs={'layer':'TABLES'})
    for yyv in yy: ms.add_line((xx[0],yyv),(xx[-1],yyv),dxfattribs={'layer':'TABLES'})
    for ri,row in enumerate([headers]+rows):
        for ci,v in enumerate(row):
            text(ms,xx[ci]+.32,y-ri*h-h*.72,v,th,'TABLES')
    return xx[-1],yy[-1]

def new_doc():
    doc=ezdxf.new('R2018',setup=True); doc.units=6
    doc.header['$MEASUREMENT']=1; doc.header['$LUPREC']=3
    for layer,c in LAYERS.items(): doc.layers.new(layer,dxfattribs={'color':c})
    doc.appids.new('EARTHWORK')
    return doc

def section_drawing(doc,s,x,y,index):
    ms=doc.modelspace(); lo=min(p[1] for p in s.pre+s.post); hi=max(p[1] for p in s.pre+s.post)
    minx=s.pre[0][0]; maxx=s.pre[-1][0]
    # Only translate profiles. Neither model axis is exaggerated or scaled.
    ox=x-minx; oy=y-7-hi
    trans=lambda pts:[(px+ox,py+oy) for px,py in pts]
    text(ms,x,y,f'SECTION {index:02d}  /  CHAINAGE {s.chainage:.3f} m',.85)
    text(ms,x,y-1.6,f'Fill {s.fill:.4f} m2   Cut {s.cut:.4f} m2   Net {s.net:.4f} m2',.62)
    text(ms,x,y-3,'1 unit = 1 m; equal X/Y scales. Green = pre; red = post.',.5)
    text(ms,x,y-4.2,f'Mean RL fill/cut {s.mean_fill:.6f} / {s.mean_cut:.6f}; bounded {s.fill:.6f} / {s.cut:.6f} m2',.43)
    for kind,polys in [('FILL',s.fill_polygons),('CUT',s.cut_polygons)]:
        for j,p in enumerate(polys,1):
            pts=trans(p)
            boundary=ms.add_lwpolyline(pts,close=True,dxfattribs={'layer':kind+'_BOUNDARY'})
            boundary.set_xdata('EARTHWORK',[(1000,kind),(1040,s.chainage),(1040,poly_area(p))])
            hatch=ms.add_hatch(color=256,dxfattribs={'layer':kind+'_HATCH'})
            hatch.paths.add_polyline_path(pts,is_closed=True)
    for kind,pts in [('PRE_WORK',s.pre),('POST_WORK',s.post)]:
        ms.add_lwpolyline(trans(pts),dxfattribs={'layer':kind})
    axis_y=oy+math.floor(lo)-1
    ms.add_line((x,axis_y),(x+maxx-minx,axis_y),dxfattribs={'layer':'GRID'})
    step=max(1,math.ceil((maxx-minx)/12/5)*5)
    for off in range(math.ceil(minx/step)*step,math.floor(maxx/step)*step+1,step):
        ms.add_line((off+ox,axis_y),(off+ox,axis_y+.25),dxfattribs={'layer':'GRID'})
        text(ms,off+ox-.5,axis_y-1,f'{off:g}',.4)
    text(ms,x,axis_y-2.4,'Local offsets (m); RL values are listed in the coordinate table.',.45)
    ty=y-5; tx=x+maxx-minx+5
    rows=[]
    for i in range(max(len(s.pre),len(s.post))):
        pre=s.pre[i] if i<len(s.pre) else None; post=s.post[i] if i<len(s.post) else None
        rows.append([str(i+1)]+([f'{v:.3f}' for v in pre] if pre else ['',''])+([f'{v:.3f}' for v in post] if post else ['','']))
    right,bottom=table(ms,tx,ty,['Pt','Pre X','Pre RL','Post X','Post RL'],rows,[4,9,9,9,9],h=1.4,th=.48)
    bottom=min(bottom,axis_y-3)
    text(ms,x,bottom-2,f'CAD placement shift: X {ox:+.3f} m, Y {oy:+.3f} m. Source offsets/RLs above.',.47)
    text(ms,x,bottom-3.2,'Bounded area = abs(sum(Xi*Yi+1 - Xi+1*Yi))/2; split at every crossing.',.47)
    text(ms,x,bottom-4.4,'Boundary polylines are closed; Properties > Area gives m2. Hatches are non-associative.',.47)
    return right,bottom-6

def write_csv(path,headers,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f); writer.writerow(headers); writer.writerows(rows)

def save_dxf(survey,vol,path,individual=False):
    doc=new_doc(); ms=doc.modelspace(); y=0
    text(ms,0,y,'EARTHWORK / PRE-WORK AND POST-WORK',1.6)
    text(ms,0,3,ATTRIBUTION,.65)
    text(ms,0,-3,f'Source: {survey.source}',.7)
    text(ms,0,-5,f'Mode: {survey.mode}',.7)
    text(ms,0,-7,f'Chainage {vol["start"]:.3f} to {vol["end"]:.3f} m; included length {vol["length"]:.3f} m',.7)
    text(ms,0,-9,f'Fill {vol["fill"]:,.3f} m3   Cut {vol["cut"]:,.3f} m3   Net {vol["net"]:,.3f} m3',.85)
    text(ms,0,-11,'METHOD: Vfill = (Afill,1 + Afill,2) / 2 x L; Vcut likewise; Vnet = Vfill - Vcut.',.62)
    text(ms,0,-12.5,'End areas at clipped limits are linearly interpolated. Excluded intervals contribute zero volume.',.62)
    text(ms,0,-14,'All model geometry is 1:1 in metres, without vertical exaggeration. No bulking/settlement factors.',.62)
    text(ms,0,-15.5,'Reference areas below RL 0 are signed integrals, not physical cut/fill quantities.',.62)
    text(ms,0,-17,'Tables are editable CAD lines and text, not live formulas. Regenerate after changing Excel data.',.62)
    text(ms,0,-18.5,'Outside survey: '+('nearest end section held constant (explicit assumption).' if vol['extend'] else 'no extrapolation allowed.'),.62)
    y=-22
    # Repeat small table headers for readable result panels.
    for offset in range(0,len(survey.sections),20):
        subset=survey.sections[offset:offset+20]
        text(ms,0,y,'SECTIONAL AREAS: MEAN RL vs COORDINATE BOUNDARY (m2)',.75); y-=2
        rows=[[f'{s.chainage:.3f}']+[f'{v:.6f}' for v in [s.mean_fill,s.mean_cut,s.fill,s.cut,s.net,max(abs(s.mean_fill-s.fill),abs(s.mean_cut-s.cut))]] for s in subset]
        _,y=table(ms,0,y,['Ch (m)','MRL fill','MRL cut','Bound fill','Bound cut','Net','Max diff'],rows,[15,18,18,18,18,18,18],h=1.8,th=.55)
        y-=4
    for offset in range(0,len(vol['rows']),18):
        text(ms,0,y,'MEAN-AREA VOLUME SCHEDULE',.85); y-=2
        rows=[]
        for r in vol['rows'][offset:offset+18]:
            rows.append([f'{r[k]:.3f}' for k in ['start','end','length','mean_fill','mean_cut','fill_volume','cut_volume','net_volume']]+['EXCLUDED' if r['excluded'] else 'EXTENDED' if r['extended'] else 'INCLUDED'])
        _,y=table(ms,0,y,['From m','To m','L m','Mean fill','Mean cut','Fill m3','Cut m3','Net m3','Status'],rows,[13,13,12,14,14,17,17,17,16],h=1.8,th=.55)
        y-=4
    text(ms,0,y,f'TOTAL: FILL {vol["fill"]:.3f} m3 / CUT {vol["cut"]:.3f} m3 / NET {vol["net"]:.3f} m3',.85); y-=3
    for line in survey.warnings:
        # Wrap ordinary text into short CAD lines.
        import textwrap
        for part in textwrap.wrap(line,135): text(ms,0,y,part,.55); y-=1.3
    maxy=0.; miny=y
    # Sections are placed to the right of the calculation schedules.
    for i,s in enumerate(survey.sections):
        _,b=section_drawing(doc,s,155, miny if i else 0,i+1)
        miny=b-4
    doc.set_modelspace_vport(height=240,center=(125,-100))
    audit=doc.audit()
    if audit.has_errors: raise InputError('DXF failed its structural audit.')
    doc.saveas(path)
    if individual:
        folder=path.parent/'Individual_sections'; folder.mkdir(exist_ok=True)
        for i,s in enumerate(survey.sections):
            d=new_doc(); right,bottom=section_drawing(d,s,0,0,i+1)
            d.set_modelspace_vport(height=max(35,-bottom+5),center=(right/2,bottom/2))
            d.saveas(folder/f'XS_{i+1:03d}_Ch_{s.chainage:.3f}m.dxf')

def discover_converter():
    config=(Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent)/'converter_path.txt'
    candidates=[]
    if config.exists(): candidates.append(config.read_text(encoding='utf-8-sig').strip())
    for base in [Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'ODA',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Open Design Alliance']:
        if base.exists(): candidates.extend(str(p) for p in base.glob('**/ODAFileConverter.exe'))
    return next((str(Path(p)) for p in candidates if p and Path(p).is_file()),'')

def geometry_signature(doc):
    entities=list(doc.modelspace())
    polys=[(e.dxf.layer,bool(e.closed),[(float(x),float(y)) for x,y,*_ in e.get_points()]) for e in entities if e.dxftype()=='LWPOLYLINE']
    hatches=[(e.dxf.layer,[list(p.vertices) for p in e.paths]) for e in entities if e.dxftype()=='HATCH']
    labels=[e.dxf.text for e in entities if e.dxftype()=='TEXT']
    return doc.units,polys,hatches,labels

def convert_dwg(dxf,converter):
    if not converter or not Path(converter).is_file(): raise InputError('DWG export needs ODA File Converter. Select its ODAFileConverter.exe in the app. DXF export works without it.')
    # Workspaces under output avoid permissions and prevent unrelated drawings being converted.
    import uuid
    work=dxf.parent/('.cad_conversion_'+uuid.uuid4().hex[:12]); work.mkdir()
    incoming=work/'input'; dwgdir=work/'dwg'; checkdir=work/'check'
    for p in [incoming,dwgdir,checkdir]: p.mkdir()
    import shutil
    shutil.copy2(dxf,incoming/dxf.name)
    def run(src,dst,fmt,pattern):
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        proc=subprocess.run([str(converter),str(src.resolve()),str(dst.resolve()),'ACAD2018',fmt,'0','1',pattern],capture_output=True,text=True,timeout=180,creationflags=flags)
        if proc.returncode: raise InputError(f'ODA converter returned {proc.returncode}. DXF output is still available.')
    run(incoming,dwgdir,'DWG','*.dxf')
    dwg=dwgdir/(dxf.stem+'.dwg')
    if not dwg.exists() or dwg.read_bytes()[:6]!=b'AC1032':
        errs=' '.join(p.read_text(errors='replace') for p in dwgdir.glob('*.err'))
        raise InputError('DWG conversion failed. '+errs[:500])
    run(dwgdir,checkdir,'DXF','*.dwg')
    back=checkdir/dxf.name
    if not back.exists(): raise InputError('DWG was created but reopening it for verification failed.')
    original=ezdxf.readfile(dxf); checked=ezdxf.readfile(back)
    if checked.audit().has_errors: raise InputError('Converted DWG failed the round-trip structural check.')
    a,b=geometry_signature(original),geometry_signature(checked)
    def close(u,v):
        if isinstance(u,(tuple,list)):
            return isinstance(v,(tuple,list)) and len(u)==len(v) and all(close(x,y) for x,y in zip(u,v))
        if isinstance(u,(float,int)): return abs(u-v)<1e-7
        return u==v
    if not close(a,b): raise InputError('Converted DWG geometry does not match the DXF; output withheld.')
    target=dxf.with_suffix('.dwg'); shutil.copy2(dwg,target)
    # Leave small verification files inside the run directory for traceability.
    return target

def export(survey,vol,folder,fmt='DWG',converter='',individual=False,profile=None):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    dxf=folder/'Earthwork_sections_and_quantities.dxf'
    save_dxf(survey,vol,dxf,individual)
    write_csv(folder/'Section_areas.csv',['Chainage_m','Mean_RL_fill_m2','Mean_RL_cut_m2','Mean_RL_net_m2','Bounded_fill_m2','Bounded_cut_m2','Bounded_net_m2','Fill_difference_m2','Cut_difference_m2','Workbook_cached_area_m2'],[[s.chainage,s.mean_fill,s.mean_cut,s.mean_net,s.fill,s.cut,s.net,s.fill-s.mean_fill,s.cut-s.mean_cut,s.cached_net] for s in survey.sections])
    write_csv(folder/'Bounded_polygon_vertices.csv',['Chainage_m','Kind','Polygon_ID','Vertex','Offset_m','RL_m','Polygon_area_m2'],[[s.chainage,kind,j,i,x,y,poly_area(p)] for s in survey.sections for kind,polys in [('Fill',s.fill_polygons),('Cut',s.cut_polygons)] for j,p in enumerate(polys,1) for i,(x,y) in enumerate(p,1)])
    from profile_export import export_profile
    lp=export_profile(survey,profile,folder)
    keys=list(vol['rows'][0])
    write_csv(folder/'Mean_area_volumes.csv',keys,[[r[k] for k in keys] for r in vol['rows']])
    write_csv(folder/'Source_coordinates.csv',['Chainage_m','Profile','Offset_m','RL_m'],[[s.chainage,kind,x,y] for s in survey.sections for kind,pts in [('Pre',s.pre),('Post',s.post)] for x,y in pts])
    (folder/'Calculation_details.json').write_text(json.dumps(dict(source=survey.source,mode=survey.mode,warnings=survey.warnings,sections=[asdict(s) for s in survey.sections],volume=vol),indent=2),encoding='utf-8')
    result=dxf
    if fmt=='DWG':
        result=convert_dwg(dxf,converter)
        convert_dwg(lp,converter)
        if individual:
            for p in (folder/'Individual_sections').glob('*.dxf'): convert_dwg(p,converter)
    (folder/'Read_me.txt').write_text(f'''EARTHWORK EXPORT
{ATTRIBUTION}
Source: {survey.source}
Mode: {survey.mode}
Model units: metres, scale 1:1 on both axes. Drawing units are metres; areas are m2 and volumes m3.
Volume: average end area, separately for fill and cut. Net = fill - cut.
Section_areas.csv compares independent Mean RL trapezoidal strips with closed-coordinate polygon (shoelace) areas. They should agree for the same straight-segment boundaries.
Coordinate method is calculated by the app, not by running AutoCAD. Native closed polylines allow AREA > Object checking.
Long_profile.dxf contains chainage/RL panels at 20x vertical exaggeration; never measure sectional areas from this longitudinal display.
Long_profile.csv contains unexaggerated RL values. Feature_offsets.csv controls centre/toe/bank selections.
Suggested feature offsets and unconfirmed side orientation are PROVISIONAL; review them in the Long profile tab. Missing or ambiguous RLs are gaps.
The long profile includes all imported chainages; volume clipping/exclusions do not remove survey stations from it.
Total fill: {vol['fill']:.6f} m3
Total cut: {vol['cut']:.6f} m3
Total net: {vol['net']:.6f} m3
Included chainage length: {vol['length']:.3f} m
Excluded intervals: {vol['excluded']}
Nearest-section extension enabled: {vol['extend']}
Source coordinates and detailed calculation schedules are included.
CAD section placements are translations only; source local offsets/RLs appear in the coordinate tables.
Use Properties or AREA > Object on FILL_BOUNDARY / CUT_BOUNDARY closed polylines. Sum all polygons in a section.
Hatches are non-associative. CAD tables are editable lines/text and do not recalculate when geometry is edited; rerun the app after source changes.
Reference pre/post areas are signed integrals relative to RL 0; use the separately calculated fill/cut for quantities.
No bulking, shrinkage, settlement or stripping adjustment is included.
The result is valid only for the supplied profiles and selected source mode. Excel formulas are not recalculated by this app.
DWG files, when requested, are checked by a geometry-preserving DXF round trip. Native AutoCAD UI testing is not performed.
''',encoding='utf-8')
    return result
