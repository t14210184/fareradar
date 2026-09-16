from __future__ import annotations
import argparse,datetime as dt,hashlib,json,os,pathlib,re,subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'; OUT.mkdir(exist_ok=True)
SPEC=ROOT/'docs/SPEC_v1.3.md'
GATE_STAGE_SIZE=8
SUITE_STAGE_COUNT=5


def sha256_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha256_file(path:pathlib.Path)->str:return sha256_bytes(path.read_bytes())
def hash_paths(paths:list[pathlib.Path])->str:
    h=hashlib.sha256()
    for path in sorted(paths,key=lambda p:p.as_posix()):
        rel=path.relative_to(ROOT).as_posix().encode(); data=path.read_bytes()
        h.update(len(rel).to_bytes(4,'big'));h.update(rel);h.update(len(data).to_bytes(8,'big'));h.update(data)
    return h.hexdigest()
def git_head()->str:return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def dependency_lock_hash()->str:return hash_paths([ROOT/'package-lock.json',ROOT/'requirements-dev.txt'])
def test_corpus_hash()->str:
    out=subprocess.check_output(['git','ls-files','tests'],cwd=ROOT,text=True).splitlines()
    return hash_paths([ROOT/x for x in out if (ROOT/x).is_file()])
def context()->dict:
    return {'commit_sha':git_head(),'spec_sha256':sha256_file(SPEC),'dependency_lock_sha256':dependency_lock_hash(),'test_corpus_sha256':test_corpus_hash()}

def parse_gate_mapping()->list[dict]:
    text=SPEC.read_text()
    m=re.search(r'## 43\.2 Gate-to-test executable mapping\n(.*?)(?:\n## 43\.3 )',text,re.S)
    if not m:raise RuntimeError('SPEC_GATE_MAPPING_NOT_FOUND')
    rows=[]
    for line in m.group(1).splitlines():
        mm=re.match(r'\|\s*(PG\d{2})\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$',line)
        if mm:rows.append({'gate_id':mm.group(1),'exact_command':mm.group(2),'expected_threshold':mm.group(3)})
    expected=[f'PG{i:02d}' for i in range(37)]
    if [r['gate_id'] for r in rows]!=expected:raise RuntimeError('SPEC_GATE_MAPPING_INCOMPLETE')
    if any(not r['expected_threshold'] for r in rows):raise RuntimeError('SPEC_GATE_THRESHOLD_MISSING')
    return rows

def _run(cmd:str)->tuple[int,str]:
    env=os.environ.copy();env['FARE_SKIP_BUILD']='1'
    p=subprocess.run(cmd,shell=True,cwd=ROOT,text=True,capture_output=True,env=env)
    return p.returncode,p.stdout+p.stderr

def run_gate(row:dict,ctx:dict)->dict:
    start=dt.datetime.now(dt.timezone.utc).isoformat(); rc,out=_run(row['exact_command']); end=dt.datetime.now(dt.timezone.utc).isoformat()
    return {**row,**ctx,'spec_version':'1.3','start':start,'end':end,'status':'LOCAL_TEST_PASS' if rc==0 else 'LOCAL_TEST_FAIL','returncode':rc,'report_sha256':sha256_bytes(out.encode()),'actual_result':'PASS' if rc==0 else 'FAIL','unresolved_items':[] if rc==0 else ['TEST_COMMAND_FAILED'],'output_tail':out[-1200:]}

