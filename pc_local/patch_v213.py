import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

# ---------------- CORE v2.1.3 ----------------
s=core_path.read_text(encoding="utf-8")
s=s.replace("APP_VERSION = '2.1.2'","APP_VERSION = '2.1.3'")

# Weekday selection for scheduled statuses.
migration_anchor="ensure_schedule_media_columns()\n"
migration_code=r'''
ensure_schedule_media_columns()

def ensure_schedule_weekday_columns():
    with DB_LOCK, db() as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(schedules)').fetchall()}
        if 'weekdays' not in cols:
            con.execute("ALTER TABLE schedules ADD COLUMN weekdays TEXT NOT NULL DEFAULT ''")
        con.commit()

ensure_schedule_weekday_columns()
'''
migration_code=textwrap.dedent(migration_code)
if "def ensure_schedule_weekday_columns" not in s:
    if migration_anchor not in s:
        raise SystemExit("No se encontró la migración de estados")
    s=s.replace(migration_anchor,migration_code,1)

save_schedule=r'''
def save_schedule(pid,d):
    kind=str(d.get('kind') or 'status_text')
    if kind not in ('status_text','status_image','status_video'):
        kind='status_text'
    recurrence=str(d.get('recurrence') or 'once')
    if recurrence not in ('once','daily','weekdays'):
        recurrence='once'
    try:
        media_id=int(d.get('media_id') or 0)
    except Exception:
        media_id=0
    weekdays=str(d.get('weekdays') or '').strip()
    vals=(
        kind,
        str(d.get('run_date') or ''),
        str(d.get('run_time') or '12:00'),
        recurrence,
        str(d.get('text') or ''),
        media_id,
        weekdays,
        1 if d.get('active',True) else 0,
    )
    if d.get('id'):
        x(
            'UPDATE schedules SET kind=?,run_date=?,run_time=?,recurrence=?,text=?,media_id=?,weekdays=?,active=? '
            'WHERE id=? AND profile_id=?',
            vals+(int(d['id']),pid)
        )
        return int(d['id'])
    return x(
        'INSERT INTO schedules(profile_id,kind,run_date,run_time,recurrence,text,media_id,weekdays,active) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (pid,)+vals
    )
'''
save_schedule=textwrap.dedent(save_schedule)
s,n=re.subn(
    r"def save_schedule\(pid,d\):.*?(?=\n\ndef delete_schedule\(sid\):)",
    lambda _m:save_schedule.rstrip(),
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar save_schedule")

new_scheduler=r'''
def scheduler_loop():
    while ENGINE.running:
        try:
            now=datetime.now()
            today=now.strftime('%Y-%m-%d')
            hm=now.strftime('%H:%M')
            weekday=str(now.weekday())  # lunes=0 ... domingo=6

            for item in q('SELECT * FROM schedules WHERE active=1'):
                recurrence=item.get('recurrence') or 'once'
                last_run=item.get('last_run') or ''
                start_date=item.get('run_date') or ''
                due=False

                if recurrence=='daily':
                    due=(hm>=item['run_time'] and last_run!=today)
                elif recurrence=='weekdays':
                    selected={x.strip() for x in str(item.get('weekdays') or '').split(',') if x.strip()}
                    date_ok=(not start_date) or (start_date<=today)
                    due=(weekday in selected and date_ok and hm>=item['run_time'] and last_run!=today)
                else:
                    due=((not start_date or start_date<=today) and hm>=item['run_time'] and last_run!=today)

                if not due:
                    continue

                try:
                    publish_whatsapp_status(
                        item['profile_id'],
                        item.get('kind') or 'status_text',
                        item.get('text') or '',
                        int(item.get('media_id') or 0),
                    )
                    keep_active=1 if recurrence in ('daily','weekdays') else 0
                    x(
                        'UPDATE schedules SET last_run=?,active=? WHERE id=?',
                        (today,keep_active,item['id'])
                    )
                    log(item['profile_id'],'info','Estado de WhatsApp publicado correctamente')
                except Exception as e:
                    log(item['profile_id'],'error',f'Error publicando estado de WhatsApp: {e}')
        except Exception as e:
            log('','error',f'Error en programador de estados: {e}')
        time.sleep(10)
'''
new_scheduler=textwrap.dedent(new_scheduler)
s,n=re.subn(
    r"def scheduler_loop\(\):.*?(?=\n\n\ndef start_services\(\):)",
    lambda _m:new_scheduler.rstrip(),
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar scheduler_loop")

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# ---------------- GUI v2.1.3 ----------------
g=gui_path.read_text(encoding="utf-8")

# Fix Tk font family with spaces.
g=g.replace("self.option_add('*Font','Segoe UI 10')","self.option_add('*Font','{Segoe UI} 10')")

# Recurrence labels.
g=g.replace(
    "RECURRENCE_LABELS = {'once':'Una sola vez','daily':'Todos los días'}",
    "RECURRENCE_LABELS = {'once':'Una sola vez','daily':'Todos los días','weekdays':'Días seleccionados'}"
)
g=g.replace(
    "RECURRENCE_BY_LABEL = {v:k for k,v in RECURRENCE_LABELS.items()}",
    "RECURRENCE_BY_LABEL = {v:k for k,v in RECURRENCE_LABELS.items()}"
)

# Replace refresh_status and status_dialog with weekday-aware versions.
status_block=r'''
    def _weekday_summary(self,value):
        names=['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']
        selected=[]
        for part in str(value or '').split(','):
            part=part.strip()
            if part.isdigit():
                i=int(part)
                if 0<=i<7:
                    selected.append(names[i])
        return ', '.join(selected)

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

            recurrence=item.get('recurrence') or 'once'
            if recurrence=='weekdays':
                rec_show=self._weekday_summary(item.get('weekdays') or '') or 'Días seleccionados'
            else:
                rec_show=RECURRENCE_LABELS.get(recurrence,'Una sola vez')

            self.status_tree.insert(
                '', 'end', iid=str(item['id']),
                values=(
                    STATUS_KIND_LABELS.get(kind,kind),
                    date_show,
                    item.get('run_time') or '',
                    rec_show,
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
            state='readonly',width=30
        )
        kind_cb.grid(row=0,column=1,columnspan=2,sticky='ew',pady=6)

        ttk.Label(f,text='Fecha de inicio').grid(row=1,column=0,sticky='w',pady=6)
        date_entry=ttk.Entry(f,textvariable=date,state='readonly',width=20)
        date_entry.grid(row=1,column=1,sticky='ew',pady=6)
        def choose_date():
            selected=self.pick_date_dialog(date.get())
            if selected:
                date.set(selected)
        ttk.Button(f,text='Escoger fecha',command=choose_date).grid(row=1,column=2,padx=(6,0),pady=6)

        ttk.Label(f,text='Hora').grid(row=2,column=0,sticky='w',pady=6)
        time_box=ttk.Frame(f)
        time_box.grid(row=2,column=1,columnspan=2,sticky='w',pady=6)
        ttk.Spinbox(time_box,from_=0,to=23,textvariable=hour,width=5,format='%02.0f').pack(side='left')
        ttk.Label(time_box,text=':').pack(side='left',padx=3)
        ttk.Spinbox(time_box,from_=0,to=59,textvariable=minute,width=5,format='%02.0f').pack(side='left')

        ttk.Label(f,text='Repetición').grid(row=3,column=0,sticky='w',pady=6)
        rec_cb=ttk.Combobox(
            f,textvariable=rec,values=list(RECURRENCE_LABELS.values()),
            state='readonly',width=30
        )
        rec_cb.grid(row=3,column=1,columnspan=2,sticky='ew',pady=6)

        weekdays_frame=ttk.LabelFrame(f,text='Días de publicación',padding=8)
        weekdays_frame.grid(row=4,column=0,columnspan=3,sticky='ew',pady=(2,8))
        day_names=['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
        existing={x.strip() for x in str(v.get('weekdays') or '').split(',') if x.strip()}
        day_vars=[]
        for i,name in enumerate(day_names):
            var=tk.BooleanVar(value=str(i) in existing)
            day_vars.append(var)
            ttk.Checkbutton(weekdays_frame,text=name,variable=var).grid(
                row=i//4,column=i%4,sticky='w',padx=8,pady=3
            )

        ttk.Label(f,text='Archivo').grid(row=5,column=0,sticky='w',pady=6)
        media=tk.StringVar()
        media_values=[f"{m['id']} | {m['name']}" for m in C.media_list()]
        old_mid=int(v.get('media_id') or 0)
        if old_mid:
            media.set(next((x for x in media_values if x.startswith(str(old_mid)+' | ')),''))
        media_cb=ttk.Combobox(f,textvariable=media,values=media_values,state='readonly',width=48)
        media_cb.grid(row=5,column=1,columnspan=2,sticky='ew',pady=6)

        text_label=ttk.Label(f,text='Texto')
        text_label.grid(row=6,column=0,sticky='nw',pady=6)
        txt=tk.Text(f,width=55,height=7,wrap='word')
        txt.grid(row=6,column=1,columnspan=2,pady=6)
        txt.insert('1.0',v.get('text',''))

        ttk.Checkbutton(f,text='Programación activa',variable=active).grid(
            row=7,column=1,columnspan=2,sticky='w',pady=(5,10)
        )

        def update_kind(*_):
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            if internal=='status_text':
                media_cb.configure(state='disabled')
                text_label.configure(text='Texto del estado')
            else:
                media_cb.configure(state='readonly')
                text_label.configure(text='Pie de publicación (opcional)')

        def update_recurrence(*_):
            internal=RECURRENCE_BY_LABEL.get(rec.get(),'once')
            if internal=='weekdays':
                weekdays_frame.grid()
            else:
                weekdays_frame.grid_remove()

        kind_cb.bind('<<ComboboxSelected>>',update_kind)
        rec_cb.bind('<<ComboboxSelected>>',update_recurrence)
        update_kind()
        update_recurrence()

        out={}
        def save():
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            recurrence=RECURRENCE_BY_LABEL.get(rec.get(),'once')
            try:
                h=max(0,min(23,int(hour.get())))
                m=max(0,min(59,int(minute.get())))
            except Exception:
                return messagebox.showwarning('Hora inválida','Escoge una hora válida.',parent=win)

            selected_days=[str(i) for i,var in enumerate(day_vars) if var.get()]
            if recurrence=='weekdays' and not selected_days:
                return messagebox.showwarning(
                    'Faltan los días',
                    'Selecciona al menos un día de la semana.',
                    parent=win
                )

            media_id=0
            if media.get():
                try:media_id=int(media.get().split('|',1)[0].strip())
                except Exception:media_id=0
            body=txt.get('1.0','end').strip()

            if internal=='status_text' and not body:
                return messagebox.showwarning('Falta el texto','Escribe el texto del estado.',parent=win)
            if internal in ('status_image','status_video') and not media_id:
                return messagebox.showwarning('Falta el archivo','Selecciona una imagen o video de la biblioteca.',parent=win)

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
                'recurrence':recurrence,
                'weekdays':','.join(selected_days) if recurrence=='weekdays' else '',
                'text':body,
                'media_id':media_id,
                'active':active.get(),
            })
            win.destroy()

        buttons=ttk.Frame(f)
        buttons.grid(row=8,column=0,columnspan=3,sticky='e',pady=(6,0))
        ttk.Button(buttons,text='Cancelar',command=win.destroy).pack(side='right',padx=(5,0))
        ttk.Button(buttons,text='Guardar programación',command=save).pack(side='right')
        win.wait_window()
        return out or None
'''
status_block=textwrap.indent(textwrap.dedent(status_block).strip()+"\n","    ")
g,n=re.subn(
    r"    def refresh_status\(self\):.*?(?=\n    def add_status\(self\):)",
    lambda _m:status_block.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar Estados para días seleccionados")

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# ---------------- INSTALLER ----------------
t=iss_path.read_text(encoding="utf-8")
t=t.replace("2.1.2","2.1.3")
iss_path.write_text(t,encoding="utf-8")
