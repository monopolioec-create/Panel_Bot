import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"
req_path=root/"requirements.txt"

# =========================================================
# VERSION
# =========================================================
s=core_path.read_text(encoding="utf-8")
if "APP_VERSION = '2.2.1'" not in s and "APP_VERSION = '2.2.2'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.2.1")
s=s.replace("APP_VERSION = '2.2.1'","APP_VERSION = '2.2.2'")
compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# Dependencia liviana que incluye ffmpeg para extraer fotogramas de videos.
if req_path.exists():
    req=req_path.read_text(encoding="utf-8")
    if "imageio-ffmpeg" not in req.lower():
        req=req.rstrip()+"\nimageio-ffmpeg>=0.5\n"
        req_path.write_text(req,encoding="utf-8")

# =========================================================
# GUI IMPORTS
# =========================================================
g=gui_path.read_text(encoding="utf-8")
g=g.replace(
    "import calendar, csv, json, os, re, threading, tkinter as tk, webbrowser",
    "import calendar, csv, json, os, re, subprocess, threading, tkinter as tk, webbrowser",
    1
)
if "import imageio_ffmpeg" not in g:
    if "from PIL import Image, ImageTk\n" in g:
        g=g.replace("from PIL import Image, ImageTk\n","from PIL import Image, ImageTk\nimport imageio_ffmpeg\n",1)
    else:
        g=g.replace("import core_local as C\n","import core_local as C\nfrom PIL import Image, ImageTk\nimport imageio_ffmpeg\n",1)

