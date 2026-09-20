import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
gui_path=root/"gui_local.py"
core_path=root/"core_local.py"
iss_path=root/"installer.iss"

# ---------------- VERSION ----------------
s=core_path.read_text(encoding="utf-8")
s=s.replace("APP_VERSION = '2.1.1'","APP_VERSION = '2.1.2'")
core_path.write_text(s,encoding="utf-8")

g=gui_path.read_text(encoding="utf-8")

# ---------------- PALETA OSCURA FUTURISTA ----------------
g=re.sub(
    r"BG='[^']*'; CARD='[^']*'; NAV='[^']*'; GOLD='[^']*'; GREEN='[^']*'; RED='[^']*'; TEXT='[^']*'; MUTED='[^']*'",
    "BG='#070B12'; CARD='#0F1722'; NAV='#05080D'; GOLD='#D6A842'; GREEN='#39FF88'; RED='#FF4D5A'; TEXT='#E9EEF7'; MUTED='#8793A6'",
    g,
    count=1
)

palette_extra = r'''
CARD2='#121D2B'
INPUT_BG='#0A111B'
BORDER='#243247'
CYAN='#4FD7FF'
AMBER='#FFB547'
GLOW_GREEN='#39FF88'
GLOW_RED='#FF4D5A'
GLOW_AMBER='#FFB547'
GLOW_CYAN='#4FD7FF'
'''
if "CARD2='#121D2B'" not in g:
    anchor="BG='#070B12'; CARD='#0F1722'; NAV='#05080D'; GOLD='#D6A842'; GREEN='#39FF88'; RED='#FF4D5A'; TEXT='#E9EEF7'; MUTED='#8793A6'\n"
    if anchor not in g:
        raise SystemExit("No se encontró la paleta de interfaz")
    g=g.replace(anchor,anchor+palette_extra+"\n",1)

