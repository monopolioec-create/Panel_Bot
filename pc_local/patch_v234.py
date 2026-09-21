import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
iss_path=root/"installer.iss"

s=core_path.read_text(encoding="utf-8")

# =========================================================
# VERSION
# =========================================================
if "APP_VERSION = '2.3.3'" not in s and "APP_VERSION = '2.3.4'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.3.3")
s=s.replace("APP_VERSION = '2.3.3'","APP_VERSION = '2.3.4'",1)

# =========================================================
# STABLE CONVERSATION KEY
# Numeric contacts keep the same key.
# LID / username-addressed chats keep their WhatsApp JID as the key.
# =========================================================
helpers = r'''
def conversation_key(value):
    if isinstance(value,dict):
        user=str(
            value.get('User') or value.get('user') or
            value.get('Username') or value.get('username') or ''
        ).strip()
        server=str(
            value.get('Server') or value.get('server') or
            value.get('Domain') or value.get('domain') or ''
        ).strip().lower()
        if user:
            user=user.split(':',1)[0]
        raw=(f'{user}@{server}' if user and server else user).strip()
    else:
        raw=str(value or '').strip()

    if not raw:
        return ''

    # Standard PN chats stay keyed by the actual phone number.
    if '@' in raw:
        user,server=raw.split('@',1)
        user=user.split(':',1)[0].strip()
        server=server.split('/',1)[0].strip().lower()
        digits=re.sub(r'\D+','',user)
        if server in ('s.whatsapp.net','c.us') and 7<=len(digits)<=15:
            return digits
        # LID/hosted/username-style chats must not be converted into a fake phone.
        return f'{user}@{server}'.casefold()

    digits=re.sub(r'\D+','',raw)
    if raw.replace('+','').replace(' ','').replace('-','').replace('(','').replace(')','').isdigit() and 7<=len(digits)<=15:
        return digits
    return raw.casefold()
'''
helpers=textwrap.dedent(helpers)
if "def conversation_key(value):" not in s:
    anchor="def normalize_contact_phone(phone):"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró normalize_contact_phone para insertar conversation_key")
    s=s[:pos]+helpers+"\n\n"+s[pos:]

# =========================================================
# SAVE CONTACT MUST NEVER BLOCK USERNAME/LID CHATS
# =========================================================
old_save = """            resolved_phone=normalize_contact_phone(phone)
            route_text=str(route or '')
            if not resolved_phone and '@lid' not in route_text.lower():
                resolved_phone=normalize_contact_phone(route_text.split('@',1)[0])
            if not resolved_phone:
                raise RuntimeError('WhatsApp no entregó el número telefónico real del cliente; se recibió un identificador interno LID.')"""
new_save = """            resolved_phone=normalize_contact_phone(phone)
            route_text=str(route or '')
            if not resolved_phone and '@lid' not in route_text.lower() and '@hosted.lid' not in route_text.lower():
                candidate=normalize_contact_phone(route_text.split('@',1)[0])
                if 7<=len(candidate)<=15:
                    resolved_phone=candidate
            if not resolved_phone:
                # WhatsApp may intentionally expose only an LID/username identity.
                # Do not abort the rule: skip only contact storage/Google sync and
                # continue with banner, text, menus and all following actions.
                log(
                    pid,'info',
                    f'Cliente identificado por usuario/LID sin número visible · '
                    f'se omite Guardar cliente y continúa el flujo · {route_text}'
                )
                return"""
if old_save not in s:
    raise SystemExit("No se encontró el bloque actual de save_contact sin PN")
s=s.replace(old_save,new_save,1)

# =========================================================
# PAUSED CONTACTS: allow phone OR LID/username JID
# =========================================================
s=s.replace(
    "    phone=normalize_contact_phone(phone)\n    if not phone:\n        raise RuntimeError('No se pudo identificar el número del cliente.')\n",
    "    phone=conversation_key(phone)\n    if not phone:\n        raise RuntimeError('No se pudo identificar al cliente.')\n",
    1
)

