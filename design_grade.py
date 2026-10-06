"""Independent design RL control, with explicit reach gradients and gaps."""
import csv,math
from engine import InputError

class DesignGrade:
    def __init__(self,segments=(),basis='No design levels supplied'):
        self.basis=basis;self.set(segments)

    def set(self,segments):
        values=[]
        for row in segments:
            if len(row)!=4:raise InputError('Each design row needs Start_m, End_m, Start_RL_m, End_RL_m.')
            a,b,y,z=map(float,row)
            if not all(math.isfinite(v) for v in (a,b,y,z)) or b<=a:raise InputError('Design rows need finite values and End_m greater than Start_m.')
            values.append((a,b,y,z))
        values.sort()
        for left,right in zip(values,values[1:]):
            if right[0]<left[1]-1e-7:raise InputError('Design reaches must not overlap.')
        self.reaches=values

    def at(self,ch):
        # At a shared endpoint, use the next reach's specified starting RL.
        for a,b,y,z in reversed(self.reaches):
            if a-1e-7<=ch<=b+1e-7:return y+(z-y)*(ch-a)/(b-a)
        return None

    def runs(self,start,end):
        for a,b,y,z in self.reaches:
            lo=max(a,start);hi=min(b,end)
            if hi>=lo:
                f=lambda x:y+(z-y)*(x-a)/(b-a)
                yield [(lo,f(lo)),(hi,f(hi))]

    def warnings(self):
        messages=[]
        for l,r in zip(self.reaches,self.reaches[1:]):
            if abs(l[1]-r[0])<1e-7 and abs(l[3]-r[2])>1e-7:
                messages.append(f'Ch {r[0]:g} m: design RL changes {l[3]:.6f} to {r[2]:.6f}; source reset retained, not smoothed.')
        return messages

    def load(self,path):
        with open(path,encoding='utf-8-sig',newline='') as f:
            rows=[[r[k] for k in ['Start_m','End_m','Start_RL_m','End_RL_m']] for r in csv.DictReader(f)]
        self.set(rows);self.basis='User-imported design grade schedule'

    def save(self,path):
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['Start_m','End_m','Start_RL_m','End_RL_m','Signed_gradient_m_per_m','Gradient_1_in_N','Direction'])
            for a,b,y,z in self.reaches:
                g=(z-y)/(b-a);w.writerow([a,b,y,z,g,'' if g==0 else 1/abs(g),'Level' if g==0 else 'Rising with chainage' if g>0 else 'Falling with chainage'])

def initial_grade(survey,kind):
    if getattr(survey,'design_reaches',None):
        rr=sorted(survey.design_reaches);a,b,y,z=rr[0];g=(z-y)/(b-a)
        if all(abs((v-u)/(e-s)-g)<1e-10 for s,e,u,v in rr) and all(abs(l[1]-r[0])<1e-6 for l,r in zip(rr,rr[1:])):
            end=rr[-1][1]
            return DesignGrade([(a,end,y,y+g*(end-a))],'Continuous gradient requested by user: first source RL and common Gradation (2) slope; intermediate RL resets removed from DESIGN line only.')
        return DesignGrade(survey.design_reaches,survey.design_basis)
    if kind=='Embankment':
        levels=[max(y for x,y in s.post) for s in survey.sections]
        if len(levels)>1 and max(levels)-min(levels)<1e-8:
            return DesignGrade([(survey.sections[0].chainage,survey.sections[-1].chainage,levels[0],levels[0])],f'Constant post crest RL {levels[0]:.3f} imported as design Top RL; verify design basis.')
    return DesignGrade()
