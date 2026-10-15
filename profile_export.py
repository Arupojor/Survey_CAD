from pathlib import Path
import csv, math, html
from long_profile import LongProfile,ATTRIBUTION,SERIES,COLORS,profile_segments

def export_profile(survey,profile,folder):
    from cad_export import new_doc,text,table,write_csv
    profile=profile or LongProfile(survey);rows=profile.rows(survey);labels=profile.labels()
    profile.save(folder/'Feature_offsets.csv')
    profile.design.save(folder/'Design_grade.csv')
    (folder/'Design_basis.txt').write_text(profile.design.basis+'\n'+'\n'.join(profile.design.warnings())+'\nDesign line is independent of pre/post work profiles. Changing the grade does not recalculate surveyed earthwork quantities.',encoding='utf-8')
    write_csv(folder/'Long_profile.csv',['Chainage_m','Centre_offset_m','Low_offset_m','High_offset_m']+[s+' RL_m' for s in labels]+['Status','Basis'],[[r['chainage'],r['centre'],r['low'],r['high']]+[r[k] for k in SERIES]+[r['status'],r['basis']] for r in rows])
    doc=new_doc();ms=doc.modelspace()
    for i,key in enumerate(SERIES):doc.layers.new('LP_'+key.upper(),dxfattribs={'color':[3,1,5,6,30,4,7][i],'linetype':'DASHED' if key=='design' else 'CONTINUOUS'})
    y=0.;lo_ch=rows[0]['chainage'];hi_ch=rows[-1]['chainage']
    # Overlap panel ends by one source station. Do not interpolate missing station data.
    groups=[];run=[]
    for r in rows:
        if run and r['chainage']-run[0]['chainage']>1000 and len(run)>1:
            groups.append(run);run=[run[-1]]
        run.append(r)
    if run:groups.append(run)
    for panel,rr in enumerate(groups,1):
        xs=[r['chainage'] for r in rr];ys=[r[k] for r in rr for k in SERIES if r[k] is not None]
        ys += [rl for run in profile.design.runs(xs[0],xs[-1]) for _,rl in run]
        datum=math.floor(min(ys)-1) if ys else 0;top=math.ceil(max(ys)+1) if ys else 5
        width=max(600,xs[-1]-xs[0]);plot_h=max(60,(top-datum)*20)
        text(ms,0,y,f'LONG PROFILE {panel} / {profile.kind} / CH {xs[0]:.3f} - {xs[-1]:.3f} m',10)
        text(ms,0,y-18,ATTRIBUTION,5)
        text(ms,0,y-31,'PROVISIONAL where offsets/orientation are unconfirmed. All imported chainages; volume limits not applied.',5)
        text(ms,0,y-43,f'Horizontal 1 unit = 1 m; vertical exaggeration 20x; datum RL {datum:g} m. Source datum retained.',5)
        for i,(label,key) in enumerate(zip(labels,SERIES)):text(ms,(i%3)*width/3,y-58-(i//3)*12,label,5,'LP_'+key.upper())
        base=y-95-plot_h
        for level in range(datum,top+1):
            yy=base+(level-datum)*20;ms.add_line((0,yy),(width,yy),dxfattribs={'layer':'GRID'});text(ms,-42,yy-2,f'{level:g}',5)
        for j in range(6):
            x=(xs[-1]-xs[0])*j/5;ms.add_line((x,base),(x,base+plot_h),dxfattribs={'layer':'GRID'});text(ms,x-10,base-13,f'{xs[0]+x:.1f}',5)
        for key in SERIES:
            for run in profile_segments(profile,rr,key):
                points=[(ch-xs[0],base+(rl-datum)*20) for ch,rl in run]
                if len(points)>1:ms.add_lwpolyline(points,dxfattribs={'layer':'LP_'+key.upper()})
                for p in points:ms.add_circle(p,1.5,dxfattribs={'layer':'LP_'+key.upper()})
        text(ms,0,base-27,'CHAINAGE (m). Missing or ambiguous feature levels are gaps; they are not extrapolated.',5)
        vals=[[f'{r["chainage"]:.3f}']+['n/a' if r[k] is None else f'{r[k]:.3f}' for k in SERIES] for r in rr]
        _,bottom=table(ms,0,base-42,['Ch m','Pre CL','Post CL','Pre low','Post low','Pre high','Post high','Design RL'],vals,[85]*8,h=14,th=5)
        yy=bottom-16
        for a,b,rl,z in profile.design.reaches:
            if b<xs[0] or a>xs[-1]:continue
            g=(z-rl)/(b-a);label='LEVEL' if abs(g)<1e-15 else f'{"RISE" if g>0 else "FALL"} 1 in {1/abs(g):.3f}'
            text(ms,0,yy,f'DESIGN: Ch {a:.3f}-{b:.3f} m; RL {rl:.6f} to {z:.6f}; {label} as chainage increases.',5);yy-=14
        y=yy-50
    doc.set_modelspace_vport(height=max(300,-y),center=(450,y/2));doc.saveas(folder/'Long_profile.dxf')
    # Portable browser preview: source values, independently fitted display axes.
    ys=[r[k] for r in rows for k in SERIES if r[k] is not None]+[rl for run in profile.design.runs(lo_ch,hi_ch) for _,rl in run];lo=min(ys)-.4 if ys else 0;hi=max(ys)+.4 if ys else 1
    pt=lambda x,y:(80+(x-lo_ch)/max(1,hi_ch-lo_ch)*1140,480-(y-lo)/(hi-lo)*400)
    shapes=[]
    for i in range(6):
        x=lo_ch+(hi_ch-lo_ch)*i/5;y=lo+(hi-lo)*i/5;px,_=pt(x,lo);_,py=pt(lo_ch,y)
        shapes += [f'<path d="M{px},80 V480 M80,{py} H1220" stroke="#d9e1e8" fill="none"/>',f'<text x="{px}" y="505" text-anchor="middle">{x:.0f}</text>',f'<text x="70" y="{py+5}" text-anchor="end">{y:.2f}</text>']
    for key,col in zip(SERIES,COLORS):
        for run in profile_segments(profile,rows,key):
            points=[pt(x,y) for x,y in run]
            shapes.append('<polyline '+('stroke-dasharray="8 4" ' if key=='design' else '')+'fill="none" stroke="'+col+'" stroke-width="2" points="'+' '.join(f'{x},{y}' for x,y in points)+'"/>')
            shapes.extend(f'<circle cx="{x}" cy="{y}" r="3" fill="{col}"/>' for x,y in points)
    legend=' '.join(f'<span style="color:{col};margin-right:22px">{html.escape(label)}</span>' for label,col in zip(labels,COLORS))
    head=['Chainage m','Centre X','Low X','High X']+labels+['Status']
    tr=[]
    for r in rows:
        v=[r[k] for k in ['chainage','centre','low','high']+SERIES]+[r['status']]
        tr.append('<tr>'+''.join('<td>'+html.escape('n/a' if x is None else f'{x:.3f}' if isinstance(x,(int,float)) else x)+'</td>' for x in v)+'</tr>')
    out='<!doctype html><meta charset="utf-8"><title>Long profile</title><style>body{font:15px Segoe UI,Arial;margin:30px;color:#20344a}svg{width:100%;max-width:1300px}table{border-collapse:collapse}td,th{padding:7px;border:1px solid #ccd6df;text-align:right}th{background:#edf2f6}h1{margin-bottom:6px}@media print{body{margin:10px}table{font-size:10px}}</style>'
    out+=f'<h1>{html.escape(profile.kind)} longitudinal profile</h1><p>{ATTRIBUTION}</p><p>Source: {html.escape(survey.source)}</p><p>PROVISIONAL where feature offsets or orientation are unconfirmed. Review Feature_offsets.csv or edit in the app. Missing values remain gaps. Display axes fitted independently.</p><p>{legend}</p>'
    out+='<p>Design basis: '+html.escape(profile.design.basis)+'</p>'
    for a,b,y,z in profile.design.reaches:
        g=(z-y)/(b-a);slope='Level' if abs(g)<1e-15 else f'{"Rise" if g>0 else "Fall"} 1 in {1/abs(g):.3f} toward increasing chainage'
        out+=f'<p>Design Ch {a:g} to {b:g} m: RL {y:.6f} to {z:.6f} m. {slope}.</p>'
    out+='<svg viewBox="0 0 1300 540" role="img" aria-label="Longitudinal reduced levels by chainage"><text x="80" y="40">RL (m, source datum)</text>'+''.join(shapes)+'<text x="600" y="535">Chainage (m)</text></svg>'
    out+='<table><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in head)+'</tr>'+''.join(tr)+'</table>'
    (folder/'Long_profile.html').write_text(out,encoding='utf-8')
    return folder/'Long_profile.dxf'
