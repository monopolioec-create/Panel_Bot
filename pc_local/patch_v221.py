import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

# =========================================================
# CORE / VERSION
# =========================================================
s=core_path.read_text(encoding="utf-8")
if "APP_VERSION = '2.2.0'" not in s and "APP_VERSION = '2.2.1'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.2.0 para actualizar")
s=s.replace("APP_VERSION = '2.2.0'","APP_VERSION = '2.2.1'")
compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI - interruptor rápido por regla + Supr para eliminar
# =========================================================
g=gui_path.read_text(encoding="utf-8")

new_build_rules = r'''
    def build_rules(self):
        f=self.tabs['Reglas']
        ttk.Label(f,text='Reglas automáticas',font=('Segoe UI',20,'bold')).pack(anchor='w')
        tpl=ttk.LabelFrame(f,text='Plantillas',padding=10);tpl.pack(fill='x',pady=(8,4))
        ttk.Label(
            tpl,
            text='Importa archivos .mbtpl que puedo prepararte con una secuencia completa. Las reglas importadas quedan DESACTIVADAS para que las revises y edites antes de usarlas.',
            wraplength=760,foreground=MUTED
        ).pack(side='left',fill='x',expand=True)
        tb=ttk.Frame(tpl);tb.pack(side='right',padx=(10,0))
        ttk.Button(tb,text='Importar plantilla',command=self.import_rule_template).pack(side='left')
        ttk.Button(tb,text='Exportar selección',command=self.export_selected_template).pack(side='left',padx=5)
        ttk.Button(tb,text='Exportar todas',command=self.export_all_template).pack(side='left')

        ttk.Label(
            f,
            text='Haz clic en el interruptor ON/OFF de la primera columna para activar o apagar una regla. Selecciona una regla y pulsa Supr para eliminarla.',
            foreground=MUTED
        ).pack(anchor='w',pady=(8,0))

        self.rules_tree=ttk.Treeview(
            f,
            columns=('toggle','name','match','pattern','priority'),
            show='headings',
            selectmode='extended'
        )
        for col,head,width,anchor in [
            ('toggle','ON / OFF',105,'center'),
            ('name','Nombre',220,'w'),
            ('match','Coincidencia',120,'center'),
            ('pattern','Patrón',300,'w'),
            ('priority','Prioridad',90,'center'),
        ]:
            self.rules_tree.heading(col,text=head)
            self.rules_tree.column(col,width=width,anchor=anchor)
        self.rules_tree.pack(fill='both',expand=True,pady=12)
        self.rules_tree.bind('<ButtonRelease-1>',self.rule_toggle_click)
        self.rules_tree.bind('<Delete>',self.rule_delete_key)
        self.rules_tree.bind('<KP_Delete>',self.rule_delete_key)

        b=ttk.Frame(f);b.pack(fill='x')
        ttk.Button(b,text='+ Nueva regla',command=self.new_rule).pack(side='left')
        ttk.Button(b,text='Editar',command=self.edit_rule).pack(side='left',padx=5)
        ttk.Button(b,text='Duplicar',command=self.dup_rule).pack(side='left')
        ttk.Button(b,text='Eliminar',command=self.del_rule).pack(side='right')
'''
new_build_rules=textwrap.indent(textwrap.dedent(new_build_rules).strip()+"\n","    ")
g,n=re.subn(
    r"    def build_rules\(self\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:new_build_rules.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar build_rules")

new_refresh_rules = r'''
    def refresh_rules(self):
        if not hasattr(self,'rules_tree'):
            return
        selected={str(x) for x in self.rules_tree.selection()}
        focused=str(self.rules_tree.focus() or '')
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)
        pid=self.pid()
        if not pid:
            return
        for rule in C.rules_for(pid):
            rid=str(rule.get('id') or '')
            enabled=bool(rule.get('enabled'))
            self.rules_tree.insert(
                '',
                'end',
                iid=rid,
                values=(
                    '● ON' if enabled else '○ OFF',
                    rule.get('name') or '',
                    rule.get('match_type') or '',
                    rule.get('pattern') or '',
                    rule.get('priority') if rule.get('priority') is not None else '',
                )
            )
        for rid in selected:
            if self.rules_tree.exists(rid):
                self.rules_tree.selection_add(rid)
        if focused and self.rules_tree.exists(focused):
            self.rules_tree.focus(focused)
'''
new_refresh_rules=textwrap.indent(textwrap.dedent(new_refresh_rules).strip()+"\n","    ")
g,n=re.subn(
    r"    def refresh_rules\(self\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:new_refresh_rules.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar refresh_rules")

