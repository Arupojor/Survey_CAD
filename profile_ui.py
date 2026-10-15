import tkinter as tk
import math
from tkinter import ttk,filedialog,messagebox
from long_profile import LongProfile,Feature,SERIES,COLORS,SIDES,profile_segments,validate_feature

class ProfilePanel:
    def __init__(self,app):
        self.app=app;self.model=None
        self.frame=ttk.Frame(app.notebook,padding=8);app.notebook.add(self.frame,text='Long profile')
        controls=ttk.Frame(self.frame);controls.pack(fill='x')
        self.kind=tk.StringVar(value='Embankment');self.side=tk.StringVar(value='Unconfirmed')
        ttk.Label(controls,text='Work type').pack(side='left')
        kind=ttk.Combobox(controls,textvariable=self.kind,values=['Embankment','River / Khal'],state='readonly',width=16);kind.pack(side='left',padx=5);kind.bind('<<ComboboxSelected>>',self.change_kind)
        ttk.Label(controls,text='Lower-offset side').pack(side='left')
        self.sidebox=ttk.Combobox(controls,textvariable=self.side,values=SIDES,state='readonly',width=15);self.sidebox.pack(side='left',padx=5);self.sidebox.bind('<<ComboboxSelected>>',lambda e:self.change_side())
        self.note=tk.StringVar(value='Analyze a survey to derive its long profile.')
        ttk.Label(self.frame,textvariable=self.note,wraplength=820,foreground='#875a16').pack(fill='x',pady=6)
        self.canvas=tk.Canvas(self.frame,bg='white',height=275,highlightthickness=1,highlightbackground='#d4dfe7');self.canvas.pack(fill='both',expand=True);self.canvas.bind('<Configure>',lambda e:self.draw())
        self.legend=ttk.Frame(self.frame);self.legend.pack(fill='x')
        buttons=ttk.Frame(self.frame);buttons.pack(fill='x',pady=5)
        for label,fn in [('Edit selected offsets',self.edit),('Import offset mapping',self.load),('Save offset mapping',self.save)]:ttk.Button(buttons,text=label,command=fn).pack(side='left',padx=(0,5))
        ttk.Button(buttons,text='Design RL / gradient',command=self.edit_design).pack(side='left')
        self.tree=app.make_tree(self.frame,['Ch m','Centre X','Low X','High X','Pre CL RL','Post CL RL','Design RL','Status'],[90,90,90,90,100,100,100,260]);self.tree.bind('<Double-1>',lambda e:self.edit())

    def reset(self,survey):
        self.model=LongProfile(survey);self.kind.set(self.model.kind);self.side.set('Unconfirmed');self.refresh()

    def change_kind(self,event=None):
        if not self.app.survey:return
        if self.model and (any(f.confirmed for f in self.model.features.values()) or self.model.design.reaches):
            if not messagebox.askyesno('Replace profile settings?','Changing work type replaces feature offsets and design settings with the source defaults.'):
                self.kind.set(self.model.kind);return
        self.model=LongProfile(self.app.survey,self.kind.get());self.side.set('Unconfirmed');self.refresh()

    def change_side(self):
        if self.model:self.model.low_side=self.side.get();self.refresh()

    def refresh(self):
        if not self.model:return
        self.sidebox['values']=['Unconfirmed']+(['C/S','R/S'] if self.model.kind=='Embankment' else ['Left bank','Right bank'])
        rows=self.model.rows(self.app.survey)
        self.note.set('Separate design line: '+self.model.design.basis+' Feature offsets remain provisional until reviewed. Design changes do not alter surveyed quantities.')
        self.tree.delete(*self.tree.get_children())
        for i,r in enumerate(rows):
            vals=[r[k] for k in ['chainage','centre','low','high','pre_centre','post_centre','design']]
            self.tree.insert('','end',iid=str(i),values=[f'{v:.3f}' if v is not None else 'n/a' for v in vals]+[r['status']])
        for child in self.legend.winfo_children():child.destroy()
        for i,(label,col) in enumerate(zip(self.model.labels(),COLORS)):ttk.Label(self.legend,text=label,foreground=col).grid(row=i//3,column=i%3,sticky='w',padx=8,pady=2)
        self.draw()

    def draw(self):
        c=self.canvas;c.delete('all')
        if not self.model or not self.app.survey:return
        rows=self.model.rows(self.app.survey);ys=[r[k] for r in rows for k in SERIES if r[k] is not None]
        ys += [rl for run in self.model.design.runs(rows[0]['chainage'],rows[-1]['chainage']) for _,rl in run]
        if not ys:c.create_text(20,30,anchor='nw',text='Enter centreline / toe / bank offsets to draw the long profile.');return
        minx=rows[0]['chainage'];maxx=rows[-1]['chainage'];lo=min(ys)-.3;hi=max(ys)+.3
        w=max(300,c.winfo_width());h=max(220,c.winfo_height())
        def xy(x,y):return 60+(x-minx)/max(1,maxx-minx)*(w-90),h-38-(y-lo)/(hi-lo)*(h-65)
        for i in range(6):
            x=minx+(maxx-minx)*i/5;px,_=xy(x,lo);c.create_line(px,25,px,h-38,fill='#e3e8ed');c.create_text(px,h-20,text=f'{x:.0f}',fill='#526478')
            y=lo+(hi-lo)*i/5;_,py=xy(minx,y);c.create_line(60,py,w-30,py,fill='#e3e8ed');c.create_text(54,py,text=f'{y:.2f}',anchor='e',fill='#526478')
        for key,col in zip(SERIES,COLORS):
            for run in profile_segments(self.model,rows,key):
                pts=[xy(x,y) for x,y in run]
                if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill=col,width=2,dash=(8,4) if key=='design' else ())
                for x,y in pts:c.create_oval(x-2,y-2,x+2,y+2,fill=col,outline=col)
        c.create_text(60,12,anchor='w',text='RL (m, source datum)  |  Chainage (m)  |  Display axes fitted independently',fill='#526478')

    def edit(self):
        if not self.model:return
        selected=self.tree.selection()
        if not selected:return
        s=self.app.survey.sections[int(selected[0])];f=self.model.features[s.chainage]
        win=tk.Toplevel(self.frame);win.title(f'Feature offsets - Ch {s.chainage:g} m');win.transient(self.app.root)
        ttk.Label(win,text=f'Offsets in metres, within {s.pre[0][0]:g} to {s.pre[-1][0]:g}. Blank = unavailable.').grid(row=0,column=0,columnspan=2,padx=15,pady=10)
        vars=[]
        for i,(name,value) in enumerate(zip(['Centreline','Lower-offset toe / bank','Higher-offset toe / bank'],[f.centre,f.low,f.high]),1):
            v=tk.StringVar(value='' if value is None else str(value));vars.append(v)
            ttk.Label(win,text=name).grid(row=i,column=0,padx=15,pady=5,sticky='w');ttk.Entry(win,textvariable=v).grid(row=i,column=1,padx=15,pady=5)
        confirmed=tk.BooleanVar(value=f.confirmed);ttk.Checkbutton(win,text='I have reviewed these feature offsets',variable=confirmed).grid(row=4,column=0,columnspan=2,padx=15,pady=8)
        ttk.Label(win,text=f.basis,wraplength=470).grid(row=5,column=0,columnspan=2,padx=15,pady=5)
        def save():
            try:
                vals=[None if not v.get().strip() else float(v.get()) for v in vars]
                self.model.features[s.chainage]=validate_feature(s,Feature(s.chainage,*vals,confirmed.get(),'User-edited feature offsets'))
                self.refresh();win.destroy()
            except ValueError as e:messagebox.showerror('Check offsets',str(e),parent=win)
        ttk.Button(win,text='Save offsets',command=save).grid(row=6,column=1,padx=15,pady=12)

    def edit_design(self):
        if not self.model:return
        from design_grade import DesignGrade
        win=tk.Toplevel(self.frame);win.title('Design Top RL / khal bed gradient');win.transient(self.app.root)
        ttk.Label(win,text='Design only: does not replace pre/post surveys or their area/volume calculations.',wraplength=680).grid(row=0,column=0,columnspan=4,padx=14,pady=10)
        ttk.Label(win,text='Reach rows: Start_m, End_m, Start_RL_m, End_RL_m. Blank = no design line.').grid(row=1,column=0,columnspan=4,padx=14)
        editor=tk.Text(win,width=78,height=9);editor.grid(row=2,column=0,columnspan=4,padx=14,pady=8)
        editor.insert('1.0','\n'.join(', '.join(f'{v:.9g}' for v in r) for r in self.model.design.reaches))
        ttk.Label(win,text='One continuous grade calculator (replaces reach rows):').grid(row=3,column=0,columnspan=4,padx=14,pady=8,sticky='w')
        rr=self.model.design.reaches
        start=rr[0][0] if rr else self.app.survey.sections[0].chainage
        end=rr[-1][1] if rr else self.app.survey.sections[-1].chainage
        rl=rr[0][2] if rr else ''
        g=(rr[0][3]-rr[0][2])/(rr[0][1]-rr[0][0]) if rr else 0
        vals=[]
        for i,(label,v) in enumerate(zip(['Start chainage m','End chainage m','Start / Top RL m','Gradient 1 in N'],[start,end,rl,'' if abs(g)<1e-15 else f'{1/abs(g):.9g}'])):
            ttk.Label(win,text=label).grid(row=4,column=i,padx=8);var=tk.StringVar(value=v);vals.append(var);ttk.Entry(win,textvariable=var,width=17).grid(row=5,column=i,padx=8)
        direction=tk.StringVar(value='Level' if abs(g)<1e-15 else 'Rise' if g>0 else 'Fall')
        ttk.Label(win,text='Direction as chainage increases').grid(row=6,column=0,columnspan=2,padx=10,pady=8)
        ttk.Combobox(win,textvariable=direction,values=['Level','Rise','Fall'],state='readonly',width=15).grid(row=6,column=2)
        def apply_calc():
            try:
                a,b,y=[float(v.get()) for v in vals[:3]]
                if direction.get()=='Level':slope=0.
                else:
                    n=float(vals[3].get())
                    if not math.isfinite(n) or n<=0:raise ValueError('Gradient denominator must be finite and positive.')
                    slope=(1 if direction.get()=='Rise' else -1)/n
                grade=DesignGrade([(a,b,y,y+slope*(b-a))])
                editor.delete('1.0','end');editor.insert('1.0',', '.join(f'{v:.12g}' for v in grade.reaches[0]))
            except ValueError as e:messagebox.showerror('Design gradient',str(e),parent=win)
        ttk.Button(win,text='Use continuous grade',command=apply_calc).grid(row=6,column=3,padx=8)
        info=tk.StringVar(value='');ttk.Label(win,textvariable=info,wraplength=680).grid(row=7,column=0,columnspan=4,padx=14,pady=6)
        def save():
            try:
                rows=[line.split(',') for line in editor.get('1.0','end').splitlines() if line.strip()]
                grade=DesignGrade(rows,'User-entered design RL / gradient schedule')
                self.model.design=grade;self.refresh();win.destroy()
            except ValueError as e:messagebox.showerror('Design grade',str(e),parent=win)
        def load_csv():
            p=filedialog.askopenfilename(filetypes=[('Design grade CSV','*.csv')],parent=win)
            if p:
                try:
                    grade=DesignGrade();grade.load(p);editor.delete('1.0','end');editor.insert('1.0','\n'.join(', '.join(f'{v:.12g}' for v in r) for r in grade.reaches));info.set('; '.join(grade.warnings()))
                except (ValueError,KeyError,OSError) as e:messagebox.showerror('Design grade',str(e),parent=win)
        ttk.Button(win,text='Import design grade CSV',command=load_csv).grid(row=8,column=0,columnspan=2,pady=12)
        ttk.Button(win,text='Save design line',command=save).grid(row=8,column=2,columnspan=2,pady=12)

    def save(self):
        if not self.model:return
        p=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='Feature_offsets.csv')
        if p:self.model.save(p)

    def load(self):
        if not self.model:return
        p=filedialog.askopenfilename(filetypes=[('Feature offsets','*.csv')])
        if p:
            try:self.model.load(p,self.app.survey);self.refresh()
            except (ValueError,KeyError,OSError) as e:messagebox.showerror('Feature mapping',str(e))
