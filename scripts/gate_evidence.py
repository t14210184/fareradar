from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pathlib, re, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'; OUT.mkdir(exist_ok=True)
SPEC=ROOT/'docs/SPEC_v1.3.md'
STAGE_SIZE=8

def sha256_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha256_file(path:pathlib.Path)->str:return sha256_bytes(path.read_bytes())
def tree_hash(paths:list[pathlib.Path])->str:
    h=hashlib.sha256()
    for p in sorted(paths,key=lambda x:x.as_posix()):
        rel=p.relative_to(ROOT).as_posix().encode(); h.update(rel+b'\0'+p.read_bytes()+b'\0')
    return h.hexdigest()
def git_head()->str:return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def clean_worktree()->bool:return subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()==''
def dependency_lock_hash()->str:
    xs=[p for p in [ROOT/'package-lock.json',ROOT/'requirements-dev.txt'] if p.exists()]
    return tree_hash(xs)
def test_corpus_hash()->str:
    return tree_hash([p for p in (ROOT/'tests').rglob('*') if p.is_file() and '__pycache__' not in p.parts])
def context()->dict:
    return {'commit_sha':git_head(),'spec_sha256':sha256_file(SPEC),'dependency_lock_hash':dependency_lock_hash(),'test_corpus_hash':test_corpus_hash()}
def parse_gate_table()->list[dict]:
    text=SPEC.read_text()
    sec=text.split('## 43.2 Gate-to-test executable mapping',1)[1].split('## 43.3',1)[0]
    rows=[]
    pat=re.compile(r'^\|\s*(PG\d{2})\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$',re.M)
    for gate,cmd,threshold in pat.findall(sec):rows.append({'gate_id':gate,'exact_command':cmd.strip(),'acceptance_threshold':threshold.strip()})
    expected=[f'PG{i:02d}' for i in range(37)]
    got=[r['gate_id'] for r in rows]
    if got!=expected:raise RuntimeError(f'GATE_MAPPING_INVALID:{got}')
    return rows

def run_gate(row:dict,ctx:dict)->dict:
    start=dt.datetime.now(dt.timezone.utc).isoformat()
    env=os.environ.copy(); env['FARE_SKIP_BUILD']='1'
    try:
        p=subprocess.run(row['exact_command'],shell=True,cwd=ROOT,text=True,capture_output=True,env=env,timeout=90)
        end=dt.datetime.now(dt.timezone.utc).isoformat(); output=p.stdout+p.stderr; rc=p.returncode
        status='LOCAL_TEST_PASS' if rc==0 else 'LOCAL_TEST_FAIL'
    except subprocess.TimeoutExpired as e:
        end=dt.datetime.now(dt.timezone.utc).isoformat(); output=((e.stdout or '')+(e.stderr or '')) if isinstance(e.stdout,str) else ''; rc=124; status='LOCAL_TEST_FAIL'
    return {**row,**ctx,'start':start,'end':end,'returncode':rc,'status':status,'report_sha256':sha256_bytes(output.encode()),'output_tail':output[-1600:]}

def stage_path(n:int)->pathlib.Path:return OUT/f'gate-stage-{n}.json'
def write_stage(n:int)->dict:
    if not clean_worktree():raise SystemExit('GATE_WORKTREE_NOT_CLEAN')
    rows=parse_gate_table(); start=n*STAGE_SIZE; subset=rows[start:start+STAGE_SIZE]
    if not subset:raise SystemExit('GATE_STAGE_OUT_OF_RANGE')
    subprocess.run(['tsc','-p','tsconfig.json','--noEmit'],cwd=ROOT,check=True)
    ctx=context()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(4,len(subset))) as ex:
        results=list(ex.map(lambda r: run_gate(r,ctx),subset))
    doc={'schema_version':2,'stage':n,'context':ctx,'gates':results,'summary':{'LOCAL_TEST_PASS':sum(r['status']=='LOCAL_TEST_PASS' for r in results),'LOCAL_TEST_FAIL':sum(r['status']=='LOCAL_TEST_FAIL' for r in results)}}
    stage_path(n).write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    print(json.dumps({'stage':n,**doc['summary']},ensure_ascii=False))
    if doc['summary']['LOCAL_TEST_FAIL']:raise SystemExit(1)
    return doc

def load_stages()->tuple[dict,list[dict]]:
    current=context(); all_rows=[]
    for n in range(5):
        p=stage_path(n)
        if not p.exists():raise SystemExit(f'GATE_STAGE_MISSING:{n}')
        d=json.loads(p.read_text())
        if d.get('context')!=current:raise SystemExit(f'GATE_STAGE_CONTEXT_MISMATCH:{n}')
        all_rows.extend(d.get('gates') or [])
    expected=[f'PG{i:02d}' for i in range(37)]
    if [r.get('gate_id') for r in all_rows]!=expected:raise SystemExit('GATE_STAGE_SET_INVALID')
    if any(r.get('status')!='LOCAL_TEST_PASS' for r in all_rows):raise SystemExit('GATE_STAGE_NOT_PASS')
    return current,all_rows

def finalize()->dict:
    if not clean_worktree():raise SystemExit('GATE_WORKTREE_NOT_CLEAN')
    current,rows=load_stages()
    start=dt.datetime.now(dt.timezone.utc).isoformat()
    env=os.environ.copy(); env['FARE_SKIP_BUILD']='1'
    tmp=tempfile.NamedTemporaryFile(prefix='fare-gate-full-',suffix='.log',mode='w',encoding='utf-8',delete=False)
    report_path=pathlib.Path(tmp.name); tmp.close(); rc=124
    try:
        with report_path.open('w',encoding='utf-8') as report:
            p=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,text=True,stdout=report,stderr=subprocess.STDOUT,env=env,timeout=180)
            rc=p.returncode
    except subprocess.TimeoutExpired:
        rc=124
    end=dt.datetime.now(dt.timezone.utc).isoformat(); output=report_path.read_text(encoding='utf-8',errors='replace') if report_path.exists() else ''
    report_path.unlink(missing_ok=True)
    full={'status':'FULL_SUITE_PASS' if rc==0 else 'FULL_SUITE_FAIL','returncode':rc,'start':start,'end':end,'report_sha256':sha256_bytes(output.encode()),'output_tail':output[-2400:]}
    doc={'schema_version':2,**current,'observed_at':end,'production_pass':0,'gates':rows,'full_suite':full,'summary':{'LOCAL_TEST_PASS':37,'LOCAL_TEST_FAIL':0,'EVIDENCE_INCOMPLETE':0}}
    (OUT/'gate-evidence-latest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    print(json.dumps({'gates':37,'full_suite':full['status'],'commit_sha':current['commit_sha']},ensure_ascii=False))
    if p.returncode:raise SystemExit(1)
    return doc

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stage',type=int); ap.add_argument('--finalize',action='store_true'); args=ap.parse_args()
    if args.stage is not None:return write_stage(args.stage)
    if args.finalize:return finalize()
    for n in range(5):write_stage(n)
    return finalize()
if __name__=='__main__':main()