new_del_rule = r'''
    def del_rule(self):
        if not hasattr(self,'rules_tree'):
            return
        ids=[int(x) for x in self.rules_tree.selection() if str(x).isdigit()]
        if not ids:
            return
        rows={int(r.get('id') or 0):r for r in C.rules_for(self.pid())}
        if len(ids)==1:
            name=(rows.get(ids[0]) or {}).get('name') or f'Regla {ids[0]}'
            question=f'¿Eliminar la regla "{name}"?\n\nEsta acción no se puede deshacer.'
        else:
            question=f'¿Eliminar las {len(ids)} reglas seleccionadas?\n\nEsta acción no se puede deshacer.'
        if not messagebox.askyesno('Eliminar regla',question,parent=self):
            return
        pid=self.pid()
        removed=0
        for rid in ids:
            try:
                if hasattr(C,'delete_rule'):
                    C.delete_rule(rid)
                else:
                    C.x('DELETE FROM rules WHERE id=? AND profile_id=?',(rid,pid))
                removed+=1
            except Exception as e:
                messagebox.showerror('Eliminar regla',f'No se pudo eliminar la regla {rid}:\n{e}',parent=self)
                break
        if removed:
            try:
                C.log(pid,'info',f'{removed} regla(s) eliminada(s) manualmente')
            except Exception:
                pass
        self.refresh_rules()
        try:
            self.refresh_home()
        except Exception:
            pass
'''
new_del_rule=textwrap.indent(textwrap.dedent(new_del_rule).strip()+"\n","    ")
g,n=re.subn(
    r"    def del_rule\(self\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:new_del_rule.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar del_rule")

quick_methods = r'''
    def rule_toggle_click(self,event):
        if not hasattr(self,'rules_tree'):
            return
        if self.rules_tree.identify_region(event.x,event.y)!='cell':
            return
        if self.rules_tree.identify_column(event.x)!='#1':
            return
        rid=self.rules_tree.identify_row(event.y)
        if not rid or not str(rid).isdigit():
            return
        pid=self.pid()
        if not pid:
            return 'break'
        current=next(
            (r for r in C.rules_for(pid) if int(r.get('id') or 0)==int(rid)),
            None
        )
        if not current:
            return 'break'
        new_state=0 if bool(current.get('enabled')) else 1
        try:
            C.x(
                'UPDATE rules SET enabled=? WHERE id=? AND profile_id=?',
                (new_state,int(rid),pid)
            )
            try:
                C.log(
                    pid,
                    'info',
                    f"Regla {'activada' if new_state else 'desactivada'} · {current.get('name') or rid}"
                )
            except Exception:
                pass
            self.refresh_rules()
            if self.rules_tree.exists(str(rid)):
                self.rules_tree.selection_set(str(rid))
                self.rules_tree.focus(str(rid))
                self.rules_tree.see(str(rid))
            try:
                self.refresh_home()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror('Reglas',f'No se pudo cambiar el estado de la regla:\n{e}',parent=self)
        return 'break'

    def rule_delete_key(self,event=None):
        if not hasattr(self,'rules_tree'):
            return 'break'
        if self.rules_tree.selection():
            self.del_rule()
        return 'break'
'''
quick_methods=textwrap.indent(textwrap.dedent(quick_methods).strip()+"\n","    ")
anchor="    def refresh_rules(self):\n"
pos=g.find(anchor)
if pos<0:
    raise SystemExit("No se encontró refresh_rules para insertar los accesos rápidos")
if "def rule_toggle_click(self,event):" not in g:
    g=g[:pos]+quick_methods+"\n"+g[pos:]

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER VERSION
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.2.0" not in t and "2.2.1" not in t:
    raise SystemExit("No se encontró versión 2.2.0 en installer.iss")
t=t.replace("2.2.0","2.2.1")
iss_path.write_text(t,encoding="utf-8")
