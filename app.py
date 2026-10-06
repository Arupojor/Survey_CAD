"""Local Windows desktop application. Start normally for GUI or use --batch for CLI."""
import sys, os, json, math, threading, argparse, traceback
from pathlib import Path
BASE=Path(__file__).resolve().parent
if (BASE/'vendor').exists(): sys.path.insert(0,str(BASE/'vendor'))
# Source checkout can also use the locally prepared CAD library.
devlibs=BASE.parent.parent/'work'/'cad_libs'
if devlibs.exists(): sys.path.insert(0,str(devlibs))
from engine import load_survey, calculate_volumes, exclusions, InputError
from cad_export import export, discover_converter
from long_profile import ATTRIBUTION, LongProfile, SIDES

MODES={'1. Pre/post coordinates (Area sheet)':'Area','2. Design profile (XS Input / XS Areas)':'Design','Flat table (Excel or CSV)':'Flat'}

def main_gui(initial=None,test_hook=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    import openpyxl

    class App:
        def __init__(self,root):
            self.root=root; self.survey=None; self.vol=None; self.output=None; self.busy=False; self.dirty=True; self.loading=False; self.revision=0
            root.title('Survey CAD v3 | Design RL and gradients'); root.geometry('1400x950'); root.minsize(1120,800); root.configure(bg='#eef2f6')
            style=ttk.Style(); style.theme_use('clam')
            style.configure('.',font=('Segoe UI',10),background='#eef2f6',foreground='#20344a')
            style.configure('TButton',padding=(12,7),font=('Segoe UI',10))
            style.configure('Accent.TButton',background='#116b72',foreground='white',font=('Segoe UI Semibold',10))
            style.map('Accent.TButton',background=[('active','#16838b'),('disabled','#b9c9cb')])
            style.configure('Treeview',rowheight=26,font=('Segoe UI',10),background='white',fieldbackground='white')
            style.configure('Treeview.Heading',font=('Segoe UI Semibold',10),padding=6)
            style.configure('TNotebook.Tab',padding=(15,7))
            self.path=tk.StringVar(); self.mode=tk.StringVar(value=next(iter(MODES))); self.sheet=tk.StringVar()
            self.start=tk.StringVar(); self.end=tk.StringVar(); self.exclude=tk.StringVar(); self.extend=tk.BooleanVar()
            self.fmt=tk.StringVar(value='DWG'); self.converter=tk.StringVar(value=discover_converter()); self.individual=tk.BooleanVar()
            self.status=tk.StringVar(value='Choose an Excel workbook to begin. All processing stays on this computer.')
            header=tk.Frame(root,bg='#143442',height=86); header.pack(fill='x')
            tk.Label(header,text='EMBANKMENT & RIVER / KHAL',font=('Segoe UI Semibold',21),fg='white',bg='#143442').pack(anchor='w',padx=24,pady=(12,0))
            tk.Label(header,text=ATTRIBUTION,font=('Segoe UI',10),fg='white',bg='#143442').pack(anchor='w',padx=25)
            tk.Label(header,text='Excel levels  →  scaled sections  →  areas & volumes  →  AutoCAD',font=('Segoe UI',11),fg='#b9d5dc',bg='#143442').pack(anchor='w',padx=25,pady=(0,13))
            body=ttk.Frame(root,padding=16); body.pack(fill='both',expand=True)
            left_outer=ttk.Frame(body,width=360); left_outer.pack(side='left',fill='y',padx=(0,16)); left_outer.pack_propagate(False)
            left_footer=ttk.Frame(left_outer); left_footer.pack(side='bottom',fill='x',pady=(8,0))
            scroll_area=ttk.Frame(left_outer); scroll_area.pack(fill='both',expand=True)
            settings_canvas=tk.Canvas(scroll_area,bg='#eef2f6',highlightthickness=0,width=338)
            settings_scroll=ttk.Scrollbar(scroll_area,orient='vertical',command=settings_canvas.yview)
            settings_canvas.configure(yscrollcommand=settings_scroll.set); settings_scroll.pack(side='right',fill='y');settings_canvas.pack(side='left',fill='both',expand=True)
            left=ttk.Frame(settings_canvas); settings_window=settings_canvas.create_window((0,0),window=left,anchor='nw')
            left.bind('<Configure>',lambda e:settings_canvas.configure(scrollregion=settings_canvas.bbox('all')))
            settings_canvas.bind('<Configure>',lambda e:settings_canvas.itemconfigure(settings_window,width=e.width))
            right=ttk.Frame(body); right.pack(side='left',fill='both',expand=True)
            def heading(parent,text): ttk.Label(parent,text=text,font=('Segoe UI Semibold',12)).pack(anchor='w',pady=(8,7))
            heading(left,'1  Choose your survey')
            ttk.Button(left,text='Open Excel / CSV…',command=self.choose_file,style='Accent.TButton').pack(fill='x')
            self.filelabel=ttk.Label(left,text='No file selected',wraplength=328,foreground='#607187'); self.filelabel.pack(anchor='w',pady=(7,12))
            ttk.Label(left,text='Input mode').pack(anchor='w')
            self.modebox=ttk.Combobox(left,textvariable=self.mode,values=list(MODES),state='readonly'); self.modebox.pack(fill='x',pady=(4,9)); self.modebox.bind('<<ComboboxSelected>>',self.mode_changed)
            ttk.Label(left,text='Worksheet (Area or flat-table mode)').pack(anchor='w')
            self.sheetbox=ttk.Combobox(left,textvariable=self.sheet,state='readonly'); self.sheetbox.pack(fill='x',pady=(4,10))
            heading(left,'2  Set the calculation limits')
            limits=ttk.Frame(left); limits.pack(fill='x')
            for c,(label,var) in enumerate([('From chainage (m)',self.start),('To chainage (m)',self.end)]):
                ttk.Label(limits,text=label).grid(row=0,column=c,sticky='w',padx=(0,10)); ttk.Entry(limits,textvariable=var,width=18).grid(row=1,column=c,sticky='ew',padx=(0,10),pady=(4,10))
                limits.columnconfigure(c,weight=1)
            ttk.Label(left,text='Excluded intervals, metres (optional)').pack(anchor='w')
            ttk.Entry(left,textvariable=self.exclude).pack(fill='x',pady=(4,3))
            ttk.Label(left,text='Example: 1200:1300; 2000:2050',foreground='#607187',font=('Segoe UI',9)).pack(anchor='w')
            ttk.Checkbutton(left,text='Extend using nearest end section area',variable=self.extend).pack(anchor='w',pady=(8,4))
            self.calcbutton=ttk.Button(left,text='Analyze / recalculate',style='Accent.TButton',command=self.analyze); self.calcbutton.pack(fill='x',pady=(6,10))
            heading(left,'3  Export drawings')
            options=ttk.Frame(left); options.pack(fill='x')
            ttk.Label(options,text='CAD format').pack(side='left')
            ttk.Combobox(options,textvariable=self.fmt,values=['DWG','DXF'],state='readonly',width=10).pack(side='right')
            ttk.Checkbutton(left,text='Also export each section separately',variable=self.individual).pack(anchor='w',pady=7)
            ttk.Button(left,text='Choose DWG converter…',command=self.choose_converter).pack(fill='x')
            self.convlabel=ttk.Label(left,text='',wraplength=328,font=('Segoe UI',9),foreground='#607187'); self.convlabel.pack(anchor='w',pady=(3,8)); self.converter_label()
            self.exportbutton=ttk.Button(left_footer,text='Export drawings & tables…',command=self.export_ui,style='Accent.TButton',state='disabled'); self.exportbutton.pack(fill='x')
            self.folderbutton=ttk.Button(left_footer,text='Open latest output folder',command=self.open_output,state='disabled'); self.folderbutton.pack(fill='x',pady=(6,0))
            cards=tk.Frame(right,bg='#eef2f6'); cards.pack(fill='x',pady=(0,12))
            self.metrics=[]
            for title in ['SECTIONS','LENGTH (m)','FILL (m³)','CUT (m³)','NET (m³)']:
                card=tk.Frame(cards,bg='white',padx=12,pady=10); card.pack(side='left',fill='both',expand=True,padx=(0,5))
                tk.Label(card,text=title,bg='white',fg='#647789',font=('Segoe UI',9)).pack(anchor='w')
                v=tk.StringVar(value='—'); tk.Label(card,textvariable=v,bg='white',fg='#143442',font=('Segoe UI Semibold',17)).pack(anchor='w'); self.metrics.append(v)
            self.notebook=ttk.Notebook(right); self.notebook.pack(fill='both',expand=True)
            sectiontab=ttk.Frame(self.notebook,padding=8); volumetab=ttk.Frame(self.notebook,padding=8); notestab=ttk.Frame(self.notebook,padding=8)
            self.notebook.add(sectiontab,text='Cross-sections'); self.notebook.add(volumetab,text='Volume schedule'); self.notebook.add(notestab,text='Source & method')
            self.plot_title=tk.StringVar(value='Select a section after analysis')
            ttk.Label(sectiontab,textvariable=self.plot_title,font=('Segoe UI Semibold',11)).pack(anchor='w',pady=(0,5))
            self.canvas=tk.Canvas(sectiontab,bg='white',height=270,highlightthickness=1,highlightbackground='#d4dfe7'); self.canvas.pack(fill='x'); self.canvas.bind('<Configure>',lambda e:self.draw_plot())
            ttk.Label(sectiontab,text='Green: pre-work   •   Red: post-work   •   Pale green: fill   •   Amber: cut   |   Equal X/Y scale',font=('Segoe UI',9),foreground='#607187').pack(anchor='w',pady=(4,7))
            self.section_tree=self.make_tree(sectiontab,['Chainage m','Mean RL fill m²','Mean RL cut m²','Bounded fill m²','Bounded cut m²','Net m²','Max diff m²'],[100,130,130,130,130,100,115]); self.section_tree.bind('<<TreeviewSelect>>',lambda e:self.draw_plot())
            from profile_ui import ProfilePanel
            self.profile=ProfilePanel(self)
            self.volume_tree=self.make_tree(volumetab,['From m','To m','Length m','Mean fill m²','Fill m³','Cut m³','Net m³','Status'],[90,90,85,105,110,100,110,90])
            self.notes=tk.Text(notestab,wrap='word',bg='white',fg='#20344a',font=('Segoe UI',11),padx=16,pady=14,relief='flat'); self.notes.pack(fill='both',expand=True)
            self.notes.insert('1.0','Open a workbook and select an input mode.\n\nSupported inputs:\n• The supplied Area worksheet with separate pre/post coordinate blocks.\n• XS Input ground points with XS Areas design overrides.\n• A flat Excel/CSV table: Chainage_m, Profile, Offset_m, RL_m.\n\nOne alignment or bank per import. CAD drawings use metres at true 1:1 model scale.'); self.notes.configure(state='disabled')
            ttk.Label(root,textvariable=self.status,background='#dfe8ed',padding=(18,9),wraplength=1270).pack(fill='x')
            for v in [self.mode,self.sheet,self.start,self.end,self.exclude,self.extend]: v.trace_add('write',lambda *_:self.mark_dirty())
            if initial: root.after(200,lambda:self.set_file(initial))

        def make_tree(self,parent,columns,widths):
            frame=ttk.Frame(parent); frame.pack(fill='both',expand=True)
            tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse',height=8)
            for c,w in zip(columns,widths): tree.heading(c,text=c); tree.column(c,width=w,minwidth=70,anchor='e')
            sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview); sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview); tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
            tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); sx.grid(row=1,column=0,sticky='ew'); frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
            return tree

        def mark_dirty(self):
            if self.loading:return
            self.revision+=1
            self.dirty=True; self.exportbutton.configure(state='disabled')
            if self.survey:self.status.set('Settings changed. Analyze / recalculate before exporting; displayed results are from the previous analysis.')

        def choose_file(self):
            if self.busy:return
            p=filedialog.askopenfilename(title='Choose survey workbook',filetypes=[('Excel or CSV','*.xlsx *.xlsm *.csv'),('Excel workbook','*.xlsx'),('CSV','*.csv')])
            if p:self.set_file(p)

        def set_file(self,p):
            try:
                self.loading=True; self.path.set(str(p)); self.filelabel.configure(text=Path(p).name)
                if Path(p).suffix.lower()=='.csv':
                    self.mode.set('Flat table (Excel or CSV)'); self.sheetbox['values']=[]; self.sheet.set('')
                else:
                    w=openpyxl.load_workbook(p,read_only=True,data_only=True,keep_links=False); names=w.sheetnames; w.close(); self.sheetbox['values']=names
                    target=next((s for s in names if s.strip().lower() in ('area','cross section')),None)
                    self.sheet.set(target or names[0])
                    self.mode.set(next(iter(MODES)) if target else '2. Design profile (XS Input / XS Areas)' if 'XS Input' in names else 'Flat table (Excel or CSV)')
                self.start.set(''); self.end.set(''); self.exclude.set(''); self.extend.set(False)
                self.loading=False; self.mark_dirty(); self.status.set('Workbook selected. Click Analyze / recalculate to read profiles and quantities.')
            except Exception as e:self.loading=False; messagebox.showerror('Cannot open workbook',str(e))

        def mode_changed(self,event=None):
            if MODES[self.mode.get()]=='Area':
                names=list(self.sheetbox['values']); self.sheet.set(next((s for s in names if s.strip().lower() in ('area','cross section')),names[0] if names else ''))
            self.sheetbox.configure(state='disabled' if MODES[self.mode.get()]=='Design' else 'readonly')

        def converter_label(self):
            self.convlabel.configure(text='Local DWG converter is ready.' if self.converter.get() and Path(self.converter.get()).is_file() else 'DXF works now. DWG needs a local ODA converter.')

        def choose_converter(self):
            p=filedialog.askopenfilename(title='Select ODAFileConverter.exe',filetypes=[('ODA converter','ODAFileConverter.exe'),('Executable','*.exe')])
            if p:self.converter.set(p); self.converter_label()

        def run_worker(self,task,done):
            if self.busy:return
            self.busy=True; self.calcbutton.configure(state='disabled'); self.exportbutton.configure(state='disabled')
            def worker():
                try: result=task(); self.root.after(0,lambda:self.finish(done,result,None))
                except Exception as e:
                    detail=str(e); self.root.after(0,lambda:self.finish(done,None,detail))
            threading.Thread(target=worker,daemon=True).start()

        def finish(self,done,result,error):
            self.busy=False; self.calcbutton.configure(state='normal')
            if error:self.status.set('Action stopped: '+error); messagebox.showerror('Please check the input',error)
            else:done(result)
            if self.survey and not self.dirty:self.exportbutton.configure(state='normal')

        def analyze(self):
            if self.busy:return
            if not self.path.get():self.choose_file(); return
            try:
                path=self.path.get(); mode=MODES[self.mode.get()]; sheet=self.sheet.get() or None
                start=float(self.start.get()) if self.start.get().strip() else None; end=float(self.end.get()) if self.end.get().strip() else None
                exc=exclusions(self.exclude.get()); extend=self.extend.get()
            except ValueError as e:messagebox.showerror('Check calculation limits',str(e));return
            self.status.set('Reading coordinates and calculating exact fill/cut areas…')
            self.dirty=True
            def task():
                s=load_survey(path,mode,sheet); return s,calculate_volumes(s,start,end,exc,extend)
            revision=self.revision
            def done(result):
                if revision!=self.revision:
                    self.dirty=True; self.status.set('Settings changed during analysis. Click Analyze / recalculate again.'); return
                self.show_results(result)
            self.run_worker(task,done)

        def show_results(self,result):
            self.survey,self.vol=result; self.loading=True
            self.start.set(f'{self.vol["start"]:g}'); self.end.set(f'{self.vol["end"]:g}'); self.loading=False; self.dirty=False
            vals=[str(len(self.survey.sections)),f'{self.vol["length"]:,.1f}',f'{self.vol["fill"]:,.2f}',f'{self.vol["cut"]:,.2f}',f'{self.vol["net"]:,.2f}']
            for v,t in zip(self.metrics,vals):v.set(t)
            self.section_tree.delete(*self.section_tree.get_children()); self.volume_tree.delete(*self.volume_tree.get_children())
            for i,s in enumerate(self.survey.sections):self.section_tree.insert('', 'end',iid=str(i),values=[f'{s.chainage:.3f}']+[f'{x:.6f}' for x in [s.mean_fill,s.mean_cut,s.fill,s.cut,s.net,max(abs(s.mean_fill-s.fill),abs(s.mean_cut-s.cut))]])
            self.profile.reset(self.survey)
            for r in self.vol['rows']:self.volume_tree.insert('','end',values=[f'{r[k]:,.3f}' for k in ['start','end','length','mean_fill','fill_volume','cut_volume','net_volume']]+['Excluded' if r['excluded'] else 'Extended' if r['extended'] else 'Included'])
            notes=[ATTRIBUTION,'Mean RL / trapezoidal strips and closed-coordinate polygon areas are computed independently and shown side by side. For the same straight-segment profiles they should agree. Bounded area = abs(sum(Xi*Yi+1 - Xi+1*Yi))/2. Cut/fill polygons are split at crossings. This is a coordinate-area calculation, not an invocation of AutoCAD.',f'Source: {self.survey.source}',f'Mode: {self.survey.mode}',f'{len(self.survey.sections)} sections. Chainages and offsets in metres. Levels use the source datum.','',
                'CALCULATION','Profiles are joined by straight segments. All pre/post offsets and exact crossing points split the integration strips. Fill is where post is above pre; cut is where post is below pre. Net = fill − cut.',
                'Volume = (area at start + area at end) / 2 × chainage distance, calculated separately for fill and cut. Areas at partial interval limits are interpolated linearly. Excluded intervals contribute zero.',
                'Reference pre/post areas are signed integrals relative to RL 0 and can be negative. They are not material quantities.','', 'SOURCE NOTES']+self.survey.warnings
            for s in self.survey.sections:
                notes.extend(f'Ch {s.chainage:g}: {w}' for w in s.warnings)
            if self.survey.reference_volume is not None:
                notes+=['',f'Workbook saved full-reach reference volume: {self.survey.reference_volume:,.6f} m³.']
                if abs(self.vol['start']-self.survey.sections[0].chainage)<1e-8 and abs(self.vol['end']-self.survey.sections[-1].chainage)<1e-8 and not self.vol['excluded']:
                    notes.append(f'Recomputed net minus workbook reference: {self.vol["net"]-self.survey.reference_volume:+.6f} m³.')
            notes+=['','CAD OUTPUT','Closed fill/cut polylines and hatches, original profile lines, coordinate tables, sectional-area tables, and a mean-area volume schedule. Model scale is 1:1 in metres on both axes. Tables are editable CAD lines/text; rerun the app to refresh calculations.',
                'DWG uses the local ODA converter and is checked by reopening to DXF and comparing geometry. No files are uploaded.','No bulking, settlement, shrinkage or stripping allowance is applied.']
            self.notes.configure(state='normal'); self.notes.delete('1.0','end'); self.notes.insert('1.0','\n\n'.join(notes)); self.notes.configure(state='disabled')
            self.section_tree.selection_set('0'); self.section_tree.focus('0'); self.draw_plot()
            self.status.set(f'Analysis complete: {len(self.survey.sections)} sections. Review the source notes, then export.')

        def draw_plot(self):
            c=self.canvas; c.delete('all')
            if not self.survey:return
            selected=self.section_tree.selection(); i=int(selected[0]) if selected else 0; s=self.survey.sections[i]
            self.plot_title.set(f'Ch {s.chainage:,.3f} m   ·   Fill {s.fill:.4f} m²   ·   Cut {s.cut:.4f} m²')
            w=max(c.winfo_width(),300); h=max(c.winfo_height(),200)
            minx=s.pre[0][0]; maxx=s.pre[-1][0]; miny=min(y for x,y in s.pre+s.post); maxy=max(y for x,y in s.pre+s.post)
            scale=min((w-100)/(maxx-minx),(h-65)/max(1,maxy-miny)); left=(w-(maxx-minx)*scale)/2; base=(h-20+(maxy-miny)*scale)/2
            def pt(p):return left+(p[0]-minx)*scale,base-(p[1]-miny)*scale
            for kind,polys in [('fill',s.fill_polygons),('cut',s.cut_polygons)]:
                for p in polys:c.create_polygon(*[q for v in p for q in pt(v)],fill='#d8eadd' if kind=='fill' else '#f7dfad',outline='')
            for pts,col in [(s.pre,'#25834f'),(s.post,'#d45043')]:c.create_line(*[q for v in pts for q in pt(v)],fill=col,width=2)
            ticks=max(1,math.ceil((maxx-minx)/8/5)*5)
            for x in range(math.ceil(minx/ticks)*ticks,math.floor(maxx/ticks)*ticks+1,ticks):
                px,_=pt((x,miny)); c.create_text(px,h-12,text=f'{x:g}',fill='#6a7d8b',font=('Segoe UI',9))
            c.create_text(10,12,anchor='nw',text=f'RL {maxy:.3f} to {miny:.3f} m',fill='#6a7d8b',font=('Segoe UI',9))
            c.create_text(w-12,12,anchor='ne',text='Offset / RL · 1:1 axes',fill='#6a7d8b',font=('Segoe UI',9))

        def export_ui(self):
            if self.dirty or not self.survey:return
            if self.fmt.get()=='DWG' and not Path(self.converter.get()).is_file():messagebox.showerror('DWG converter needed','Select ODAFileConverter.exe, or choose DXF output.');return
            folder=filedialog.askdirectory(title='Choose a folder for the export')
            if not folder:return
            from datetime import datetime
            target=Path(folder)/('Earthwork_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
            n=2
            while target.exists():target=Path(folder)/(target.name+f'_{n}'); n+=1
            import copy
            survey,vol=self.survey,self.vol; fmt=self.fmt.get(); converter=self.converter.get(); individual=self.individual.get(); profile=copy.deepcopy(self.profile.model)
            self.status.set('Creating CAD geometry and tables'+(' and verifying DWG conversion…' if fmt=='DWG' else '…'))
            def done(p):
                self.output=Path(p).parent; self.folderbutton.configure(state='normal'); self.status.set('Export complete: '+str(p)); messagebox.showinfo('Drawings created',f'Saved {fmt} drawing, coordinate data and quantity schedules to:\n{self.output}')
            self.run_worker(lambda:export(survey,vol,target,fmt,converter,individual,profile),done)

        def open_output(self):
            if self.output and self.output.exists():os.startfile(self.output)

    root=tk.Tk(); instance=App(root)
    if test_hook:root.after(300,lambda:test_hook(instance))
    root.mainloop()

def main():
    parser=argparse.ArgumentParser(description='Local Excel pre/post survey to AutoCAD converter')
    parser.add_argument('--open'); parser.add_argument('--batch'); parser.add_argument('--mode',choices=['Area','Design','Flat'],default='Area'); parser.add_argument('--sheet')
    parser.add_argument('--out'); parser.add_argument('--format',choices=['DWG','DXF'],default='DXF'); parser.add_argument('--converter',default='')
    parser.add_argument('--start',type=float); parser.add_argument('--end',type=float); parser.add_argument('--exclude',default=''); parser.add_argument('--extend',action='store_true'); parser.add_argument('--individual',action='store_true')
    parser.add_argument('--kind',choices=['Embankment','River / Khal']);parser.add_argument('--low-side',choices=SIDES,default='Unconfirmed');parser.add_argument('--features')
    parser.add_argument('--design-grade',help='CSV with Start_m,End_m,Start_RL_m,End_RL_m')
    args=parser.parse_args()
    if args.batch:
        if not args.out:parser.error('--out is required with --batch')
        survey=load_survey(args.batch,args.mode,args.sheet); vol=calculate_volumes(survey,args.start,args.end,exclusions(args.exclude),args.extend)
        profile=LongProfile(survey,args.kind,args.low_side)
        if args.features:profile.load(args.features,survey)
        if args.design_grade:profile.design.load(args.design_grade)
        result=export(survey,vol,args.out,args.format,args.converter or discover_converter(),args.individual,profile)
        print(json.dumps(dict(drawing=str(result),sections=len(survey.sections),fill=vol['fill'],cut=vol['cut'],net=vol['net'],length=vol['length'])))
    else: main_gui(args.open)

if __name__=='__main__': main()