def gate_stage(index:int)->dict:
    rows=parse_gate_mapping(); start=index*GATE_STAGE_SIZE; selected=rows[start:start+GATE_STAGE_SIZE]
    if not selected:raise RuntimeError('GATE_STAGE_OUT_OF_RANGE')
    ctx=context(); subprocess.run(['npx','tsc','-p','tsconfig.json','--noEmit'],cwd=ROOT,check=True)
    with ThreadPoolExecutor(max_workers=min(4,len(selected))) as ex:results=list(ex.map(lambda row:run_gate(row,ctx),selected))
    doc={'schema_version':2,'kind':'gate-stage','stage':index,'context':ctx,'gates':results}
    (OUT/f'gate-stage-{index}.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    return doc

def suite_files()->list[str]:
    xs=subprocess.check_output(['git','ls-files','tests/test_*.py','tests/*/test_*.py'],cwd=ROOT,text=True).splitlines()
    return sorted(set(x for x in xs if (ROOT/x).is_file()))
def suite_stage(index:int)->dict:
    files=suite_files(); groups=[files[i::SUITE_STAGE_COUNT] for i in range(SUITE_STAGE_COUNT)]
    if index<0 or index>=SUITE_STAGE_COUNT:raise RuntimeError('SUITE_STAGE_OUT_OF_RANGE')
    selected=groups[index];ctx=context();cmd='pytest -q '+' '.join(selected)
    start=dt.datetime.now(dt.timezone.utc).isoformat();rc,out=_run(cmd);end=dt.datetime.now(dt.timezone.utc).isoformat()
    doc={'schema_version':2,'kind':'suite-stage','stage':index,'context':ctx,'exact_command':cmd,'files':selected,'start':start,'end':end,'status':'FULL_SUITE_STAGE_PASS' if rc==0 else 'FULL_SUITE_STAGE_FAIL','returncode':rc,'report_sha256':sha256_bytes(out.encode()),'output_tail':out[-1600:]}
    (OUT/f'full-suite-stage-{index}.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2))
    return doc

def finalize()->dict:
    ctx=context(); mapping=parse_gate_mapping(); all_gates=[]; suite_docs=[]
    for i in range((len(mapping)+GATE_STAGE_SIZE-1)//GATE_STAGE_SIZE):
        p=OUT/f'gate-stage-{i}.json'
        if not p.exists():raise RuntimeError(f'GATE_STAGE_{i}_MISSING')
        d=json.loads(p.read_text())
        if d.get('context')!=ctx:raise RuntimeError(f'GATE_STAGE_{i}_CONTEXT_MISMATCH')
        all_gates.extend(d.get('gates',[]))
    for i in range(SUITE_STAGE_COUNT):
        p=OUT/f'full-suite-stage-{i}.json'
        if not p.exists():raise RuntimeError(f'FULL_SUITE_STAGE_{i}_MISSING')
        d=json.loads(p.read_text())
        if d.get('context')!=ctx:raise RuntimeError(f'FULL_SUITE_STAGE_{i}_CONTEXT_MISMATCH')
        if d.get('status')!='FULL_SUITE_STAGE_PASS':raise RuntimeError(f'FULL_SUITE_STAGE_{i}_FAILED')
        suite_docs.append(d)
    ids=[g.get('gate_id') for g in all_gates]
    expected=[r['gate_id'] for r in mapping]
    if ids!=expected:raise RuntimeError('FINAL_GATE_SET_MISMATCH')
    current={r['gate_id']:r for r in mapping}
    for g in all_gates:
        spec=current[g['gate_id']]
        if g.get('status')!='LOCAL_TEST_PASS' or g.get('exact_command')!=spec['exact_command'] or g.get('expected_threshold')!=spec['expected_threshold']:raise RuntimeError(f"GATE_NOT_CURRENT_PASS:{g['gate_id']}")
        if g.get('commit_sha')!=ctx['commit_sha'] or g.get('spec_sha256')!=ctx['spec_sha256'] or g.get('dependency_lock_sha256')!=ctx['dependency_lock_sha256'] or g.get('test_corpus_sha256')!=ctx['test_corpus_sha256']:raise RuntimeError(f"GATE_CONTEXT_MISMATCH:{g['gate_id']}")
    suite_files_seen=sorted(x for d in suite_docs for x in d['files'])
    if suite_files_seen!=suite_files():raise RuntimeError('FULL_SUITE_FILE_COVERAGE_MISMATCH')
    suite_digest=sha256_bytes(''.join(d['report_sha256'] for d in suite_docs).encode())
    doc={'schema_version':2,'spec_version':'1.3',**ctx,'production_pass':0,'gates':all_gates,'summary':{'LOCAL_TEST_PASS':37,'LOCAL_TEST_FAIL':0,'EVIDENCE_INCOMPLETE':0},'full_suite':{'status':'FULL_SUITE_PASS','stage_count':SUITE_STAGE_COUNT,'file_count':len(suite_files_seen),'report_sha256':suite_digest}}
    path=OUT/'gate-evidence-latest.json';path.write_text(json.dumps(doc,ensure_ascii=False,indent=2));return doc

def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--stage',type=int);g.add_argument('--suite-stage',type=int);g.add_argument('--finalize',action='store_true');g.add_argument('--show-context',action='store_true');a=ap.parse_args()
    if a.stage is not None:d=gate_stage(a.stage);print(json.dumps({'stage':a.stage,'pass':sum(x['status']=='LOCAL_TEST_PASS' for x in d['gates']),'total':len(d['gates'])}));raise SystemExit(1 if any(x['status']!='LOCAL_TEST_PASS' for x in d['gates']) else 0)
    if a.suite_stage is not None:d=suite_stage(a.suite_stage);print(json.dumps({'suite_stage':a.suite_stage,'status':d['status'],'files':len(d['files'])}));raise SystemExit(0 if d['status']=='FULL_SUITE_STAGE_PASS' else 1)
    if a.finalize:d=finalize();print(json.dumps({'commit_sha':d['commit_sha'],'summary':d['summary'],'full_suite':d['full_suite']}));return
    print(json.dumps(context(),indent=2))
if __name__=='__main__':main()
