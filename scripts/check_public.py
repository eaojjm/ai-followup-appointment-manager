"""Dependency-free prepublication checks. Reports locations, never secret values."""
import json,re,struct,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'telegram-bot-token':r'(?<![A-Za-z0-9_])\d{6,12}:[A-Za-z0-9_-]{25,}(?![A-Za-z0-9_-])',
    'openai-key':r'(?<![A-Za-z0-9_])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}',
    'jwt':r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
    'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'aws-access-key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'github-token':r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
    'password-in-uri':r'(?:postgres(?:ql)?|mysql|mongodb)://[^\s/:]+:[^\s@]+@',
    'personal-email':r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'private-host':r'(?:dani9\.ru|[a-z0-9]{15,}\.supabase\.co)',
    'local-absolute-path':r'\b[A-Za-z]:[\\/]',
}
EXPECTED={
 '01-log-bot-message.json','02-workflow-error-alerts.json','03-appointment-booking.json',
 '04-appointment-lifecycle.json','05-followup-engine.json','06-telegram-router.json',
}
errors=[]
def fail(file,reason):errors.append({'file':str(file.relative_to(ROOT)),'reason':reason})
def walk(value,path=''):
    if isinstance(value,dict):
        for key,item in value.items():yield from walk(item,path+'/'+key)
    elif isinstance(value,list):
        for i,item in enumerate(value):yield from walk(item,path+'/'+str(i))
    else:yield path,value
files=[p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts
       and '__pycache__' not in p.relative_to(ROOT).parts]
images=[]
for file in files:
    relative=file.relative_to(ROOT)
    if file.suffix not in {'.md','.json','.py','.sql','.png'} and file.name not in {'.gitignore','.env.example'}:
        fail(file,'unreviewed file type')
    if any(x in relative.parts for x in ('private-audit','.tesseract-work','sources')):
        fail(file,'private directory')
    if file.suffix=='.png':
        data=file.read_bytes()
        if data[:8]!=b'\x89PNG\r\n\x1a\n':fail(file,'invalid PNG');continue
        width,height=struct.unpack('>II',data[16:24]);offset=8;chunks=[]
        while offset+12<=len(data):
            length=struct.unpack_from('>I',data,offset)[0];kind=data[offset+4:offset+8]
            chunks.append(kind.decode('ascii',errors='replace'));offset+=length+12
        if any(c in chunks for c in ('tEXt','iTXt','zTXt','eXIf')):fail(file,'embedded image metadata needs review')
        images.append({'file':str(relative),'width':width,'height':height,'bytes':len(data)})
        continue
    text=file.read_text(encoding='utf-8-sig')
    for name,pattern in PATTERNS.items():
        if re.search(pattern,text,re.I if name in ('private-host','password-in-uri') else 0):fail(file,name)
    if file.suffix=='.md':
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target) or target.startswith('#'):continue
            destination=(file.parent/target.split('#')[0]).resolve()
            if not destination.is_relative_to(ROOT.resolve()) or not destination.exists():fail(file,'broken local Markdown link')
workflow_files=list((ROOT/'workflows').glob('*.json'))
if {p.name for p in workflow_files}!=EXPECTED:errors.append({'file':'workflows','reason':'unexpected/missing workflow set'})
workflow_info=[]
for file in workflow_files:
    try:doc=json.loads(file.read_text(encoding='utf-8'))
    except json.JSONDecodeError:fail(file,'invalid JSON');continue
    if doc.get('active') is not False:fail(file,'active workflow')
    if doc.get('pinData')!={}:fail(file,'pinned data')
    if set(doc)-{'name','nodes','connections','settings','active','pinData','tags'}:fail(file,'unreviewed top-level metadata')
    names=[n['name'] for n in doc['nodes']]
    if len(names)!=len(set(names)):fail(file,'duplicate node names')
    ids=[n['id'] for n in doc['nodes']]
    if len(ids)!=len(set(ids)):fail(file,'duplicate node IDs')
    for path,value in walk(doc):
        if any(key in path.split('/') for key in ('credentials','webhookId','cachedResultUrl','cachedResultName')):fail(file,'private node metadata')
    for name,ports in doc['connections'].items():
        if name not in names:fail(file,'connection source missing')
        for groups in ports.values():
            for group in groups:
                for edge in group:
                    if edge['node'] not in names:fail(file,'connection target missing')
    for n in doc['nodes']:
        if n['type']=='n8n-nodes-base.executeWorkflow':
            ref=n['parameters']['workflowId']
            if ref.get('mode')!='id' or not ref.get('value','').startswith('REPLACE_WITH_'):fail(file,'subworkflow not anonymized')
        if n['type']=='n8n-nodes-base.httpRequest':
            if '$env.TELEGRAM_BOT_TOKEN' not in n['parameters'].get('url',''):fail(file,'unexpected HTTP endpoint')
        if n['type']=='n8n-nodes-base.postgres' and '{{' in n['parameters'].get('query',''):
            fail(file,'SQL interpolation needs manual review')
    workflow_info.append({'file':file.name,'nodes':len(doc['nodes'])})
report={'status':'PASS' if not errors else 'FAIL','files':len(files),
        'workflows':workflow_info,'images':images,'findings':errors,
        'limitations':['Heuristic scan; no OCR or end-to-end import/runtime validation.']}
print(json.dumps(report,ensure_ascii=True,indent=2))
sys.exit(1 if errors else 0)
