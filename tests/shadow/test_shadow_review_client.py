import pathlib
import sys
import pytest

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import shadow_review as m

COMMIT='d'*40
KEY='shadow-reviewer'

def review(sample='s1'):
    return {'sample_id':sample,'subject_id':'itin-1','subject_type':'ITINERARY','observed_at':'2026-09-16T00:00:00Z','label':'TRUE_DEAL','complex':True,'source_discovery':False,'agency_clearance':False,'false_actionable':False,'safety_error_code':None,'evidence_id':'intake-1'}

def row(r):
    return {**r,'complex':1,'source_discovery':0,'agency_clearance':0,'false_actionable':0,'reviewer_key_id':KEY,'commit_sha':COMMIT,'strategy_type':'S09'}

class Fake:
    def __init__(self, mode): self.mode=mode; self.calls=[]; self.stored={}
    def request(self, method,path,payload=None,signed=True):
        self.calls.append((method,path,payload))
        if path=='/health': return {'spec':'1.3','deployment_mode':'SHADOW_ACCEPTANCE','commit_sha':COMMIT}
        if path=='/shadow/reviews/readback': return {'review':self.stored.get(payload['sample_id'])}
        if path=='/shadow/acceptance/readback': return {'pass':False}
        if path=='/shadow/reviews':
            r=payload
            if self.mode=='timeout_applied': self.stored[r['sample_id']]=row(r); raise m.TransportUnknown('x')
            if self.mode=='timeout_absent': raise m.TransportUnknown('x')
            self.stored[r['sample_id']]=row(r); return {'ok':True}
        raise AssertionError(path)

def mutation_calls(fake): return [c for c in fake.calls if c[1]=='/shadow/reviews']

def test_prereadback_exact_skips_mutation():
    r=review(); f=Fake('normal'); f.stored[r['sample_id']]=row(r)
    out=m.submit_reviews([r],transport=f,key_id=KEY,commit=COMMIT)
    assert out['already_confirmed']==1 and out['written']==0 and mutation_calls(f)==[]

def test_timeout_applied_reconciles_without_resend():
    r=review(); f=Fake('timeout_applied')
    out=m.submit_reviews([r],transport=f,key_id=KEY,commit=COMMIT)
    assert out['already_confirmed']==1 and len(mutation_calls(f))==1
    assert [p for _,p,_ in f.calls].count('/shadow/reviews/readback')==2

def test_timeout_absent_fails_without_blind_resend():
    r=review(); f=Fake('timeout_absent')
    with pytest.raises(m.TransportUnknown,match='UNKNOWN_NOT_APPLIED'): m.submit_reviews([r],transport=f,key_id=KEY,commit=COMMIT)
    assert len(mutation_calls(f))==1

def test_prereadback_mismatch_blocks_write():
    r=review(); f=Fake('normal'); bad=row(r); bad['label']='NORMAL'; f.stored[r['sample_id']]=bad
    with pytest.raises(m.ShadowReviewError,match='PREREADBACK_MISMATCH'): m.submit_reviews([r],transport=f,key_id=KEY,commit=COMMIT)
    assert mutation_calls(f)==[]

def test_runtime_identity_mismatch_blocks_all_review_calls():
    r=review(); f=Fake('normal')
    original=f.request
    def wrong(method,path,payload=None,signed=True):
        if path=='/health': return {'spec':'1.3','deployment_mode':'PRODUCTION','commit_sha':COMMIT}
        return original(method,path,payload,signed)
    f.request=wrong
    with pytest.raises(m.ShadowReviewError,match='RUNTIME_IDENTITY_MISMATCH'): m.submit_reviews([r],transport=f,key_id=KEY,commit=COMMIT)
    assert mutation_calls(f)==[]

def test_load_reviews_rejects_duplicate_sample_and_unit(tmp_path):
    import json
    r=review(); p=tmp_path/'x.jsonl'; p.write_text(json.dumps(r)+'\n'+json.dumps(r)+'\n')
    with pytest.raises(m.ShadowReviewError,match='DUPLICATE_SAMPLE_ID'): m.load_reviews(p)
    r2=review('s2'); p.write_text(json.dumps(r)+'\n'+json.dumps(r2)+'\n')
    with pytest.raises(m.ShadowReviewError,match='DUPLICATE_REVIEW_UNIT'): m.load_reviews(p)