# resume_contact
resume_old="""def resume_contact(profile_id,phone):
    phone=normalize_contact_phone(phone)
    x('DELETE FROM paused_contacts WHERE profile_id=? AND phone=?',(profile_id,phone))
"""
resume_new="""def resume_contact(profile_id,phone):
    phone=conversation_key(phone)
    if phone:
        x('DELETE FROM paused_contacts WHERE profile_id=? AND phone=?',(profile_id,phone))
"""
if resume_old not in s:
    raise SystemExit("No se encontró resume_contact")
s=s.replace(resume_old,resume_new,1)

# is_contact_paused from v2.3.2
paused_old="""def is_contact_paused(profile_id,phone):
    phone=normalize_contact_phone(phone)
    if not phone:
        return False
"""
paused_new="""def is_contact_paused(profile_id,phone):
    phone=conversation_key(phone)
    if not phone:
        return False
"""
if paused_old not in s:
    raise SystemExit("No se encontró encabezado de is_contact_paused")
s=s.replace(paused_old,paused_new,1)

# Webhook pause check must fall back to the conversation JID.
s=s.replace(
    "            if is_contact_paused(pid,phone):\n",
    "            if is_contact_paused(pid,phone or route):\n",
    1
)

# =========================================================
# GUIDED FLOW: key by phone OR route JID
# =========================================================
for old,new in [
    ("    phone=normalize_contact_phone(phone)\n    if not phone:return None\n    return q(\n        'SELECT * FROM guided_flows WHERE profile_id=? AND phone=?',",
     "    phone=conversation_key(phone)\n    if not phone:return None\n    return q(\n        'SELECT * FROM guided_flows WHERE profile_id=? AND phone=?',"),
    ("    phone=normalize_contact_phone(phone)\n    if not phone:return\n    flow_id=str((action or {}).get('flow_id') or 'main')[:100]",
     "    phone=conversation_key(phone)\n    if not phone:return\n    flow_id=str((action or {}).get('flow_id') or 'main')[:100]"),
    ("    phone=normalize_contact_phone(phone)\n    if phone:\n        x('DELETE FROM guided_flows WHERE profile_id=? AND phone=?',(profile_id,phone))",
     "    phone=conversation_key(phone)\n    if phone:\n        x('DELETE FROM guided_flows WHERE profile_id=? AND phone=?',(profile_id,phone))"),
    ("    phone=normalize_contact_phone(phone)\n    if phone:\n        x(\n            'UPDATE guided_flows SET invalid_count=?,updated_at=? WHERE profile_id=? AND phone=?',",
     "    phone=conversation_key(phone)\n    if phone:\n        x(\n            'UPDATE guided_flows SET invalid_count=?,updated_at=? WHERE profile_id=? AND phone=?',"),
]:
    if old not in s:
        raise SystemExit("No se encontró un bloque de guided_flows esperado")
    s=s.replace(old,new,1)

# Interceptor must use a stable state key even when phone is blank.
old_intercept="""    def guided_menu_intercept(self,pid,token,route,phone,name,text):
        state=guided_flow_get(pid,phone)
        if not state:
            return None
"""
new_intercept="""    def guided_menu_intercept(self,pid,token,route,phone,name,text):
        state_key=phone or route
        state=guided_flow_get(pid,state_key)
        if not state:
            return None
"""
if old_intercept not in s:
    raise SystemExit("No se encontró encabezado de guided_menu_intercept")
s=s.replace(old_intercept,new_intercept,1)

# All state mutations in the interceptor must use the same key.
start=s.find("    def guided_menu_intercept(self,pid,token,route,phone,name,text):")
end=s.find("\n    def execute_action(",start)
if start<0 or end<0:
    raise SystemExit("No se pudo delimitar guided_menu_intercept")
block=s[start:end]
block=block.replace("guided_flow_clear(pid,phone)","guided_flow_clear(pid,state_key)")
block=block.replace("guided_flow_set_invalid(pid,phone,invalid_count+1)","guided_flow_set_invalid(pid,state_key,invalid_count+1)")
s=s[:start]+block+s[end:]

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# Installer
t=iss_path.read_text(encoding="utf-8")
if "2.3.3" not in t and "2.3.4" not in t:
    raise SystemExit("No se encontró versión 2.3.3 en installer.iss")
t=t.replace("2.3.3","2.3.4")
iss_path.write_text(t,encoding="utf-8")
