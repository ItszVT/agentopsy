"""Local first API; never sends uploaded traces to an external service."""
import csv
import io
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from .analyzer import ImportProblem, parse_import, MAX_BYTES
from .demo import demo_cases
from .failure import failure_lab
from .research import research_findings
from . import storage
from .public_demo import load_seed, ATTRIBUTION, SOURCE_PAGE, LICENSE_URL, CITATION_URL, NOTICES_PATH
from .storage import init_db, get_cases, get_case, overview, save_cases, connection, clear_demo, performance_lab

ROOT=Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = os.environ.get('AGENTOPSY_MODE', 'local')
    if mode not in ('local', 'demo-preview', 'public'):
        raise RuntimeError('Unknown AGENTOPSY_MODE; use local, demo-preview, or public.')
    app.state.mode = mode
    app.state.read_only = mode != 'local'
    app.state.demo_ready = False
    if mode == 'public' and not os.environ.get('AGENTOPSY_DATA_PERMISSION_REFERENCE', '').strip():
        raise RuntimeError('Public demo blocked: confirm dataset display/redistribution rights using the reviewed official source and notices. See DATASET_LICENSE.md.')
    previous_path = storage.DB_PATH
    temporary = None
    try:
        if app.state.read_only:
            cases = load_seed(os.environ.get('AGENTOPSY_DEMO_SEED', str(ROOT.parent/'data'/'public-demo-nju.json')))
            temporary = tempfile.TemporaryDirectory(prefix='agentopsy-demo-')
            storage.DB_PATH = Path(temporary.name)/'demo.sqlite'
            init_db()
            save_cases(cases)
            # All request connections become SQLite read-only after seeding.
            storage.READ_ONLY = True
            app.state.demo_ready = True
        else:
            init_db()
            with connection() as db:
                existing=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
            if not existing:
                save_cases(demo_cases())
        yield
    finally:
        storage.READ_ONLY = False
        app.state.demo_ready = False
        storage.DB_PATH = previous_path
        if temporary:
            temporary.cleanup()

app = FastAPI(title='Agentopsy', version='0.1.0', lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')


@app.middleware('http')
async def public_boundary(request: Request, call_next):
    read_only = os.environ.get('AGENTOPSY_MODE', 'local') != 'local'
    if read_only and not getattr(app.state, 'demo_ready', False):
        return JSONResponse({'detail':'Benchmark demo is not ready.'}, status_code=503)
    if read_only and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        return JSONResponse({'detail':'This benchmark demo is read-only. Run Agentopsy locally to import private traces.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    if read_only:
        response.headers['Link'] = '</dataset-notices.txt>; rel="license"'
    return response

@app.get('/')
def index():
    return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/health')
def health():
    return {'ok':True, 'mode':getattr(app.state, 'mode', 'local'),
            'read_only':getattr(app.state, 'read_only', False), 'upload_limit_mb':8,
            'attribution':ATTRIBUTION, 'source_url':SOURCE_PAGE,
            'dataset_license':'MIT', 'license_url':LICENSE_URL,
            'notices_url':'/dataset-notices.txt', 'citation_url':CITATION_URL}


@app.get('/dataset-notices.txt')
def dataset_notices():
    return FileResponse(NOTICES_PATH, media_type='text/plain; charset=utf-8')

@app.get('/api/overview')
def get_overview(source: str='all'):
    return overview(source)

@app.get('/api/cases')
def list_cases(source:str='all', status:str='all', q:str='', limit:int=Query(default=1500,ge=1,le=2000)):
    return {'cases':get_cases(source,status,q,limit)}


@app.get('/api/performance')
def get_performance(agent: str | None = None, category: str | None = None,
                    outcome: str | None = None):
    return performance_lab(agent, category, outcome)


@app.get('/api/failure-lab')
def get_failure_lab(agent: str | None = None, category: str | None = None,
                    outcome: str | None = None, signal: str | None = None,
                    min_steps: int | None = Query(default=None, ge=0),
                    max_steps: int | None = Query(default=None, ge=0)):
    if min_steps is not None and max_steps is not None and min_steps > max_steps:
        raise HTTPException(422, 'Minimum steps must not exceed maximum steps.')
    return failure_lab(agent, category, outcome, min_steps, max_steps, signal)


@app.get('/api/findings')
def get_findings(agent: str | None = None, category: str | None = None):
    return research_findings(agent, category)

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
    raw_length=request.headers.get('content-length')
    if raw_length is not None:
        try:
            length=int(raw_length)
        except ValueError:
            raise HTTPException(400,'Invalid content length.')
        if length < 0:
            raise HTTPException(400,'Invalid content length.')
        if length>MAX_BYTES:
            raise HTTPException(413,'File exceeds 8 MB.')
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>MAX_BYTES:
            raise HTTPException(413,'File exceeds 8 MB.')
        data.extend(chunk)
    try:
        source,cases=parse_import(bytes(data))
    except ImportProblem as exc:
        raise HTTPException(422,str(exc)) from exc
    ids = {c['id'] for c in cases}
    with connection() as db:
        existing = {r['id'] for r in db.execute('SELECT id FROM cases')}
    clear_demo()
    return {'format':source,'imported':save_cases(cases),
            'records': {'unique':len(ids), 'inserted':len(ids-existing),
                        'updated':len(ids & existing), 'duplicate_rows':len(cases)-len(ids)},
            'privacy':'Only extracted metadata and safe event categories are stored in local SQLite.'}

@app.delete('/api/demo')
def delete_demo():
    return {'deleted':clear_demo()}

@app.get('/api/export.csv')
def export_csv():
    cases=get_cases(limit=2000)
    output=io.StringIO()
    fields=['id','source','agent','model','task','category','outcome','step_count','issue_count','incorrect_stages','is_demo']
    read_only=getattr(app.state,'read_only',False)
    if read_only:
        fields+=['dataset_source','dataset_license','license_notice']
    writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    for index,c in enumerate(cases):
        row={k:c[k] for k in fields if k in c}
        if read_only:
            row.update(dataset_source=SOURCE_PAGE,dataset_license='MIT',
                       license_notice=NOTICES_PATH.read_text(encoding='utf-8') if index==0 else '')
        writer.writerow(row)
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="agentopsy_cases.csv"'})
