"""Local first API; never sends uploaded traces to an external service."""
import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .analyzer import ImportProblem, parse_import, MAX_BYTES
from .demo import demo_cases
from .storage import init_db, get_cases, get_case, overview, save_cases, connection, clear_demo

ROOT=Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with connection() as db:
        existing=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
    if not existing:
        save_cases(demo_cases())
    yield

app = FastAPI(title='Agentopsy', version='0.1.0', lifespan=lifespan)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')

@app.get('/')
def index():
    return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/health')
def health():
    return {'ok':True,'mode':'local','upload_limit_mb':8}

@app.get('/api/overview')
def get_overview(source: str='all'):
    return overview(source)

@app.get('/api/cases')
def list_cases(source:str='all', status:str='all', q:str='', limit:int=Query(default=1500,ge=1,le=2000)):
    return {'cases':get_cases(source,status,q,limit)}

@app.get('/api/cases/{case_id}')
def detail(case_id:str):
    item=get_case(case_id)
    if not item:
        raise HTTPException(404,'Case not found')
    return item

@app.post('/api/import')
async def import_jsonl(request:Request):
    if request.headers.get('content-type','').split(';')[0] not in ('application/octet-stream','application/x-ndjson','application/jsonl'):
        raise HTTPException(415,'Upload raw JSONL bytes, not multipart form data.')
    if int(request.headers.get('content-length','0') or 0)>MAX_BYTES:
        raise HTTPException(413,'File exceeds 8 MB.')
    data=await request.body()
    try:
        source,cases=parse_import(data)
    except ImportProblem as exc:
        raise HTTPException(422,str(exc)) from exc
    clear_demo()
    return {'format':source,'imported':save_cases(cases),
            'privacy':'Only extracted metadata and safe event categories are stored in local SQLite.'}

@app.delete('/api/demo')
def delete_demo():
    return {'deleted':clear_demo()}

@app.get('/api/export.csv')
def export_csv():
    cases=get_cases(limit=2000)
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=['id','source','agent','model','task','category','outcome','step_count','issue_count','incorrect_stages','is_demo'])
    writer.writeheader()
    for c in cases:
        writer.writerow({k:c[k] for k in writer.fieldnames})
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="agentopsy_cases.csv"'})
