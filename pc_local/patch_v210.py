import calendar
import pathlib
import re
import sys
import textwrap

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r"pc_local\buildsrc")
core_path = root / "core_local.py"
gui_path = root / "gui_local.py"
iss_path = root / "installer.iss"

# ---------------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------------
s = core_path.read_text(encoding="utf-8")
s = s.replace("APP_VERSION = '2.0.9'", "APP_VERSION = '2.1.1'")

# Add media_id to scheduled WhatsApp status posts without breaking existing DBs.
migration_anchor = "ensure_google_contact_columns()\n"
migration_code = r'''
ensure_google_contact_columns()

def ensure_schedule_media_columns():
    with DB_LOCK, db() as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(schedules)').fetchall()}
        if 'media_id' not in cols:
            con.execute("ALTER TABLE schedules ADD COLUMN media_id INTEGER NOT NULL DEFAULT 0")
        con.commit()

ensure_schedule_media_columns()
'''
migration_code = textwrap.dedent(migration_code)
if "def ensure_schedule_media_columns" not in s:
    if migration_anchor not in s:
        raise SystemExit("No se encontró migración base para estados multimedia")
    s = s.replace(migration_anchor, migration_code, 1)

# Replace schedule persistence helpers.
schedule_helpers = r'''
def schedules_for(pid):
    return q('SELECT * FROM schedules WHERE profile_id=? ORDER BY active DESC,run_date,run_time,id',(pid,))

def save_schedule(pid,d):
    kind=str(d.get('kind') or 'status_text')
    if kind not in ('status_text','status_image','status_video'):
        kind='status_text'
    recurrence=str(d.get('recurrence') or 'once')
    if recurrence not in ('once','daily'):
        recurrence='once'
    try:
        media_id=int(d.get('media_id') or 0)
    except Exception:
        media_id=0
    vals=(
        kind,
        str(d.get('run_date') or ''),
        str(d.get('run_time') or '12:00'),
        recurrence,
        str(d.get('text') or ''),
        media_id,
        1 if d.get('active',True) else 0,
    )
    if d.get('id'):
        x(
            'UPDATE schedules SET kind=?,run_date=?,run_time=?,recurrence=?,text=?,media_id=?,active=? '
            'WHERE id=? AND profile_id=?',
            vals+(int(d['id']),pid)
        )
        return int(d['id'])
    return x(
        'INSERT INTO schedules(profile_id,kind,run_date,run_time,recurrence,text,media_id,active) '
        'VALUES(?,?,?,?,?,?,?,?)',
        (pid,)+vals
    )

def delete_schedule(sid):
    x('DELETE FROM schedules WHERE id=?',(sid,))
'''
schedule_helpers = textwrap.dedent(schedule_helpers)
s, n = re.subn(
    r"def schedules_for\(pid\):.*?def delete_schedule\(sid\):\s*x\('DELETE FROM schedules WHERE id=\?',\(sid,\)\)",
    lambda _m: schedule_helpers.rstrip(),
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudieron actualizar las funciones de programación de estados")

# Real WhatsApp Status/Stories: send to status@broadcast.
status_helpers = r'''
def publish_whatsapp_status(pid, kind='status_text', text='', media_id=0):
    p=get_profile(pid)
    if not p:
        raise RuntimeError('Negocio no encontrado.')
    token=ENGINE.prepare(pid)
    kind=str(kind or 'status_text')
    text=str(text or '').strip()
    phone='status@broadcast'

    if kind=='status_text':
        if not text:
            raise RuntimeError('Escribe el texto del estado.')
        path='/chat/send/text'
        payload={'Phone':phone,'Body':text}
        timeout=90
    elif kind=='status_image':
        if not media_id:
            raise RuntimeError('Selecciona una imagen para el estado.')
        path='/chat/send/image'
        payload={
            'Phone':phone,
            'Image':media_data_uri(int(media_id),'image'),
            'Caption':text,
            'MimeType':media_mime(int(media_id)),
        }
        timeout=240
    elif kind=='status_video':
        if not media_id:
            raise RuntimeError('Selecciona un video para el estado.')
        path='/chat/send/video'
        payload={
            'Phone':phone,
            'Video':media_data_uri(int(media_id),'video'),
            'Caption':text,
            'MimeType':media_mime(int(media_id)),
        }
        timeout=420
    else:
        raise RuntimeError('Tipo de estado no compatible.')

    code,result=WUZ.call(token,'POST',path,payload,timeout)
    if code>=300 or (isinstance(result,dict) and result.get('success') is False):
        err=(result.get('error') if isinstance(result,dict) else str(result)) or str(result)
        raise RuntimeError(f'No se pudo publicar el estado: HTTP {code} · {err}')
    return result
'''
status_helpers = textwrap.dedent(status_helpers)
anchor = "def scheduler_loop():"
if "def publish_whatsapp_status" not in s:
    pos=s.find(anchor)
    if pos < 0:
        raise SystemExit("No se encontró scheduler_loop")
    s=s[:pos]+status_helpers+"\n\n"+s[pos:]

new_scheduler = r'''
def scheduler_loop():
    while ENGINE.running:
        try:
            now=datetime.now()
            today=now.strftime('%Y-%m-%d')
            hm=now.strftime('%H:%M')
            for item in q('SELECT * FROM schedules WHERE active=1'):
                due=False
                if item['recurrence']=='daily':
                    due=(hm>=item['run_time'] and item['last_run']!=today)
                else:
                    due=(item['run_date']<=today and hm>=item['run_time'] and item['last_run']!=today)
                if not due:
                    continue
                try:
                    publish_whatsapp_status(
                        item['profile_id'],
                        item.get('kind') or 'status_text',
                        item.get('text') or '',
                        int(item.get('media_id') or 0),
                    )
                    x(
                        'UPDATE schedules SET last_run=?,active=? WHERE id=?',
                        (today,1 if item['recurrence']=='daily' else 0,item['id'])
                    )
                    log(item['profile_id'],'info','Estado de WhatsApp publicado correctamente')
                except Exception as e:
                    log(item['profile_id'],'error',f'Error publicando estado de WhatsApp: {e}')
        except Exception as e:
            log('','error',f'Error en programador de estados: {e}')
        time.sleep(10)
'''
new_scheduler=textwrap.dedent(new_scheduler)
s, n = re.subn(
    r"def scheduler_loop\(\):.*?(?=\n\n\ndef start_services\(\):)",
    lambda _m:new_scheduler.rstrip(),
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo reemplazar scheduler_loop")

compile(s, str(core_path), "exec")
core_path.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
g = gui_path.read_text(encoding="utf-8")

# New imports needed for gallery thumbnails and calendar picker.
g = re.sub(
    r"^import [^\n]*tkinter as tk[^\n]*$",
    "import calendar, csv, json, os, re, threading, tkinter as tk, webbrowser",
    g,
    count=1,
    flags=re.M,
)
if "from datetime import datetime" not in g:
    g = g.replace("from pathlib import Path\n", "from pathlib import Path\nfrom datetime import datetime\n", 1)
if "from PIL import Image, ImageTk" not in g:
    g = g.replace("import core_local as C\n", "import core_local as C\nfrom PIL import Image, ImageTk\n", 1)

# Display labels. Internal values stay stable for rules/templates.
labels = r'''
ACTION_LABELS = {
    'text':'Texto',
    'image':'Imagen',
    'video':'Video',
    'audio':'Audio',
    'document':'Documento',
    'sticker':'Sticker',
    'location':'Ubicación',
    'contact':'Enviar contacto',
    'save_contact':'Guardar cliente',
    'buttons':'Botones',
    'list':'Lista de opciones',
}
ACTION_BY_LABEL = {v:k for k,v in ACTION_LABELS.items()}

MATCH_LABELS = {
    'exact':'Es exactamente',
    'contains':'Contiene',
    'starts':'Empieza por',
    'regex':'Expresión avanzada',
    'any':'Cualquier mensaje',
}
MATCH_BY_LABEL = {v:k for k,v in MATCH_LABELS.items()}

BUTTON_TYPE_LABELS = {
    'reply':'Respuesta',
    'cta_url':'Abrir enlace',
    'cta_call':'Llamar',
    'copy':'Copiar texto',
}
BUTTON_TYPE_BY_LABEL = {v:k for k,v in BUTTON_TYPE_LABELS.items()}

RECURRENCE_LABELS = {'once':'Una sola vez','daily':'Todos los días'}
RECURRENCE_BY_LABEL = {v:k for k,v in RECURRENCE_LABELS.items()}
STATUS_KIND_LABELS = {
    'status_text':'Solo texto',
    'status_image':'Imagen',
    'status_video':'Video',
}
STATUS_KIND_BY_LABEL = {v:k for k,v in STATUS_KIND_LABELS.items()}
SPANISH_MONTHS = (
    '', 'Enero','Febrero','Marzo','Abril','Mayo','Junio',
    'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'
)

def action_label(value):
    return ACTION_LABELS.get(str(value or ''), str(value or ''))

def match_label(value):
    return MATCH_LABELS.get(str(value or ''), str(value or ''))
'''
labels=textwrap.dedent(labels)
if "ACTION_LABELS = {" not in g:
    color_anchor="MUTED='#667085'\n"
    if color_anchor not in g:
        raise SystemExit("No se encontró ancla de colores para traducciones")
    g=g.replace(color_anchor,color_anchor+"\n"+labels+"\n",1)

# Fully localized option editor.
option_class = r'''
class OptionDialog(tk.Toplevel):
    def __init__(self,parent,kind,value=None):
        super().__init__(parent)
        self.result=None
        self.kind=kind
        self.title('Editar opción')
        self.transient(parent)
        self.grab_set()
        self.resizable(False,False)
        v=value or {}
        f=ttk.Frame(self,padding=18)
        f.pack(fill='both',expand=True)

        if kind=='button':
            ttk.Label(f,text='Qué hace el botón').grid(row=0,column=0,sticky='w',pady=5)
            internal=v.get('type','reply')
            self.type=tk.StringVar(value=BUTTON_TYPE_LABELS.get(internal,'Respuesta'))
            ttk.Combobox(
                f,textvariable=self.type,
                values=list(BUTTON_TYPE_LABELS.values()),
                state='readonly',width=28
            ).grid(row=0,column=1,pady=5)
            ttk.Label(f,text='Texto visible').grid(row=1,column=0,sticky='w',pady=5)
            self.titlev=tk.StringVar(value=v.get('title',''))
            ttk.Entry(f,textvariable=self.titlev,width=35).grid(row=1,column=1,pady=5)
            ttk.Label(f,text='Valor del botón').grid(row=2,column=0,sticky='w',pady=5)
            dest=v.get('id') or v.get('url') or v.get('phone_number') or v.get('copy_code') or ''
            self.dest=tk.StringVar(value=dest)
            ttk.Entry(f,textvariable=self.dest,width=35).grid(row=2,column=1,pady=5)
            ttk.Label(
                f,
                text='Para Respuesta escribe una palabra o código, por ejemplo VIDEOCLIP. '
                     'Para Abrir enlace pega la dirección web. Para Llamar escribe el número. '
                     'Para Copiar texto escribe lo que se copiará.',
                wraplength=430,foreground=MUTED
            ).grid(row=3,column=0,columnspan=2,sticky='w',pady=8)
        else:
            labels=[('Sección','section'),('Título','title'),('Código de la opción','id'),('Descripción','desc')]
            self.vars={}
            for i,(lab,key) in enumerate(labels):
                ttk.Label(f,text=lab).grid(row=i,column=0,sticky='w',pady=5)
                sv=tk.StringVar(value=v.get(key,''))
                self.vars[key]=sv
                ttk.Entry(f,textvariable=sv,width=42).grid(row=i,column=1,pady=5)

        b=ttk.Frame(f)
        b.grid(row=8,column=0,columnspan=2,pady=(15,0))
        ttk.Button(b,text='Guardar',command=self.save).pack(side='left',padx=5)
        ttk.Button(b,text='Cancelar',command=self.destroy).pack(side='left',padx=5)
        self.wait_window()

    def save(self):
        if self.kind=='button':
            typ=BUTTON_TYPE_BY_LABEL.get(self.type.get(),'reply')
            title=self.titlev.get().strip()
            dest=self.dest.get().strip()
            if not title:
                return messagebox.showwarning('Falta el texto','Escribe el texto visible del botón.',parent=self)
            d={'type':typ,'title':title}
            if typ=='reply':
                d['id']=dest or title
            elif typ=='cta_url':
                d['url']=dest
            elif typ=='cta_call':
                d['phone_number']=dest
            else:
                d['copy_code']=dest
            self.result=d
        else:
            self.result={k:v.get().strip() for k,v in self.vars.items()}
            if not self.result['title']:
                return messagebox.showwarning('Falta el título','Escribe el título de la opción.',parent=self)
            if not self.result['id']:
                self.result['id']=self.result['title'].upper().replace(' ','_')
        self.destroy()
'''
option_class=textwrap.dedent(option_class)
g, n = re.subn(
    r"class OptionDialog\(tk\.Toplevel\):.*?(?=\n\nclass ActionDialog\(tk\.Toplevel\):)",
    lambda _m:option_class.rstrip(),
    g,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo localizar OptionDialog")

# Fully localized action editor, preserving all internal action types.
action_class = r'''
class ActionDialog(tk.Toplevel):
    TYPES=['text','image','video','audio','document','sticker','location','contact','save_contact','buttons','list']

    def __init__(self,parent,value=None):
        super().__init__(parent)
        self.result=None
        self.v=value.copy() if value else {'type':'text','delay_ms':0}
        self.title('Editar acción')
        self.geometry('790x700')
        self.transient(parent)
        self.grab_set()

        root=ttk.Frame(self,padding=16)
        root.pack(fill='both',expand=True)
        top=ttk.Frame(root)
        top.pack(fill='x')

        ttk.Label(top,text='Tipo de acción').pack(side='left')
        current=self.v.get('type','text')
        self.type_label=tk.StringVar(value=ACTION_LABELS.get(current,'Texto'))
        cb=ttk.Combobox(
            top,textvariable=self.type_label,
            values=[ACTION_LABELS[x] for x in self.TYPES],
            state='readonly',width=22
        )
        cb.pack(side='left',padx=8)
        cb.bind('<<ComboboxSelected>>',lambda e:self.rebuild())

        ttk.Label(top,text='Esperar antes de enviar (segundos)').pack(side='left',padx=(20,5))
        ms=int(self.v.get('delay_ms') or 0)
        self.delay=tk.StringVar(value=f'{ms/1000:g}')
        ttk.Entry(top,textvariable=self.delay,width=8).pack(side='left')

        self.body=ttk.Frame(root)
        self.body.pack(fill='both',expand=True,pady=12)
        self.rebuild()

        foot=ttk.Frame(root)
        foot.pack(fill='x')
        ttk.Button(foot,text='GUARDAR ACCIÓN',command=self.save).pack(side='right',padx=5)
        ttk.Button(foot,text='Cancelar',command=self.destroy).pack(side='right')
        self.wait_window()

    def current_type(self):
        return ACTION_BY_LABEL.get(self.type_label.get(),'text')

    def media_values(self):
        return [f"{m['id']} | {m['name']}" for m in C.media_list()]

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _show_template_hint(self,key,label):
        value=str(self.v.get(key) or '').strip()
        if value:
            ttk.Label(
                self.body,
                text=f'{label}: {value}. Selecciona el archivo correcto de tu biblioteca.',
                foreground=MUTED,wraplength=700
            ).pack(anchor='w',pady=(0,6))

    def rebuild(self):
        self.clear()
        typ=self.current_type()
        self.widgets={}

        if typ in ('text','image','video','document','buttons','list'):
            label='Mensaje' if typ=='text' else 'Texto / pie de publicación'
            ttk.Label(self.body,text=label).pack(anchor='w')
            t=tk.Text(self.body,height=4,wrap='word')
            t.pack(fill='x',pady=(4,10))
            t.insert('1.0',self.v.get('text',self.v.get('caption','')))
            self.widgets['text']=t

        if typ in ('image','video','audio','document','sticker'):
            self._show_template_hint('template_media_name','Archivo sugerido por la plantilla')
            row=ttk.Frame(self.body)
            row.pack(fill='x',pady=4)
            ttk.Label(row,text='Archivo de la biblioteca',width=25).pack(side='left')
            sv=tk.StringVar()
            self.widgets['media']=sv
            vals=self.media_values()
            old=self.v.get('media_id')
            if old:
                sv.set(next((z for z in vals if z.startswith(str(old)+' | ')),''))
            ttk.Combobox(row,textvariable=sv,values=vals,state='readonly').pack(side='left',fill='x',expand=True)

            row2=ttk.Frame(self.body)
            row2.pack(fill='x',pady=4)
            ttk.Label(row2,text='Enlace externo (opcional)',width=25).pack(side='left')
            uv=tk.StringVar(value=self.v.get('url',''))
            self.widgets['url']=uv
            ttk.Entry(row2,textvariable=uv).pack(side='left',fill='x',expand=True)

        if typ=='document':
            r=ttk.Frame(self.body);r.pack(fill='x',pady=4)
            ttk.Label(r,text='Nombre que verá el cliente',width=25).pack(side='left')
            sv=tk.StringVar(value=self.v.get('file_name','archivo'))
            self.widgets['file_name']=sv
            ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

        if typ=='location':
            for lab,key in [('Nombre del lugar','name'),('Latitud','lat'),('Longitud','lng')]:
                r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
                ttk.Label(r,text=lab,width=25).pack(side='left')
                sv=tk.StringVar(value=str(self.v.get(key,'')))
                self.widgets[key]=sv
                ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

        if typ=='contact':
            for lab,key in [('Nombre','name'),('Número de teléfono','number')]:
                r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
                ttk.Label(r,text=lab,width=25).pack(side='left')
                sv=tk.StringVar(value=str(self.v.get(key,'')))
                self.widgets[key]=sv
                ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

        if typ=='save_contact':
            ttk.Label(
                self.body,text='GUARDAR CLIENTE',font=('Segoe UI',11,'bold')
            ).pack(anchor='w',pady=(2,8))
            ttk.Label(
                self.body,
                text='Cuando esta regla coincida, el número del cliente se guardará en Contactos. '
                     'Si ya existe, se omite y no se modifica. Si Google Contacts está conectado, '
                     'solo los contactos nuevos se sincronizan.',
                wraplength=700,foreground=MUTED
            ).pack(anchor='w',pady=(0,12))
            for lab,key,default in [
                ('Nombre a guardar','contact_name','@nombre'),
                ('Etiqueta','label','Cliente'),
            ]:
                r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
                ttk.Label(r,text=lab,width=25).pack(side='left')
                sv=tk.StringVar(value=str(self.v.get(key,default)))
                self.widgets[key]=sv
                ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)
            ttk.Label(self.body,text='Nota (opcional)').pack(anchor='w',pady=(12,3))
            nt=tk.Text(self.body,height=5,wrap='word')
            nt.pack(fill='x')
            nt.insert('1.0',self.v.get('note',''))
            self.widgets['note']=nt
            ttk.Label(
                self.body,
                text='Variables disponibles: @nombre, @telefono, @mensaje, @hora, @dia, @fecha_completa.',
                foreground=MUTED
            ).pack(anchor='w',pady=8)

        if typ in ('buttons','list'):
            for lab,key in [('Título','title'),('Pie del mensaje','footer')]:
                r=ttk.Frame(self.body);r.pack(fill='x',pady=4)
                ttk.Label(r,text=lab,width=25).pack(side='left')
                sv=tk.StringVar(value=self.v.get(key,''))
                self.widgets[key]=sv
                ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

        if typ=='buttons':
            self._show_template_hint('template_image_name','Imagen sugerida por la plantilla')
            r=ttk.Frame(self.body);r.pack(fill='x',pady=4)
            ttk.Label(r,text='Imagen de cabecera',width=25).pack(side='left')
            sv=tk.StringVar();self.widgets['image_media']=sv
            vals=self.media_values();old=self.v.get('image_media_id')
            sv.set(next((z for z in vals if old and z.startswith(str(old)+' | ')),''))
            ttk.Combobox(r,textvariable=sv,values=vals,state='readonly').pack(side='left',fill='x',expand=True)
            self.options=[dict(b) for b in self.v.get('buttons',[])]
            self.build_option_table('button')

        if typ=='list':
            r=ttk.Frame(self.body);r.pack(fill='x',pady=4)
            ttk.Label(r,text='Texto del botón',width=25).pack(side='left')
            sv=tk.StringVar(value=self.v.get('button_text','Ver opciones'))
            self.widgets['button_text']=sv
            ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)
            self.options=[]
            for sec in self.v.get('sections',[]):
                st=sec.get('title','')
                for row in sec.get('rows',[]):
                    self.options.append({
                        'section':st,
                        'title':row.get('title',''),
                        'id':row.get('RowId') or row.get('RowID') or row.get('rowId') or row.get('title',''),
                        'desc':row.get('desc','')
                    })
            self.build_option_table('list')

    def build_option_table(self,kind):
        title='Botones editables' if kind=='button' else 'Opciones de la lista'
        box=ttk.LabelFrame(self.body,text=title,padding=8)
        box.pack(fill='both',expand=True,pady=10)
        cols=('a','b','c','d') if kind=='list' else ('a','b','c')
        self.opt_tree=ttk.Treeview(box,columns=cols,show='headings',height=8)
        heads=('Acción','Texto','Valor') if kind=='button' else ('Sección','Título','Código','Descripción')
        for col,h in zip(cols,heads):
            self.opt_tree.heading(col,text=h)
            self.opt_tree.column(col,width=130 if col!='d' else 220)
        self.opt_tree.pack(fill='both',expand=True)
        b=ttk.Frame(box);b.pack(fill='x',pady=(7,0))
        ttk.Button(b,text='+ Agregar',command=lambda:self.opt_add(kind)).pack(side='left')
        ttk.Button(b,text='Editar',command=lambda:self.opt_edit(kind)).pack(side='left',padx=5)
        ttk.Button(b,text='Eliminar',command=self.opt_delete).pack(side='left')
        self.opt_refresh(kind)

    def opt_refresh(self,kind):
        for i in self.opt_tree.get_children():
            self.opt_tree.delete(i)
        for idx,o in enumerate(self.options):
            if kind=='button':
                dest=o.get('id') or o.get('url') or o.get('phone_number') or o.get('copy_code') or ''
                vals=(BUTTON_TYPE_LABELS.get(o.get('type','reply'),'Respuesta'),o.get('title',''),dest)
            else:
                vals=(o.get('section',''),o.get('title',''),o.get('id',''),o.get('desc',''))
            self.opt_tree.insert('', 'end', iid=str(idx), values=vals)

    def opt_add(self,kind):
        d=OptionDialog(self,kind)
        if d.result:
            self.options.append(d.result)
            self.opt_refresh(kind)

    def opt_edit(self,kind):
        sel=self.opt_tree.selection()
        if not sel:return
        idx=int(sel[0])
        d=OptionDialog(self,kind,self.options[idx])
        if d.result:
            self.options[idx]=d.result
            self.opt_refresh(kind)

    def opt_delete(self):
        sel=self.opt_tree.selection()
        if sel:
            self.options.pop(int(sel[0]))
            self.opt_refresh('button' if self.current_type()=='buttons' else 'list')

    def save(self):
        typ=self.current_type()
        d={'type':typ}
        try:
            seconds=float((self.delay.get() or '0').replace(',','.'))
            d['delay_ms']=max(0,int(seconds*1000))
        except Exception:
            d['delay_ms']=0

        for k,w in self.widgets.items():
            if isinstance(w,tk.Text):
                d[k]=w.get('1.0','end').strip()
            else:
                d[k]=w.get().strip()

        if 'media' in d:
            m=d.pop('media')
            if m:d['media_id']=int(m.split('|',1)[0].strip())
        if 'image_media' in d:
            m=d.pop('image_media')
            if m:d['image_media_id']=int(m.split('|',1)[0].strip())

        if typ=='buttons':
            d['buttons']=self.options
        if typ=='list':
            sections=[]
            for o in self.options:
                sec=next((s for s in sections if s['title']==o.get('section','')),None)
                if not sec:
                    sec={'title':o.get('section',''),'rows':[]}
                    sections.append(sec)
                sec['rows'].append({
                    'title':o.get('title',''),
                    'RowId':o.get('id') or o.get('title',''),
                    'desc':o.get('desc','')
                })
            d['sections']=sections

        self.result=d
        self.destroy()
'''
action_class=textwrap.dedent(action_class)
g, n = re.subn(
    r"class ActionDialog\(tk\.Toplevel\):.*?(?=\n\nclass RuleDialog\(tk\.Toplevel\):)",
    lambda _m:action_class.rstrip(),
    g,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo localizar ActionDialog")

rule_class = r'''
class RuleDialog(tk.Toplevel):
    def __init__(self,parent,pid,value=None):
        super().__init__(parent)
        self.result=None
        self.pid=pid
        self.v=value or {}
        self.actions=[dict(a) for a in self.v.get('actions',[])]
        self.title('Editar regla')
        self.geometry('920x720')
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

        box=ttk.LabelFrame(root,text='Secuencia de acciones',padding=8)
        box.pack(fill='both',expand=True,pady=10)
        self.tree=ttk.Treeview(box,columns=('tipo','resumen'),show='headings')
        self.tree.heading('tipo',text='Acción')
        self.tree.heading('resumen',text='Detalle')
        self.tree.column('tipo',width=150)
        self.tree.column('resumen',width=610)
        self.tree.pack(fill='both',expand=True)

        b=ttk.Frame(box);b.pack(fill='x',pady=7)
        ttk.Button(b,text='+ Agregar acción',command=self.add_action).pack(side='left')
        ttk.Button(b,text='Editar',command=self.edit_action).pack(side='left',padx=5)
        ttk.Button(b,text='Eliminar',command=self.del_action).pack(side='left')
        ttk.Button(b,text='Subir',command=lambda:self.move(-1)).pack(side='left',padx=(18,3))
        ttk.Button(b,text='Bajar',command=lambda:self.move(1)).pack(side='left')

        foot=ttk.Frame(root);foot.pack(fill='x')
        ttk.Button(foot,text='GUARDAR REGLA',command=self.save).pack(side='right',padx=5)
        ttk.Button(foot,text='Cancelar',command=self.destroy).pack(side='right')
        self.refresh()
        self.wait_window()

    def summary(self,a):
        t=a.get('type','')
        if t=='save_contact':
            return f"Guardar cliente · {a.get('contact_name') or '@nombre'} · {a.get('label') or 'Cliente'}"
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
g, n = re.subn(
    r"class RuleDialog\(tk\.Toplevel\):.*?(?=\n\nclass App\(tk\.Tk\):)",
    lambda _m:rule_class.rstrip(),
    g,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo localizar RuleDialog")

# Local file library with list/gallery switch.
media_methods = r'''
    def build_media(self):
        f=self.tabs['Archivos']
        ttk.Label(f,text='Biblioteca local de archivos',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(
            f,
            text='Los archivos quedan guardados en esta PC. Puedes verlos como lista o con miniaturas. '
                 'Las imágenes muestran una vista previa; videos, audios y documentos muestran una tarjeta con su tipo.',
            wraplength=980,foreground=MUTED
        ).pack(anchor='w',pady=(2,8))

        tools=ttk.Frame(f);tools.pack(fill='x',pady=(4,6))
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

        self.media_area=ttk.Frame(f)
        self.media_area.pack(fill='both',expand=True)

        self.media_tree=ttk.Treeview(
            self.media_area,columns=('name','type','size','path'),show='headings'
        )
        for col,head,width in [
            ('name','Archivo',280),('type','Tipo',110),('size','Tamaño',90),('path','Ubicación local',560)
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
            lambda e:self.media_gallery_canvas.itemconfigure(self.media_gallery_window,width=e.width)
        )
        self.media_gallery_canvas.pack(side='left',fill='both',expand=True)
        self.media_gallery_scroll.pack(side='right',fill='y')

        self.media_selected=set()
        self.media_checks={}
        self.media_photo_refs=[]
        self.refresh_media()
        self.set_media_view()

    def media_file_type(self,path):
        ext=Path(path).suffix.lower()
        if ext in ('.jpg','.jpeg','.png','.webp','.gif','.bmp'):
            return 'Imagen'
        if ext in ('.mp4','.mov','.m4v','.webm','.avi','.mkv'):
            return 'Video'
        if ext in ('.mp3','.wav','.m4a','.ogg','.aac','.flac'):
            return 'Audio'
        if ext=='.pdf':
            return 'PDF'
        return 'Documento'

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
                values=(m['name'],self.media_file_type(m['path']),human_size(m['size']),m['path'])
            )
        if hasattr(self,'media_gallery_inner'):
            self.refresh_media_gallery()

    def refresh_media_gallery(self):
        if not hasattr(self,'media_gallery_inner'):
            return
        for w in self.media_gallery_inner.winfo_children():
            w.destroy()
        self.media_photo_refs=[]
        self.media_checks={}
        valid_ids={int(m['id']) for m in C.media_list()}
        self.media_selected.intersection_update(valid_ids)

        for idx,m in enumerate(C.media_list()):
            mid=int(m['id'])
            card=ttk.Frame(self.media_gallery_inner,padding=8,relief='solid',borderwidth=1)
            card.grid(row=idx//4,column=idx%4,sticky='nsew',padx=6,pady=6)
            self.media_gallery_inner.columnconfigure(idx%4,weight=1)

            preview=ttk.Frame(card,width=170,height=110)
            preview.pack(fill='x')
            preview.pack_propagate(False)
            typ=self.media_file_type(m['path'])
            photo=None
            if typ=='Imagen':
                try:
                    with Image.open(m['path']) as im:
                        im=im.convert('RGB')
                        im.thumbnail((165,105))
                        photo=ImageTk.PhotoImage(im.copy())
                    self.media_photo_refs.append(photo)
                except Exception:
                    photo=None
            if photo:
                ttk.Label(preview,image=photo).pack(expand=True)
            else:
                ttk.Label(
                    preview,text=f'[{typ.upper()}]',anchor='center',
                    font=('Segoe UI',12,'bold')
                ).pack(fill='both',expand=True)

            ttk.Label(card,text=m['name'],wraplength=165).pack(anchor='w',pady=(6,1))
            ttk.Label(card,text=human_size(m['size']),foreground=MUTED).pack(anchor='w')
            var=tk.BooleanVar(value=mid in self.media_selected)
            self.media_checks[mid]=var
            ttk.Checkbutton(
                card,text='Seleccionar',variable=var,
                command=lambda x=mid,v=var:self.toggle_media_selection(x,v)
            ).pack(anchor='w',pady=(5,0))

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
        for mid in ids:
            C.delete_media(mid)
        self.media_selected.difference_update(ids)
        self.refresh_media()
'''
media_methods=textwrap.dedent(media_methods)
media_methods=textwrap.indent(media_methods,"    ")
g, n = re.subn(
    r"    def build_media\(self\):.*?(?=\n    def refresh_google_contacts_status\(self\):|\n    def build_contacts\(self\):)",
    lambda _m:media_methods.rstrip(),
    g,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo reemplazar la biblioteca de archivos")

# Interactive date picker + real WhatsApp Status scheduling.
status_methods = r'''
    def pick_date_dialog(self,initial=''):
        try:
            current=datetime.strptime(initial,'%Y-%m-%d')
        except Exception:
            current=datetime.now()
        state={'year':current.year,'month':current.month,'value':None}

        win=tk.Toplevel(self)
        win.title('Escoger fecha')
        win.transient(self)
        win.grab_set()
        win.resizable(False,False)
        root=ttk.Frame(win,padding=14)
        root.pack(fill='both',expand=True)

        title=tk.StringVar()
        head=ttk.Frame(root);head.pack(fill='x')
        ttk.Button(head,text='‹',width=4).pack(side='left')
        prev=head.winfo_children()[-1]
        ttk.Label(head,textvariable=title,font=('Segoe UI',11,'bold')).pack(side='left',expand=True)
        ttk.Button(head,text='›',width=4).pack(side='right')
        nxt=head.winfo_children()[-1]

        grid=ttk.Frame(root);grid.pack(pady=(10,0))
        for col,name in enumerate(('Lun','Mar','Mié','Jue','Vie','Sáb','Dom')):
            ttk.Label(grid,text=name,width=5,anchor='center').grid(row=0,column=col,padx=1,pady=2)

        day_buttons=[]

        def render():
            for b in day_buttons:
                b.destroy()
            day_buttons.clear()
            title.set(f"{SPANISH_MONTHS[state['month']]} {state['year']}")
            weeks=calendar.Calendar(firstweekday=0).monthdayscalendar(state['year'],state['month'])
            for r,week in enumerate(weeks,1):
                for col,day in enumerate(week):
                    if not day:
                        ttk.Label(grid,text='',width=5).grid(row=r,column=col,padx=1,pady=1)
                        continue
                    b=ttk.Button(
                        grid,text=str(day),width=4,
                        command=lambda d=day:choose(d)
                    )
                    b.grid(row=r,column=col,padx=1,pady=1)
                    day_buttons.append(b)

        def move(delta):
            month=state['month']+delta
            year=state['year']
            if month<1:
                month=12;year-=1
            elif month>12:
                month=1;year+=1
            state['month']=month;state['year']=year
            for w in grid.grid_slaves():
                info=w.grid_info()
                if int(info.get('row',0))>0:
                    w.destroy()
            day_buttons.clear()
            render()

        def choose(day):
            state['value']=f"{state['year']:04d}-{state['month']:02d}-{day:02d}"
            win.destroy()

        prev.configure(command=lambda:move(-1))
        nxt.configure(command=lambda:move(1))
        render()
        ttk.Button(root,text='Cancelar',command=win.destroy).pack(anchor='e',pady=(10,0))
        win.wait_window()
        return state['value']

    def build_status(self):
        f=self.tabs['Estados']
        ttk.Label(f,text='Estados de WhatsApp programados',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(
            f,
            text='Programa publicaciones reales en Estados de WhatsApp: texto, imagen o video. '
                 'Las imágenes y videos pueden llevar un pie de publicación.',
            wraplength=980,foreground=MUTED
        ).pack(anchor='w',pady=(2,8))

        cols=('type','date','time','rec','content','active')
        self.status_tree=ttk.Treeview(f,columns=cols,show='headings')
        for col,head,width in [
            ('type','Tipo',105),('date','Fecha',105),('time','Hora',75),
            ('rec','Repetición',120),('content','Contenido',490),('active','Activo',65)
        ]:
            self.status_tree.heading(col,text=head)
            self.status_tree.column(col,width=width)
        self.status_tree.pack(fill='both',expand=True,pady=12)

        b=ttk.Frame(f);b.pack(fill='x')
        ttk.Button(b,text='+ Programar estado',command=self.add_status).pack(side='left')
        ttk.Button(b,text='Editar',command=self.edit_status).pack(side='left',padx=5)
        ttk.Button(b,text='Publicar ahora',command=self.publish_status_now).pack(side='left')
        ttk.Button(b,text='Eliminar',command=self.del_status).pack(side='right')

    def _status_media_name(self,media_id):
        if not media_id:return ''
        try:
            return C.media_name(int(media_id))
        except Exception:
            return 'Archivo no disponible'

    def refresh_status(self):
        if not hasattr(self,'status_tree'):
            return
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        pid=self.pid()
        if not pid:return

        for item in C.schedules_for(pid):
            date=item.get('run_date') or ''
            try:
                date_show=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                date_show=date
            kind=item.get('kind') or 'status_text'
            text=(item.get('text') or '').strip()
            media_name=self._status_media_name(item.get('media_id') or 0)
            if kind=='status_text':
                content=text
            else:
                content=media_name + (f' · {text}' if text else '')
            self.status_tree.insert(
                '', 'end', iid=str(item['id']),
                values=(
                    STATUS_KIND_LABELS.get(kind,kind),
                    date_show,
                    item.get('run_time') or '',
                    RECURRENCE_LABELS.get(item.get('recurrence') or 'once','Una sola vez'),
                    content[:180],
                    'Sí' if item.get('active') else 'No'
                )
            )

    def status_dialog(self,val=None):
        v=val or {}
        win=tk.Toplevel(self)
        win.title('Programar estado de WhatsApp')
        win.transient(self)
        win.grab_set()
        win.resizable(False,False)
        f=ttk.Frame(win,padding=18)
        f.pack(fill='both',expand=True)

        kind_internal=v.get('kind') or 'status_text'
        kind=tk.StringVar(value=STATUS_KIND_LABELS.get(kind_internal,'Solo texto'))
        date=tk.StringVar(value=v.get('run_date') or datetime.now().strftime('%Y-%m-%d'))

        current_time=v.get('run_time') or datetime.now().strftime('%H:%M')
        try:
            hh,mm=current_time.split(':',1)
        except Exception:
            hh,mm='12','00'
        hour=tk.StringVar(value=hh)
        minute=tk.StringVar(value=mm)

        rec=tk.StringVar(value=RECURRENCE_LABELS.get(v.get('recurrence') or 'once','Una sola vez'))
        active=tk.BooleanVar(value=bool(v.get('active',1)))

        ttk.Label(f,text='Tipo de publicación').grid(row=0,column=0,sticky='w',pady=6)
        kind_cb=ttk.Combobox(
            f,textvariable=kind,values=list(STATUS_KIND_LABELS.values()),
            state='readonly',width=28
        )
        kind_cb.grid(row=0,column=1,columnspan=2,sticky='ew',pady=6)

        ttk.Label(f,text='Fecha').grid(row=1,column=0,sticky='w',pady=6)
        date_entry=ttk.Entry(f,textvariable=date,state='readonly',width=20)
        date_entry.grid(row=1,column=1,sticky='ew',pady=6)
        def choose_date():
            selected=self.pick_date_dialog(date.get())
            if selected:date.set(selected)
        ttk.Button(f,text='Escoger fecha',command=choose_date).grid(row=1,column=2,padx=(6,0),pady=6)

        ttk.Label(f,text='Hora').grid(row=2,column=0,sticky='w',pady=6)
        time_box=ttk.Frame(f);time_box.grid(row=2,column=1,columnspan=2,sticky='w',pady=6)
        ttk.Spinbox(time_box,from_=0,to=23,textvariable=hour,width=5,format='%02.0f').pack(side='left')
        ttk.Label(time_box,text=':').pack(side='left',padx=3)
        ttk.Spinbox(time_box,from_=0,to=59,textvariable=minute,width=5,format='%02.0f').pack(side='left')

        ttk.Label(f,text='Repetición').grid(row=3,column=0,sticky='w',pady=6)
        ttk.Combobox(
            f,textvariable=rec,values=list(RECURRENCE_LABELS.values()),
            state='readonly',width=28
        ).grid(row=3,column=1,columnspan=2,sticky='ew',pady=6)

        ttk.Label(f,text='Archivo').grid(row=4,column=0,sticky='w',pady=6)
        media=tk.StringVar()
        media_values=[f"{m['id']} | {m['name']}" for m in C.media_list()]
        old_mid=int(v.get('media_id') or 0)
        if old_mid:
            media.set(next((x for x in media_values if x.startswith(str(old_mid)+' | ')),''))
        media_cb=ttk.Combobox(f,textvariable=media,values=media_values,state='readonly',width=48)
        media_cb.grid(row=4,column=1,columnspan=2,sticky='ew',pady=6)

        text_label=ttk.Label(f,text='Texto')
        text_label.grid(row=5,column=0,sticky='nw',pady=6)
        txt=tk.Text(f,width=55,height=7,wrap='word')
        txt.grid(row=5,column=1,columnspan=2,pady=6)
        txt.insert('1.0',v.get('text',''))

        ttk.Checkbutton(f,text='Programación activa',variable=active).grid(
            row=6,column=1,columnspan=2,sticky='w',pady=(5,10)
        )

        def update_kind(*_):
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            if internal=='status_text':
                media_cb.configure(state='disabled')
                text_label.configure(text='Texto del estado')
            else:
                media_cb.configure(state='readonly')
                text_label.configure(text='Pie de publicación (opcional)')
        kind_cb.bind('<<ComboboxSelected>>',update_kind)
        update_kind()

        out={}
        def save():
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            try:
                h=max(0,min(23,int(hour.get())))
                m=max(0,min(59,int(minute.get())))
            except Exception:
                return messagebox.showwarning('Hora inválida','Escoge una hora válida.',parent=win)
            media_id=0
            if media.get():
                try:media_id=int(media.get().split('|',1)[0].strip())
                except Exception:media_id=0
            body=txt.get('1.0','end').strip()
            if internal=='status_text' and not body:
                return messagebox.showwarning('Falta el texto','Escribe el texto del estado.',parent=win)
            if internal in ('status_image','status_video') and not media_id:
                return messagebox.showwarning('Falta el archivo','Selecciona una imagen o video de la biblioteca.',parent=win)

            # Validate media type early.
            if media_id:
                try:
                    mime=C.media_mime(media_id)
                    if internal=='status_image' and not mime.startswith('image/'):
                        return messagebox.showwarning('Archivo incorrecto','Selecciona una imagen para este estado.',parent=win)
                    if internal=='status_video' and not mime.startswith('video/'):
                        return messagebox.showwarning('Archivo incorrecto','Selecciona un video para este estado.',parent=win)
                except Exception as e:
                    return messagebox.showwarning('Archivo',str(e),parent=win)

            out.update({
                'id':v.get('id'),
                'kind':internal,
                'run_date':date.get().strip(),
                'run_time':f'{h:02d}:{m:02d}',
                'recurrence':RECURRENCE_BY_LABEL.get(rec.get(),'once'),
                'text':body,
                'media_id':media_id,
                'active':active.get(),
            })
            win.destroy()

        buttons=ttk.Frame(f);buttons.grid(row=7,column=0,columnspan=3,sticky='e',pady=(6,0))
        ttk.Button(buttons,text='Cancelar',command=win.destroy).pack(side='right',padx=(5,0))
        ttk.Button(buttons,text='Guardar programación',command=save).pack(side='right')
        win.wait_window()
        return out or None

    def add_status(self):
        d=self.status_dialog()
        if d:
            C.save_schedule(self.pid(),d)
            self.refresh_status()

    def edit_status(self):
        selected=self.status_tree.selection()
        if not selected:return
        sid=int(selected[0])
        value=next((x for x in C.schedules_for(self.pid()) if int(x['id'])==sid),None)
        d=self.status_dialog(value)
        if d:
            C.save_schedule(self.pid(),d)
            self.refresh_status()

    def publish_status_now(self):
        selected=self.status_tree.selection()
        if not selected:
            return messagebox.showinfo('Estados','Selecciona una publicación.',parent=self)
        sid=int(selected[0])
        item=next((x for x in C.schedules_for(self.pid()) if int(x['id'])==sid),None)
        if not item:return
        def worker():
            C.publish_whatsapp_status(
                self.pid(),
                item.get('kind') or 'status_text',
                item.get('text') or '',
                int(item.get('media_id') or 0),
            )
            return True
        bgcall(
            worker,
            lambda _r:messagebox.showinfo('Estados','Estado publicado correctamente.',parent=self),
            lambda e:messagebox.showerror('Estados',str(e),parent=self)
        )

    def del_status(self):
        selected=self.status_tree.selection()
        if not selected:return
        if messagebox.askyesno('Eliminar publicación','¿Eliminar esta publicación programada?',parent=self):
            C.delete_schedule(int(selected[0]))
            self.refresh_status()
'''
status_methods=textwrap.dedent(status_methods)
status_methods=textwrap.indent(status_methods,"    ")
g, n = re.subn(
    r"    def build_status\(self\):.*?(?=\n    def build_logs\(self\):)",
    lambda _m:status_methods.rstrip(),
    g,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No se pudo reemplazar la sección de Estados")

# Easy Colombian Spanish in a few remaining visible labels.
g=g.replace("Desconectar socket","Desconectar conexión")
g=g.replace("Panel local","Panel principal")
g=g.replace("Arquitectura local","Funcionamiento del programa")
g=g.replace(
    "Todo funciona en esta PC. Reglas, archivos y respuestas se procesan localmente para reducir la latencia. "
    "WuzAPI solo escucha en 127.0.0.1 y no se publica en Internet.",
    "El bot funciona directamente en esta PC. Las reglas, los archivos y las respuestas se procesan aquí para responder más rápido."
)

# Repair any mojibake introduced by earlier PowerShell-generated patch files.
mojibake = {
    "\u00c3\u00a1":"\u00e1", "\u00c3\u00a9":"\u00e9", "\u00c3\u00ad":"\u00ed",
    "\u00c3\u00b3":"\u00f3", "\u00c3\u00ba":"\u00fa", "\u00c3\u00b1":"\u00f1",
    "\u00c3\u0081":"\u00c1", "\u00c3\u0089":"\u00c9", "\u00c3\u008d":"\u00cd",
    "\u00c3\u0093":"\u00d3", "\u00c3\u009a":"\u00da", "\u00c3\u0091":"\u00d1",
    "\u00c2\u00bf":"\u00bf", "\u00c2\u00a1":"\u00a1", "\u00c2\u00b7":"\u00b7",
    "\u00e2\u0080\u00a6":"\u2026", "\u00e2\u0080\u009c":"\u201c",
    "\u00e2\u0080\u009d":"\u201d", "\u00e2\u0080\u0093":"\u2013",
}
for bad,good in mojibake.items():
    g=g.replace(bad,good)

compile(g, str(gui_path), "exec")
gui_path.write_text(g, encoding="utf-8")

# Installer version.
t=iss_path.read_text(encoding="utf-8")
t=t.replace("2.0.9","2.1.1")
iss_path.write_text(t,encoding="utf-8")