# =========================================================
# EDITOR DE REGLAS: pie fijo SIEMPRE visible
# =========================================================
rule_class = r'''
class RuleDialog(tk.Toplevel):
    def __init__(self,parent,pid,value=None):
        super().__init__(parent)
        self.result=None
        self.pid=pid
        self.v=value or {}
        self.actions=[dict(a) for a in self.v.get('actions',[])]
        self.title('Editar regla')

        sw=max(800,self.winfo_screenwidth())
        sh=max(650,self.winfo_screenheight())
        width=min(920,max(760,sw-100))
        height=min(760,max(610,sh-120))
        x=max(10,(sw-width)//2)
        y=max(10,(sh-height)//2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.minsize(760,600)
        self.resizable(True,True)
        self.transient(parent)
        self.grab_set()

        root=ttk.Frame(self,padding=16)
        root.pack(fill='both',expand=True)

        grid=ttk.Frame(root)
        grid.pack(fill='x')
        self.vars={}

        fields=[
            ('Nombre de la regla','name',self.v.get('name','')),
            ('Cuándo se activa','match_type',MATCH_LABELS.get(self.v.get('match_type','contains'),'Contiene')),
            ('Palabra o frase','pattern',self.v.get('pattern','')),
            ('Prioridad','priority',str(self.v.get('priority',100))),
        ]
        for i,(lab,key,val) in enumerate(fields):
            ttk.Label(grid,text=lab).grid(row=i,column=0,sticky='w',pady=5)
            sv=tk.StringVar(value=val)
            self.vars[key]=sv
            if key=='match_type':
                w=ttk.Combobox(grid,textvariable=sv,values=list(MATCH_LABELS.values()),state='readonly')
            else:
                w=ttk.Entry(grid,textvariable=sv)
            w.grid(row=i,column=1,sticky='ew',pady=5)
            grid.columnconfigure(1,weight=1)

        ttk.Label(
            grid,
            text='Ejemplo: si eliges “Contiene” y escribes VIDEOCLIP, la regla se activa cuando el mensaje incluya esa palabra.',
            foreground=MUTED,wraplength=700
        ).grid(row=4,column=0,columnspan=2,sticky='w',pady=(2,8))

        self.enabled=tk.BooleanVar(value=bool(self.v.get('enabled',1)))
        self.case=tk.BooleanVar(value=bool(self.v.get('case_sensitive',0)))
        self.stop=tk.BooleanVar(value=bool(self.v.get('stop_after',1)))
        opts=ttk.Frame(root)
        opts.pack(fill='x',pady=5)
        ttk.Checkbutton(opts,text='Regla activa',variable=self.enabled).pack(side='left')
        ttk.Checkbutton(opts,text='Distinguir mayúsculas y minúsculas',variable=self.case).pack(side='left',padx=15)
        ttk.Checkbutton(opts,text='No revisar más reglas después de esta',variable=self.stop).pack(side='left')

        # El pie se reserva ANTES del panel expansible. Así nunca queda fuera de pantalla.
        foot=ttk.Frame(root)
        foot.pack(side='bottom',fill='x',pady=(8,0))
        ttk.Button(foot,text='GUARDAR REGLA',command=self.save).pack(side='right',padx=5)
        ttk.Button(foot,text='Cancelar',command=self.destroy).pack(side='right')

        box=ttk.LabelFrame(root,text='Secuencia de acciones',padding=8)
        box.pack(fill='both',expand=True,pady=(10,0))
        self.tree=ttk.Treeview(box,columns=('tipo','resumen'),show='headings')
        self.tree.heading('tipo',text='Acción')
        self.tree.heading('resumen',text='Detalle')
        self.tree.column('tipo',width=150)
        self.tree.column('resumen',width=610)
        self.tree.pack(fill='both',expand=True)

        b=ttk.Frame(box)
        b.pack(fill='x',pady=7)
        ttk.Button(b,text='+ Agregar acción',command=self.add_action).pack(side='left')
        ttk.Button(b,text='Editar',command=self.edit_action).pack(side='left',padx=5)
        ttk.Button(b,text='Eliminar',command=self.del_action).pack(side='left')
        ttk.Button(b,text='Subir',command=lambda:self.move(-1)).pack(side='left',padx=(18,3))
        ttk.Button(b,text='Bajar',command=lambda:self.move(1)).pack(side='left')

        self.bind('<Escape>',lambda _e:self.destroy())
        self.bind('<Control-s>',lambda _e:self.save())
        self.bind('<Control-S>',lambda _e:self.save())

        self.refresh()
        self.wait_window()

    def summary(self,a):
        t=a.get('type','')
        if t=='save_contact':
            return f"Guardar cliente · {a.get('contact_name') or '@nombre'} · {a.get('label') or 'Cliente'}"
        if t=='human_handoff':
            return a.get('reason') or 'Pasar la conversación a un asesor'
        if t in ('buttons','list'):
            return (a.get('text') or '')[:90]+f" · {len(a.get('buttons',a.get('sections',[])))} opciones"
        if a.get('template_media_name'):
            return f"Archivo pendiente: {a.get('template_media_name')}"
        return (a.get('text') or a.get('name') or a.get('file_name') or '')[:110]

    def refresh(self):
        for x in self.tree.get_children():
            self.tree.delete(x)
        for i,a in enumerate(self.actions):
            self.tree.insert('', 'end', iid=str(i), values=(action_label(a.get('type','')),self.summary(a)))

    def add_action(self):
        d=ActionDialog(self)
        if d.result:
            self.actions.append(d.result)
            self.refresh()

    def edit_action(self):
        selected=self.tree.selection()
        if not selected:return
        i=int(selected[0])
        d=ActionDialog(self,self.actions[i])
        if d.result:
            self.actions[i]=d.result
            self.refresh()

    def del_action(self):
        selected=self.tree.selection()
        if selected:
            self.actions.pop(int(selected[0]))
            self.refresh()

    def move(self,delta):
        selected=self.tree.selection()
        if not selected:return
        i=int(selected[0]);j=i+delta
        if 0<=j<len(self.actions):
            self.actions[i],self.actions[j]=self.actions[j],self.actions[i]
            self.refresh()
            self.tree.selection_set(str(j))

    def save(self):
        name=self.vars['name'].get().strip()
        if not name:
            return messagebox.showwarning('Falta el nombre','Escribe el nombre de la regla.',parent=self)
        try:
            priority=int(self.vars['priority'].get() or 100)
        except Exception:
            priority=100
        self.result={
            'id':self.v.get('id'),
            'name':name,
            'match_type':MATCH_BY_LABEL.get(self.vars['match_type'].get(),'contains'),
            'pattern':self.vars['pattern'].get(),
            'priority':priority,
            'enabled':self.enabled.get(),
            'case_sensitive':self.case.get(),
            'stop_after':self.stop.get(),
            'actions':self.actions,
        }
        self.destroy()
'''
rule_class=textwrap.dedent(rule_class)
g,n=re.subn(
    r"class RuleDialog\(tk\.Toplevel\):.*?(?=\n\nclass App\(tk\.Tk\):)",
    lambda _m:rule_class.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar RuleDialog")

# =========================================================
# BIBLIOTECA: miniaturas reales + tamaño ajustable + iconos
# =========================================================
media_methods = r'''
    def build_media(self):
        f=self.tabs['Archivos']
        ttk.Label(f,text='Biblioteca local de archivos',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(
            f,
            text='Las imágenes y videos muestran una miniatura real. Audios, PDF y otros documentos muestran un icono por tipo. '
                 'Puedes ajustar el tamaño de las tarjetas con el control “Tamaño”.',
            wraplength=1000,foreground=MUTED
        ).pack(anchor='w',pady=(2,8))

        tools=ttk.Frame(f)
        tools.pack(fill='x',pady=(4,6))
        ttk.Button(tools,text='+ Agregar archivos',command=self.add_files).pack(side='left')
        ttk.Button(tools,text='Eliminar seleccionados',command=self.remove_media).pack(side='left',padx=5)
        ttk.Button(tools,text='Abrir carpeta',command=lambda:os.startfile(C.MEDIA_DIR)).pack(side='left',padx=(0,14))
        ttk.Label(tools,text='Ver como:').pack(side='left')
        self.media_view=tk.StringVar(value='miniaturas')
        ttk.Radiobutton(
            tools,text='Miniaturas',value='miniaturas',variable=self.media_view,
            command=self.set_media_view
        ).pack(side='left',padx=4)
        ttk.Radiobutton(
            tools,text='Lista',value='lista',variable=self.media_view,
            command=self.set_media_view
        ).pack(side='left')

        ttk.Separator(tools,orient='vertical').pack(side='left',fill='y',padx=10)
        ttk.Label(tools,text='Tamaño:').pack(side='left')
        self.media_thumb_size=tk.DoubleVar(value=130)
        self.media_thumb_value=tk.StringVar(value='130 px')
        ttk.Scale(
            tools,from_=90,to=240,orient='horizontal',
            variable=self.media_thumb_size,
            command=self._on_media_thumb_size,
            length=160
        ).pack(side='left',padx=(6,4))
        ttk.Label(tools,textvariable=self.media_thumb_value,width=7).pack(side='left')

        self.media_area=ttk.Frame(f)
        self.media_area.pack(fill='both',expand=True)

        self.media_tree=ttk.Treeview(
            self.media_area,columns=('name','type','size','path'),show='headings'
        )
        for col,head,width in [
            ('name','Archivo',280),('type','Tipo',120),('size','Tamaño',90),('path','Ubicación local',560)
        ]:
            self.media_tree.heading(col,text=head)
            self.media_tree.column(col,width=width)

        self.media_gallery_wrap=ttk.Frame(self.media_area)
        self.media_gallery_canvas=tk.Canvas(self.media_gallery_wrap,bg=BG,highlightthickness=0)
        self.media_gallery_scroll=ttk.Scrollbar(
            self.media_gallery_wrap,orient='vertical',command=self.media_gallery_canvas.yview
        )
        self.media_gallery_canvas.configure(yscrollcommand=self.media_gallery_scroll.set)
        self.media_gallery_inner=ttk.Frame(self.media_gallery_canvas)
        self.media_gallery_window=self.media_gallery_canvas.create_window(
            (0,0),window=self.media_gallery_inner,anchor='nw'
        )
        self.media_gallery_inner.bind(
            '<Configure>',
            lambda e:self.media_gallery_canvas.configure(scrollregion=self.media_gallery_canvas.bbox('all'))
        )
        self.media_gallery_canvas.bind(
            '<Configure>',
            self._media_gallery_resize
        )
        self.media_gallery_canvas.bind('<MouseWheel>',self._media_gallery_wheel)
        self.media_gallery_canvas.bind('<Control-MouseWheel>',self._media_thumb_wheel)
        self.media_gallery_canvas.pack(side='left',fill='both',expand=True)
        self.media_gallery_scroll.pack(side='right',fill='y')

        self.media_selected=set()
        self.media_checks={}
        self.media_photo_refs=[]
        self._media_thumb_after=None
        self._media_last_gallery_width=0
        self.refresh_media()
        self.set_media_view()

    def media_file_type(self,path):
        ext=Path(path).suffix.lower()
        if ext in ('.jpg','.jpeg','.png','.webp','.gif','.bmp','.tif','.tiff'):
            return 'Imagen'
        if ext in ('.mp4','.mov','.m4v','.webm','.avi','.mkv','.wmv','.mpeg','.mpg'):
            return 'Video'
        if ext in ('.mp3','.wav','.m4a','.ogg','.oga','.aac','.flac','.wma'):
            return 'Audio'
        if ext=='.pdf':
            return 'PDF'
        if ext in ('.doc','.docx','.odt','.rtf'):
            return 'Documento'
        if ext in ('.xls','.xlsx','.ods','.csv'):
            return 'Hoja de cálculo'
        if ext in ('.ppt','.pptx','.odp'):
            return 'Presentación'
        if ext in ('.zip','.rar','.7z','.tar','.gz'):
            return 'Comprimido'
        if ext in ('.txt','.md','.log'):
            return 'Texto'
        return 'Archivo'

    def media_icon_text(self,path):
        typ=self.media_file_type(path)
        ext=Path(path).suffix.lower().lstrip('.').upper()
        if typ=='Audio':
            return '♫','AUDIO'
        if typ=='PDF':
            return '▣','PDF'
        if typ=='Documento':
            return '▤',ext or 'DOC'
        if typ=='Hoja de cálculo':
            return '▦',ext or 'XLS'
        if typ=='Presentación':
            return '▥',ext or 'PPT'
        if typ=='Comprimido':
            return '▧',ext or 'ZIP'
        if typ=='Texto':
            return '≡',ext or 'TXT'
        return '◇',ext or 'ARCHIVO'

    def _media_type_display(self,path):
        typ=self.media_file_type(path)
        if typ in ('Imagen','Video'):
            return typ
        icon,label=self.media_icon_text(path)
        return f'{icon} {label}'

    def _video_thumbnail_path(self,m):
        src=Path(m.get('path') or '')
        if not src.exists() or not src.is_file():
            return None
        try:
            mid=int(m.get('id') or 0)
        except Exception:
            mid=0
        thumb_dir=Path(C.DATA_DIR)/'thumb_cache'
        thumb_dir.mkdir(parents=True,exist_ok=True)
        dst=thumb_dir/f'video_{mid or abs(hash(str(src)))}.jpg'
        try:
            if dst.exists() and dst.stat().st_size>1000 and dst.stat().st_mtime>=src.stat().st_mtime:
                return dst
        except Exception:
            pass

        exe=imageio_ffmpeg.get_ffmpeg_exe()
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        for seek in ('0.6','0'):
            try:
                if dst.exists():
                    try:dst.unlink()
                    except Exception:pass
                cmd=[
                    exe,'-hide_banner','-loglevel','error','-y',
                    '-ss',seek,'-i',str(src),
                    '-frames:v','1',
                    '-vf','scale=480:-2',
                    '-q:v','4',
                    str(dst)
                ]
                result=subprocess.run(
                    cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=flags,timeout=15
                )
                if result.returncode==0 and dst.exists() and dst.stat().st_size>500:
                    try:
                        os.utime(dst,(src.stat().st_atime,src.stat().st_mtime))
                    except Exception:
                        pass
                    return dst
            except Exception:
                continue
        return None

    def _media_photo(self,m,max_w,max_h):
        typ=self.media_file_type(m.get('path') or '')
        source=None
        if typ=='Imagen':
            source=Path(m.get('path') or '')
        elif typ=='Video':
            source=self._video_thumbnail_path(m)
        if not source:
            return None
        try:
            source=Path(source)
            if not source.exists():
                return None
            with Image.open(source) as im:
                im=im.convert('RGB')
                im.thumbnail((max(20,int(max_w)),max(20,int(max_h))),Image.LANCZOS)
                return ImageTk.PhotoImage(im.copy())
        except Exception:
            return None

    def _on_media_thumb_size(self,value):
        try:size=max(90,min(240,int(float(value))))
        except Exception:size=130
        self.media_thumb_value.set(f'{size} px')
        if getattr(self,'_media_thumb_after',None):
            try:self.after_cancel(self._media_thumb_after)
            except Exception:pass
        self._media_thumb_after=self.after(120,self.refresh_media_gallery)

    def _media_thumb_wheel(self,event):
        try:
            step=10 if event.delta>0 else -10
            value=max(90,min(240,int(float(self.media_thumb_size.get()))+step))
            self.media_thumb_size.set(value)
            self._on_media_thumb_size(value)
        except Exception:
            pass
        return 'break'

    def _media_gallery_wheel(self,event):
        try:
            self.media_gallery_canvas.yview_scroll(int(-1*(event.delta/120)),'units')
        except Exception:
            pass
        return 'break'

    def _media_gallery_resize(self,event):
        self.media_gallery_canvas.itemconfigure(self.media_gallery_window,width=event.width)
        if abs(int(event.width)-int(getattr(self,'_media_last_gallery_width',0)))>50:
            self._media_last_gallery_width=int(event.width)
            if getattr(self,'media_view',None) is not None and self.media_view.get()=='miniaturas':
                if getattr(self,'_media_thumb_after',None):
                    try:self.after_cancel(self._media_thumb_after)
                    except Exception:pass
                self._media_thumb_after=self.after(100,self.refresh_media_gallery)

    def set_media_view(self):
        if not hasattr(self,'media_view'):
            return
        self.media_tree.pack_forget()
        self.media_gallery_wrap.pack_forget()
        if self.media_view.get()=='lista':
            self.media_tree.pack(fill='both',expand=True,pady=8)
        else:
            self.media_gallery_wrap.pack(fill='both',expand=True,pady=8)
            self.refresh_media_gallery()

    def refresh_media(self):
        if not hasattr(self,'media_tree'):
            return
        for item in self.media_tree.get_children():
            self.media_tree.delete(item)
        for m in C.media_list():
            self.media_tree.insert(
                '', 'end', iid=str(m['id']),
                values=(m['name'],self._media_type_display(m['path']),human_size(m['size']),m['path'])
            )
        if hasattr(self,'media_gallery_inner'):
            self.refresh_media_gallery()

    def refresh_media_gallery(self):
        if not hasattr(self,'media_gallery_inner'):
            return
        self._media_thumb_after=None
        for w in self.media_gallery_inner.winfo_children():
            w.destroy()
        self.media_photo_refs=[]
        self.media_checks={}
        media=C.media_list()
        valid_ids={int(m['id']) for m in media}
        self.media_selected.intersection_update(valid_ids)

        try:thumb=max(90,min(240,int(float(self.media_thumb_size.get()))))
        except Exception:thumb=130
        preview_h=max(62,int(thumb*0.62))
        available=max(thumb+30,int(self.media_gallery_canvas.winfo_width() or 900)-20)
        cols=max(1,min(10,available//(thumb+34)))

        for col in range(12):
            self.media_gallery_inner.columnconfigure(col,weight=0,minsize=0)

        for idx,m in enumerate(media):
            mid=int(m['id'])
            row=idx//cols
            col=idx%cols
            card=ttk.Frame(self.media_gallery_inner,padding=7,relief='solid',borderwidth=1)
            card.grid(row=row,column=col,sticky='nw',padx=5,pady=5)

            preview=ttk.Frame(card,width=thumb,height=preview_h)
            preview.pack()
            preview.pack_propagate(False)

            typ=self.media_file_type(m['path'])
            photo=self._media_photo(m,thumb-8,preview_h-8)
            if photo:
                self.media_photo_refs.append(photo)
                ttk.Label(preview,image=photo).pack(fill='both',expand=True)
            else:
                icon,label=self.media_icon_text(m['path'])
                if typ=='Video':
                    icon,label='▶','VIDEO'
                ttk.Label(
                    preview,text=f'{icon}\n{label}',anchor='center',justify='center',
                    font=('Segoe UI',max(10,min(22,int(thumb/7))),'bold')
                ).pack(fill='both',expand=True)

            type_label=typ if typ in ('Imagen','Video') else self._media_type_display(m['path'])
            ttk.Label(card,text=type_label,foreground=MUTED).pack(anchor='w',pady=(5,0))
            ttk.Label(card,text=m['name'],wraplength=thumb).pack(anchor='w',pady=(2,1))
            ttk.Label(card,text=human_size(m['size']),foreground=MUTED).pack(anchor='w')
            var=tk.BooleanVar(value=mid in self.media_selected)
            self.media_checks[mid]=var
            ttk.Checkbutton(
                card,text='Seleccionar',variable=var,
                command=lambda x=mid,v=var:self.toggle_media_selection(x,v)
            ).pack(anchor='w',pady=(4,0))

    def toggle_media_selection(self,mid,var):
        if var.get():
            self.media_selected.add(int(mid))
        else:
            self.media_selected.discard(int(mid))

    def selected_media_ids(self):
        if hasattr(self,'media_view') and self.media_view.get()=='miniaturas':
            return sorted(self.media_selected)
        return [int(x) for x in self.media_tree.selection()]

    def add_files(self):
        files=filedialog.askopenfilenames(parent=self,title='Seleccionar archivos')
        for path in files:
            try:
                C.add_media(path)
            except Exception as e:
                messagebox.showerror('Archivo',str(e),parent=self)
        self.refresh_media()

    def remove_media(self):
        ids=self.selected_media_ids()
        if not ids:
            return messagebox.showinfo('Biblioteca','Selecciona uno o varios archivos.',parent=self)
        if not messagebox.askyesno(
            'Eliminar archivos',
            f'¿Eliminar {len(ids)} archivo(s) de la biblioteca local?',
            parent=self
        ):
            return
        thumb_dir=Path(C.DATA_DIR)/'thumb_cache'
        for mid in ids:
            C.delete_media(mid)
            try:
                p=thumb_dir/f'video_{int(mid)}.jpg'
                if p.exists():p.unlink()
            except Exception:
                pass
        self.media_selected.difference_update(ids)
        self.refresh_media()
'''
media_methods=textwrap.indent(textwrap.dedent(media_methods).strip()+"\n","    ")
g,n=re.subn(
    r"    def build_media\(self\):.*?(?=\n    def refresh_google_contacts_status\(self\):|\n    def build_contacts\(self\):)",
    lambda _m:media_methods.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar la biblioteca de archivos")

# =========================================================
# ESTADOS: miniatura visible en la tabla
# =========================================================
new_build_status = r'''
    def build_status(self):
        f=self.tabs['Estados']
        ttk.Label(f,text='Estados de WhatsApp programados',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(
            f,
            text='Programa publicaciones reales en Estados de WhatsApp. Las imágenes y videos muestran una vista previa '
                 'para que puedas identificar rápidamente qué archivo está programado.',
            wraplength=1000,foreground=MUTED
        ).pack(anchor='w',pady=(2,8))

        style=ttk.Style(self)
        style.configure('Status.Treeview',rowheight=76)

        cols=('type','date','time','rec','content','active')
        self.status_tree=ttk.Treeview(
            f,columns=cols,show='tree headings',style='Status.Treeview'
        )
        self.status_tree.heading('#0',text='Vista')
        self.status_tree.column('#0',width=125,minwidth=110,stretch=False,anchor='center')
        for col,head,width in [
            ('type','Tipo',90),('date','Fecha',95),('time','Hora',70),
            ('rec','Repetición',130),('content','Contenido / archivo',520),('active','Activo',65)
        ]:
            self.status_tree.heading(col,text=head)
            self.status_tree.column(col,width=width)
        self.status_tree.pack(fill='both',expand=True,pady=12)
        self.status_photo_refs=[]

        b=ttk.Frame(f);b.pack(fill='x')
        ttk.Button(b,text='+ Programar estado',command=self.add_status).pack(side='left')
        ttk.Button(b,text='Editar',command=self.edit_status).pack(side='left',padx=5)
        ttk.Button(b,text='Publicar ahora',command=self.publish_status_now).pack(side='left')
        ttk.Button(b,text='Eliminar',command=self.del_status).pack(side='right')
'''
new_build_status=textwrap.indent(textwrap.dedent(new_build_status).strip()+"\n","    ")
g,n=re.subn(
    r"    def build_status\(self\):.*?(?=\n    def _status_media_name\(self,media_id\):)",
    lambda _m:new_build_status.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar build_status")

new_refresh_status = r'''
    def refresh_status(self):
        if not hasattr(self,'status_tree'):
            return
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        self.status_photo_refs=[]
        pid=self.pid()
        if not pid:return

        media_by_id={int(m['id']):m for m in C.media_list()}
        day_names={'0':'Lun','1':'Mar','2':'Mié','3':'Jue','4':'Vie','5':'Sáb','6':'Dom'}

        for item in C.schedules_for(pid):
            date=item.get('run_date') or ''
            try:
                date_show=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                date_show=date

            kind=item.get('kind') or 'status_text'
            text=(item.get('text') or '').strip()
            try:media_id=int(item.get('media_id') or 0)
            except Exception:media_id=0
            media_name=self._status_media_name(media_id)

            if kind=='status_text':
                content=text
                preview_text='TEXTO'
                photo=None
            else:
                content=media_name + (f' · {text}' if text else '')
                preview_text='VIDEO' if kind=='status_video' else 'IMAGEN'
                record=media_by_id.get(media_id)
                photo=self._media_photo(record,105,62) if record else None
                if photo:
                    self.status_photo_refs.append(photo)

            rec=item.get('recurrence') or 'once'
            if rec=='selected_days':
                selected=[x.strip() for x in str(item.get('weekdays') or '').split(',') if x.strip()]
                rec_show=', '.join(day_names.get(x,x) for x in selected) or 'Días seleccionados'
            else:
                rec_show=RECURRENCE_LABELS.get(rec,'Una sola vez')

            self.status_tree.insert(
                '', 'end', iid=str(item['id']),
                text=preview_text,
                image=photo if photo else '',
                values=(
                    STATUS_KIND_LABELS.get(kind,kind),
                    date_show if rec=='once' else '—',
                    item.get('run_time') or '',
                    rec_show,
                    content[:220],
                    'Sí' if item.get('active') else 'No'
                )
            )
'''
new_refresh_status=textwrap.indent(textwrap.dedent(new_refresh_status).strip()+"\n","    ")
g,n=re.subn(
    r"    def refresh_status\(self\):.*?(?=\n    def status_dialog\(self,val=None\):)",
    lambda _m:new_refresh_status.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar refresh_status")

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER VERSION
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.2.1" not in t and "2.2.2" not in t:
    raise SystemExit("No se encontró versión 2.2.1 en installer.iss")
t=t.replace("2.2.1","2.2.2")
iss_path.write_text(t,encoding="utf-8")