# ---------------- APP + ESTILOS ----------------
new_init = r'''
    def __init__(self):
        super().__init__()
        global APP
        APP=self
        self.title(f'{C.APP_NAME} {C.APP_VERSION}')
        self.geometry('1180x760')
        self.minsize(1050,680)
        self.configure(bg=BG)
        self.protocol('WM_DELETE_WINDOW',self.hide)

        # Apariencia oscura elegante.
        self.option_add('*Font','Segoe UI 10')
        self.option_add('*Text.background',INPUT_BG)
        self.option_add('*Text.foreground',TEXT)
        self.option_add('*Text.insertBackground',CYAN)
        self.option_add('*Text.selectBackground','#24405C')
        self.option_add('*Text.selectForeground','#FFFFFF')
        self.option_add('*Listbox.background',INPUT_BG)
        self.option_add('*Listbox.foreground',TEXT)

        self.style=ttk.Style(self)
        self.style.theme_use('clam')

        self.style.configure('.',background=BG,foreground=TEXT,font=('Segoe UI',10))
        self.style.configure('TFrame',background=BG)
        self.style.configure('Card.TFrame',background=CARD)
        self.style.configure('TLabel',background=BG,foreground=TEXT)
        self.style.configure('Muted.TLabel',background=BG,foreground=MUTED)
        self.style.configure('Card.TLabel',background=CARD,foreground=TEXT)
        self.style.configure('Title.TLabel',font=('Segoe UI',22,'bold'),background=NAV,foreground=TEXT)

        self.style.configure(
            'TButton',
            background=CARD2,foreground=TEXT,
            bordercolor=BORDER,darkcolor=CARD2,lightcolor=CARD2,
            padding=(11,7),relief='flat'
        )
        self.style.map(
            'TButton',
            background=[('active','#18283A'),('pressed','#0B111A'),('disabled','#0B1118')],
            foreground=[('disabled','#586273'),('active','#FFFFFF')]
        )
        self.style.configure(
            'Accent.TButton',
            background=GOLD,foreground='#090B0F',
            bordercolor=GOLD,font=('Segoe UI',10,'bold'),padding=(12,8)
        )
        self.style.map(
            'Accent.TButton',
            background=[('active','#E6BE62'),('pressed','#B78B32')],
            foreground=[('active','#05070A')]
        )

        self.style.configure(
            'TEntry',fieldbackground=INPUT_BG,foreground=TEXT,
            insertcolor=CYAN,bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=7
        )
        self.style.map('TEntry',bordercolor=[('focus',CYAN)])

        self.style.configure(
            'TCombobox',fieldbackground=INPUT_BG,background=CARD2,foreground=TEXT,
            arrowcolor=CYAN,bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=6
        )
        self.style.map(
            'TCombobox',
            fieldbackground=[('readonly',INPUT_BG)],
            foreground=[('readonly',TEXT)],
            bordercolor=[('focus',CYAN)]
        )

        self.style.configure(
            'TSpinbox',fieldbackground=INPUT_BG,foreground=TEXT,
            arrowcolor=CYAN,bordercolor=BORDER
        )
        self.style.configure('TCheckbutton',background=BG,foreground=TEXT)
        self.style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',TEXT)])
        self.style.configure('TRadiobutton',background=BG,foreground=TEXT)
        self.style.map('TRadiobutton',background=[('active',BG)],foreground=[('active',TEXT)])

        self.style.configure(
            'TLabelframe',background=BG,foreground=GOLD,
            bordercolor=BORDER,relief='solid'
        )
        self.style.configure(
            'TLabelframe.Label',background=BG,foreground=GOLD,
            font=('Segoe UI',10,'bold')
        )

        self.style.configure(
            'Treeview',
            background=CARD,fieldbackground=CARD,foreground=TEXT,
            bordercolor=BORDER,rowheight=30
        )
        self.style.configure(
            'Treeview.Heading',
            background='#111D2B',foreground='#D7E1EF',
            bordercolor=BORDER,font=('Segoe UI',9,'bold'),relief='flat'
        )
        self.style.map(
            'Treeview',
            background=[('selected','#173B54')],
            foreground=[('selected','#FFFFFF')]
        )
        self.style.map(
            'Treeview.Heading',
            background=[('active','#172638')]
        )

        self.style.configure(
            'TNotebook',background=BG,borderwidth=0,tabmargins=(0,4,0,0)
        )
        self.style.configure(
            'TNotebook.Tab',
            background='#0B121C',foreground=MUTED,
            padding=(13,9),borderwidth=0
        )
        self.style.map(
            'TNotebook.Tab',
            background=[('selected',CARD2),('active','#101B29')],
            foreground=[('selected',GOLD),('active',TEXT)]
        )

        self.style.configure(
            'Vertical.TScrollbar',
            background=CARD2,troughcolor=BG,bordercolor=BG,
            arrowcolor=CYAN,darkcolor=CARD2,lightcolor=CARD2
        )

        self.profile_var=tk.StringVar()
        self.profile_map={}
        self.make_header()
        self.nb=ttk.Notebook(self)
        self.nb.pack(fill='both',expand=True,padx=16,pady=(0,16))
        self.make_tabs()
        self.reload_profiles()
        self.after(1000,self.periodic)
        self.start_tray()
'''
new_init=textwrap.indent(textwrap.dedent(new_init).strip()+"\n","    ")
g,n=re.subn(
    r"    def __init__\(self\):.*?(?=\n    def make_header\(self\):)",
    lambda _m:new_init.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar App.__init__")

# ---------------- HEADER FUTURISTA ----------------
new_header = r'''
    def make_header(self):
        h=tk.Frame(self,bg=NAV,height=82,highlightthickness=0)
        h.pack(fill='x')
        left=tk.Frame(h,bg=NAV)
        left.pack(side='left',padx=22,pady=14)

        tk.Label(
            left,text='MONOPOLIO',bg=NAV,fg=GOLD,
            font=('Segoe UI',20,'bold')
        ).pack(side='left')
        tk.Label(
            left,text=' MULTIBOT',bg=NAV,fg=TEXT,
            font=('Segoe UI',20,'bold')
        ).pack(side='left')
        tk.Label(
            left,text='  DESKTOP',bg=NAV,fg=CYAN,
            font=('Segoe UI',10,'bold')
        ).pack(side='left',padx=(4,0),pady=(7,0))

        right=tk.Frame(h,bg=NAV)
        right.pack(side='right',padx=22)
        tk.Label(
            right,text='NEGOCIO',bg=NAV,fg=MUTED,
            font=('Segoe UI',9,'bold')
        ).pack(side='left',padx=8)
        self.profile_cb=ttk.Combobox(
            right,textvariable=self.profile_var,state='readonly',width=27
        )
        self.profile_cb.pack(side='left')
        self.profile_cb.bind('<<ComboboxSelected>>',lambda e:self.profile_changed())

        # Línea dorada/cian muy sutil debajo del encabezado.
        line=tk.Frame(self,bg=GOLD,height=1)
        line.pack(fill='x')
'''
new_header=textwrap.indent(textwrap.dedent(new_header).strip()+"\n","    ")
g,n=re.subn(
    r"    def make_header\(self\):.*?(?=\n    def make_tabs\(self\):)",
    lambda _m:new_header.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar make_header")

# ---------------- SEMÁFOROS CON RESPLANDOR ----------------
glow_methods = r'''
    def _status_color(self,text):
        value=str(text or '').upper()
        if any(x in value for x in ('VINCULADO','ENCENDIDO','EN LÍNEA','CONECTADO','OK')):
            return GLOW_GREEN
        if any(x in value for x in ('PENDIENTE','INICIANDO','ESPERANDO')):
            return GLOW_AMBER
        if any(x in value for x in ('ERROR','APAGADO','DESCONECTADO','NO')):
            return GLOW_RED
        return GLOW_CYAN

    def _paint_glow(self,canvas,color):
        canvas.delete('all')
        # Capas concéntricas para simular resplandor neón.
        canvas.create_oval(1,1,31,31,fill='',outline=color,width=1,stipple='gray75')
        canvas.create_oval(5,5,27,27,fill='',outline=color,width=2,stipple='gray50')
        canvas.create_oval(9,9,23,23,fill=color,outline=color,width=1)
        canvas.create_oval(12,12,18,18,fill='#F7FFFF',outline='',width=0)

    def _set_status(self,label,text,color=None):
        color=color or self._status_color(text)
        label.config(text=text,fg=color)
        canvas=getattr(label,'glow_canvas',None)
        if canvas:
            self._paint_glow(canvas,color)
'''
glow_methods=textwrap.indent(textwrap.dedent(glow_methods).strip()+"\n","    ")
anchor="    def build_home(self):\n"
pos=g.find(anchor)
if pos<0:
    raise SystemExit("No se encontró build_home")
if "def _paint_glow" not in g:
    g=g[:pos]+glow_methods+g[pos:]

# ---------------- HOME CARDS ----------------
new_home = r'''
    def build_home(self):
        f=self.tabs['Inicio']
        ttk.Label(
            f,text='Panel principal',
            font=('Segoe UI',22,'bold'),foreground=TEXT
        ).pack(anchor='w')
        ttk.Label(
            f,text='Estado general de tus conexiones y automatizaciones.',
            foreground=MUTED
        ).pack(anchor='w',pady=(2,4))

        cards=ttk.Frame(f)
        cards.pack(fill='x',pady=18)
        self.home_engine=self.card(cards,'MOTOR','INICIANDO',0)
        self.home_wa=self.card(cards,'WHATSAPP','PENDIENTE',1)
        self.home_bot=self.card(cards,'BOT','ENCENDIDO',2)
        self.home_rules=self.card(cards,'REGLAS','0',3,neutral=True)

        box=ttk.LabelFrame(f,text='Funcionamiento del programa',padding=16)
        box.pack(fill='x',pady=8)
        ttk.Label(
            box,
            text='El bot funciona directamente en esta PC. Las reglas, los archivos y las respuestas '
                 'se procesan aquí para responder más rápido.',
            wraplength=940,foreground=MUTED
        ).pack(anchor='w')

    def card(self,parent,title,value,col,neutral=False):
        fr=tk.Frame(
            parent,bg=CARD,bd=0,
            highlightthickness=1,highlightbackground=BORDER,
            padx=16,pady=13
        )
        fr.grid(row=0,column=col,padx=7,sticky='nsew')
        parent.columnconfigure(col,weight=1)

        top=tk.Frame(fr,bg=CARD)
        top.pack(fill='x')
        tk.Label(
            top,text=title,bg=CARD,fg=MUTED,
            font=('Segoe UI',9,'bold')
        ).pack(side='left')

        if neutral:
            glow=None
        else:
            glow=tk.Canvas(
                top,width=32,height=32,bg=CARD,
                highlightthickness=0,bd=0
            )
            glow.pack(side='right')

        lab=tk.Label(
            fr,text=value,bg=CARD,fg=TEXT,
            font=('Segoe UI',17,'bold'),anchor='w'
        )
        lab.pack(fill='x',pady=(5,0))
        lab.glow_canvas=glow
        if glow:
            self._paint_glow(glow,self._status_color(value))
        return lab

    def refresh_home(self):
        pid=self.pid()
        p=C.get_profile(pid) if pid else None

        try:
            C.WUZ.start()
            self._set_status(self.home_engine,'EN LÍNEA',GLOW_GREEN)
        except Exception:
            self._set_status(self.home_engine,'ERROR',GLOW_RED)

        if p:
            try:
                tok=C.ENGINE.prepare(pid)
                connected,logged,_=C.WUZ.flags(tok)
                if logged:
                    self._set_status(self.home_wa,'VINCULADO',GLOW_GREEN)
                elif connected:
                    self._set_status(self.home_wa,'CONECTANDO',GLOW_AMBER)
                else:
                    self._set_status(self.home_wa,'PENDIENTE',GLOW_AMBER)
            except Exception:
                self._set_status(self.home_wa,'ERROR',GLOW_RED)

            self._set_status(
                self.home_bot,
                'ENCENDIDO' if p['bot_enabled'] else 'APAGADO',
                GLOW_GREEN if p['bot_enabled'] else GLOW_RED
            )
            self.home_rules.config(
                text=str(len(C.rules_for(pid))),
                fg=CYAN
            )
'''
new_home=textwrap.indent(textwrap.dedent(new_home).strip()+"\n","    ")
g,n=re.subn(
    r"    def build_home\(self\):.*?(?=\n    def build_profiles\(self\):)",
    lambda _m:new_home.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar Home")

# ---------------- WHATSAPP STATUS GLOW ----------------
new_whatsapp = r'''
    def build_whatsapp(self):
        f=self.tabs['WhatsApp']
        ttk.Label(f,text='Vincular WhatsApp',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(
            f,text='Conecta el WhatsApp del negocio seleccionado.',
            foreground=MUTED
        ).pack(anchor='w',pady=(2,4))

        box=ttk.LabelFrame(f,text='Sesión del negocio seleccionado',padding=16)
        box.pack(fill='x',pady=14)

        ttk.Label(box,text='Número internacional (sin +)').grid(row=0,column=0,sticky='w')
        self.phone=tk.StringVar()
        ttk.Entry(box,textvariable=self.phone,width=35).grid(row=1,column=0,sticky='w',pady=6)
        ttk.Button(
            box,text='GENERAR CÓDIGO',style='Accent.TButton',command=self.pair
        ).grid(row=1,column=1,padx=8)

        self.pair_code=tk.StringVar()
        tk.Label(
            box,textvariable=self.pair_code,bg=BG,fg=GOLD,
            font=('Consolas',24,'bold')
        ).grid(row=2,column=0,sticky='w',pady=12)
        ttk.Button(box,text='Copiar código',command=self.copy_code).grid(row=2,column=1,padx=8)

        status_row=tk.Frame(box,bg=BG)
        status_row.grid(row=3,column=0,columnspan=2,sticky='w',pady=8)
        self.wa_glow=tk.Canvas(
            status_row,width=32,height=32,bg=BG,
            highlightthickness=0,bd=0
        )
        self.wa_glow.pack(side='left',padx=(0,5))
        self.wa_status=tk.StringVar(value='WhatsApp: PENDIENTE')
        self.wa_status_label=tk.Label(
            status_row,textvariable=self.wa_status,bg=BG,
            fg=AMBER,font=('Segoe UI',10,'bold')
        )
        self.wa_status_label.pack(side='left')
        self._paint_glow(self.wa_glow,GLOW_AMBER)

        actions=ttk.Frame(box)
        actions.grid(row=4,column=0,columnspan=2,sticky='w',pady=10)
        ttk.Button(actions,text='Conectar',command=self.connect_wa).pack(side='left')
        ttk.Button(actions,text='Desconectar conexión',command=self.disconnect_wa).pack(side='left',padx=6)
        ttk.Button(actions,text='Cerrar sesión WhatsApp',command=self.logout_wa).pack(side='left')

    def _set_whatsapp_status(self,text,state='pending'):
        self.wa_status.set(text)
        color={
            'ok':GLOW_GREEN,
            'pending':GLOW_AMBER,
            'error':GLOW_RED,
            'off':GLOW_RED,
        }.get(state,GLOW_CYAN)
        if hasattr(self,'wa_status_label'):
            self.wa_status_label.config(fg=color)
        if hasattr(self,'wa_glow'):
            self._paint_glow(self.wa_glow,color)

    def refresh_whatsapp(self):
        pid=self.pid()
        if not pid:
            return
        try:
            tok=C.ENGINE.prepare(pid)
            connected,logged,_=C.WUZ.flags(tok)
            if logged:
                self._set_whatsapp_status(
                    f"WhatsApp: VINCULADO · conexión: {'OK' if connected else 'ESPERANDO'}",
                    'ok' if connected else 'pending'
                )
            else:
                self._set_whatsapp_status(
                    f"WhatsApp: PENDIENTE · conexión: {'OK' if connected else 'NO'}",
                    'pending'
                )
        except Exception as e:
            self._set_whatsapp_status('Error: '+str(e),'error')
'''
new_whatsapp=textwrap.indent(textwrap.dedent(new_whatsapp).strip()+"\n","    ")
g,n=re.subn(
    r"    def build_whatsapp\(self\):.*?(?=\n    def pair\(self\):)",
    lambda _m:new_whatsapp.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar WhatsApp")

# Pair status also gets glow.
g=g.replace(
    "pid=self.pid();phone=self.phone.get();self.wa_status.set('Generando código…')",
    "pid=self.pid();phone=self.phone.get();self._set_whatsapp_status('Generando código…','pending')"
)
g=g.replace(
    "lambda code:(self.pair_code.set(code),self.wa_status.set('Código listo. Úsalo en WhatsApp > Dispositivos vinculados > Vincular con número.'))",
    "lambda code:(self.pair_code.set(code),self._set_whatsapp_status('Código listo. Úsalo en WhatsApp > Dispositivos vinculados > Vincular con número.','pending'))"
)

# ---------------- TREEVIEW TAGS FOR BOT STATUS ----------------
old_refresh_profiles = re.search(
    r"    def refresh_profiles\(self\):.*?(?=\n    def selected_profile\(self\):)",
    g,flags=re.S
)
if old_refresh_profiles:
    new_refresh_profiles = r'''
    def refresh_profiles(self):
        if not hasattr(self,'profiles_tree'):
            return
        for item in self.profiles_tree.get_children():
            self.profiles_tree.delete(item)
        self.profiles_tree.tag_configure('on',foreground=GLOW_GREEN)
        self.profiles_tree.tag_configure('off',foreground=GLOW_RED)
        for p in C.profile_list():
            on=bool(p['bot_enabled'])
            self.profiles_tree.insert(
                '', 'end', iid=p['id'],
                values=(p['name'],'ENCENDIDO' if on else 'APAGADO'),
                tags=('on' if on else 'off',)
            )
'''
    new_refresh_profiles=textwrap.indent(textwrap.dedent(new_refresh_profiles).strip()+"\n","    ")
    g=g[:old_refresh_profiles.start()]+new_refresh_profiles.rstrip()+g[old_refresh_profiles.end():]

# ---------------- DARK FIXES FOR TK WIDGETS ----------------
g=g.replace("bg='white'","bg=CARD")
g=g.replace("highlightbackground='#e2e5e9'","highlightbackground=BORDER")
g=g.replace("fg='white'","fg=TEXT")

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# ---------------- INSTALLER ----------------
t=iss_path.read_text(encoding="utf-8")
t=t.replace("2.1.1","2.1.2")
iss_path.write_text(t,encoding="utf-8")
