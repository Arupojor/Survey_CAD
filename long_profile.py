"""Explicit, reviewable feature selection for longitudinal profiles."""
from dataclasses import dataclass, asdict
import csv, math
from engine import interp, InputError, EPS

ATTRIBUTION='Built by Engr. Arup Chakraborty, Executive Engineer, BWDB'
SIDES=['Unconfirmed','C/S','R/S','Left bank','Right bank']

@dataclass
class Feature:
    chainage: float
    centre: float | None
    low: float | None
    high: float | None
    confirmed: bool=False
    basis: str='Suggested from profile geometry; verify offsets'

def suggest(s,kind):
    target=(max if kind=='Embankment' else min)(y for x,y in s.post)
    runs=[]; run=[]
    for p in s.post:
        if abs(p[1]-target)<1e-7: run.append(p)
        else:
            if run:runs.append(run)
            run=[]
    if run:runs.append(run)
    runs=[r for r in runs if len(r)>1 and r[-1][0]-r[0][0]>EPS]
    if len(runs)!=1:return Feature(s.chainage,None,None,None,False,'No unique flat crest/bed. Enter feature offsets.')
    crest=runs[0]; c=(crest[0][0]+crest[-1][0])/2
    if kind=='Embankment':
        before=[p for p in s.post if p[0]<crest[0][0]]
        after=[p for p in s.post if p[0]>crest[-1][0]]
        lo=before[-1][0] if before else None;hi=after[0][0] if after else None
        basis='Suggested: flat post crest midpoint; adjacent post vertices as toes. Verify.'
    else:
        left=[p for p in s.pre if p[0]<crest[0][0]];right=[p for p in s.pre if p[0]>crest[-1][0]]
        lo=max(left,key=lambda p:(p[1],p[0]))[0] if left else None
        hi=max(right,key=lambda p:(p[1],-p[0]))[0] if right else None
        basis='Suggested: flat post bed midpoint; highest pre RL on each side as bank candidates. Verify.'
    return Feature(s.chainage,c,lo,hi,False,basis)

def validate_feature(s,f):
    for name,x in [('centre',f.centre),('low',f.low),('high',f.high)]:
        if x is not None and (not math.isfinite(x) or x<s.pre[0][0] or x>s.pre[-1][0]):
            raise InputError(f'Ch {s.chainage:g}: {name} offset is outside the survey.')
    if f.low is not None and f.high is not None and f.low>=f.high:raise InputError('Low feature offset must be less than high feature offset.')
    if f.centre is not None:
        if f.low is not None and f.low>=f.centre:raise InputError('Low feature must be before the centreline.')
        if f.high is not None and f.high<=f.centre:raise InputError('High feature must be after the centreline.')
    return f

def sample(pts,x):
    if x is None:return None
    if abs(interp(pts,x)-interp(pts,x,'left'))>1e-8:return None
    return interp(pts,x)

class LongProfile:
    def __init__(self,survey,kind=None,low_side='Unconfirmed'):
        self.kind=kind or ('Embankment' if sum(s.net for s in survey.sections)>=0 else 'River / Khal')
        self.low_side=low_side
        self.features={s.chainage:suggest(s,self.kind) for s in survey.sections}
        from design_grade import initial_grade
        self.design=initial_grade(survey,self.kind)

    def names(self):
        pairs={'C/S':('C/S toe','R/S toe'),'R/S':('R/S toe','C/S toe'),'Left bank':('Left bank','Right bank'),'Right bank':('Right bank','Left bank')}
        if self.kind=='Embankment' and self.low_side in ('Left bank','Right bank'):raise InputError('Select C/S or R/S for embankment orientation.')
        if self.kind!='Embankment' and self.low_side in ('C/S','R/S'):raise InputError('Select Left bank or Right bank for khal orientation.')
        return pairs.get(self.low_side,('Low-offset '+('toe' if self.kind=='Embankment' else 'bank'),'High-offset '+('toe' if self.kind=='Embankment' else 'bank')))

    def rows(self,survey):
        rows=[]
        for s in survey.sections:
            f=validate_feature(s,self.features[s.chainage]);r=asdict(f)
            for feature in ['centre','low','high']:
                for profile in ['pre','post']:r[profile+'_'+feature]=sample(getattr(s,profile),getattr(f,feature))
            r['design']=self.design.at(s.chainage)
            missing=any(r[k] is None for k in SERIES if k!='design')
            r['status']='Incomplete / vertical RL ambiguity' if missing else 'Reviewed offsets' if f.confirmed else 'PROVISIONAL offsets'
            if self.low_side=='Unconfirmed':r['status']+='; orientation unconfirmed'
            rows.append(r)
        return rows

    def labels(self):
        lo,hi=self.names()
        return ['Pre centreline','Post centreline','Pre '+lo,'Post '+lo,'Pre '+hi,'Post '+hi,'Design Top RL' if self.kind=='Embankment' else 'Design khal bed RL']

    def load(self,path,survey):
        proposed={}; known={round(s.chainage,8):s for s in survey.sections}
        with open(path,encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                ch=float(r['Chainage_m']);key=round(ch,8)
                if key not in known:raise InputError(f'Feature mapping chainage {ch:g} is absent from the survey.')
                if key in proposed:raise InputError(f'Duplicate feature mapping chainage {ch:g}.')
                def v(k):return None if not r.get(k,'').strip() else float(r[k])
                s=known[key];feat=Feature(s.chainage,v('Centre_offset_m'),v('Low_offset_m'),v('High_offset_m'),r.get('Confirmed','').lower() in ['true','1','yes'],'Imported feature mapping')
                proposed[key]=validate_feature(s,feat)
        if set(proposed)!=set(known):raise InputError('Feature mapping must contain every survey chainage exactly once.')
        self.features={f.chainage:f for f in proposed.values()}

    def save(self,path):
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['Chainage_m','Centre_offset_m','Low_offset_m','High_offset_m','Confirmed'])
            for p in self.features.values():w.writerow([p.chainage,p.centre,p.low,p.high,p.confirmed])

SERIES=['pre_centre','post_centre','pre_low','post_low','pre_high','post_high','design']
COLORS=['#237a45','#c73730','#3b62b5','#7e3fa2','#ac7415','#127d8b','#202020']

def profile_segments(model,rows,key):
    if key=='design':yield from model.design.runs(rows[0]['chainage'],rows[-1]['chainage'])
    else:yield from segments(rows,key)

def segments(rows,key):
    run=[]
    for r in rows:
        if r[key] is None:
            if run:yield run
            run=[]
        else:run.append((r['chainage'],r[key]))
    if run:yield run
