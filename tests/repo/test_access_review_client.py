from __future__ import annotations
import importlib.util,json,pathlib,sys
import pytest

ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('access_review_client',ROOT/'scripts/access_review.py')
mod=importlib.util.module_from_spec(spec); assert spec.loader; sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

HEAD='a'*40
KEY='access-global'

def source_record():
    return {'kind':'source','review':{
      'review_id':'source-r1','source_id':'s1','target_state':'SHADOW','access_basis':'PUBLIC_PAGE_MONITOR',
      'terms_snapshot_at':'2026-09-15T00:00:00Z','evidence_id':'source-ev1','access_basis_valid':True,
      'privacy_review_pass':True,'parser_contract_pass':True,'provenance_hash_pass':True,'rate_budget_pass':True,'shadow_pass':False}}

def provider_record():
    return {'kind':'provider','review':{
      'review_id':'provider-r1','provider_id':'duffel','access_basis':'OFFICIAL_API','terms_snapshot_at':'2026-09-15T00:00:00Z',
      'rate_policy':'official-v1','evidence_id':'provider-ev1','access_basis_valid':True,'terms_review_pass':True,'rate_policy_review_pass':True}}

class FakeTransport:
    def __init__(self,head=HEAD):
        self.head=head; self.audit={}; self.reviews={}; self.calls=[]; self.lose_audit=False; self.lose_review=False; self.drop_audit=False; self.drop_review=False
    def health(self): return mod.HttpResult(200,{'ok':True,'spec':'1.3','mode':'SHADOW_ACCEPTANCE','commit_sha':self.head})
    def post(self,path,payload):
        self.calls.append((path,json.loads(json.dumps(payload))))
        if path=='/audit/evidence/readback': return mod.HttpResult(200,{'evidence':self.audit.get(payload['evidence_id'])})
        if path=='/access/reviews/readback':
            key=(payload['kind'],payload['entity_id'],payload.get('review_id'))
            return mod.HttpResult(200,self.reviews.get(key,{'kind':payload['kind'],'review':None,'registry':None}))
        if path=='/audit/evidence':
            if not self.drop_audit:self.audit[payload['evidence_id']]=json.loads(json.dumps(payload))
            if self.lose_audit: self.lose_audit=False; raise mod.TransportUnknown('lost')
            return mod.HttpResult(202,{'ok':True})
        if path in {'/sources/onboarding/review','/providers/access/review'}:
            kind='source' if path.startswith('/sources') else 'provider'; ek='source_id' if kind=='source' else 'provider_id'; entity=payload[ek]
            record={'kind':kind,'review':payload}; ph=mod.review_payload_hash(record)
            if kind=='source':
                checks={n:payload[n] for n in mod.SOURCE_FIELDS[-6:]}
                review={**payload,'payload_sha256':ph,'reviewer_key_id':KEY,'checks_json':checks,'created_at':'2026-09-15T01:00:00Z'}
                registry={'source_id':entity,'lifecycle_state':payload['target_state'],'status':payload['target_state'],'access_basis':payload['access_basis'],'terms_snapshot_at':payload['terms_snapshot_at'],'kill_switch':0,'kill_switch_state':'CLEAR'}
            else:
                checks={n:payload[n] for n in mod.PROVIDER_FIELDS[-3:]}
                review={**payload,'payload_sha256':ph,'reviewer_key_id':KEY,'checks_json':checks,'created_at':'2026-09-15T01:00:00Z'}
                registry={'provider_id':entity,'access_basis':payload['access_basis'],'terms_snapshot_at':payload['terms_snapshot_at'],'rate_policy':payload['rate_policy']}
            if not self.drop_review:self.reviews[(kind,entity,payload['review_id'])]={'kind':kind,'review':review,'registry':registry}
            if self.lose_review: self.lose_review=False; raise mod.TransportUnknown('lost')
            return mod.HttpResult(202,{'ok':True})
        raise AssertionError(path)

def test_strict_record_validation_and_payload_hash_stability(tmp_path):
    s=source_record(); p=provider_record()
    assert mod.validate_record(s)==s and mod.validate_record(p)==p
    assert len(mod.review_payload_hash(s))==64 and len(mod.review_payload_hash(p))==64
    bad=json.loads(json.dumps(p));bad['review']['extra']=1
    with pytest.raises(mod.AccessReviewError,match='ACCESS_REVIEW_FIELDS_INVALID'):mod.validate_record(bad)
    bad=json.loads(json.dumps(p));bad['review']['access_basis']='UNSUPPORTED_WRAPPER'
    with pytest.raises(mod.AccessReviewError,match='ACCESS_REVIEW_ACCESS_BASIS_INVALID'):mod.validate_record(bad)
    f=tmp_path/'r.jsonl';f.write_text(json.dumps(s)+'\n'+json.dumps(s)+'\n')
    with pytest.raises(mod.AccessReviewError,match='DUPLICATE_REVIEW_ID'):mod.load_jsonl(f)

def test_origin_requires_exact_head_and_explicit_fallback_agreement(tmp_path):
    ev=tmp_path/'worker-deploy.json';ev.write_text(json.dumps({'commit_sha':HEAD,'worker_origin':'https://fare.example'}))
    assert mod.resolve_base_url(HEAD,None,ev)=='https://fare.example'
    assert mod.resolve_base_url(HEAD,'https://fare.example/',ev)=='https://fare.example'
    with pytest.raises(mod.AccessReviewError,match='BASE_URL_MISMATCH'):mod.resolve_base_url(HEAD,'https://other.example',ev)
    with pytest.raises(mod.AccessReviewError,match='PROVIDER_HEAD_MISMATCH'):mod.resolve_base_url('b'*40,None,ev)
    assert mod.resolve_base_url(HEAD,'https://fallback.example',tmp_path/'absent.json')=='https://fallback.example'

def test_exact_replay_never_resends_mutations():
    t=FakeTransport(); records=[source_record(),provider_record()]
    first=mod.run(records,HEAD,KEY,t)
    writes=[p for p,_ in t.calls if p in {'/audit/evidence','/sources/onboarding/review','/providers/access/review'}]
    assert len(writes)==4 and all(x['audit']=='written' and x['review']=='written' for x in first)
    t.calls.clear(); second=mod.run(records,HEAD,KEY,t)
    assert all(x['audit']=='existing' and x['review']=='existing' for x in second)
    assert not [p for p,_ in t.calls if p in {'/audit/evidence','/sources/onboarding/review','/providers/access/review'}]

def test_lost_audit_and_review_responses_reconcile_without_resend():
    t=FakeTransport();t.lose_audit=True;t.lose_review=True
    got=mod.run([source_record()],HEAD,KEY,t)[0]
    assert got=={'review_id':'source-r1','audit':'reconciled','review':'reconciled'}
    assert sum(p=='/audit/evidence' for p,_ in t.calls)==1
    assert sum(p=='/sources/onboarding/review' for p,_ in t.calls)==1

def test_unknown_without_applied_state_fails_closed_and_does_not_retry():
    t=FakeTransport();t.lose_audit=True;t.drop_audit=True
    with pytest.raises(mod.AccessReviewError,match='ACCESS_REVIEW_TRANSPORT_UNKNOWN'):mod.run([source_record()],HEAD,KEY,t)
    assert sum(p=='/audit/evidence' for p,_ in t.calls)==1
    assert not any(p=='/sources/onboarding/review' for p,_ in t.calls)

def test_mismatched_prestate_blocks_zero_write():
    t=FakeTransport(); r=source_record(); ev=mod.evidence_for(r,HEAD,'2026-09-15T01:00:00Z');ev['test_report_hash']='0'*64;t.audit[r['review']['evidence_id']]=ev
    with pytest.raises(mod.AccessReviewError,match='AUDIT_PRESTATE_MISMATCH'):mod.run([r],HEAD,KEY,t)
    assert sum(p=='/audit/evidence' for p,_ in t.calls)==0

def test_dry_run_validates_health_and_readback_without_mutation():
    t=FakeTransport();got=mod.run([source_record()],HEAD,KEY,t,dry_run=True)[0]
    assert got['audit']=='would_write' and got['review']=='would_write'
    assert not [p for p,_ in t.calls if p in {'/audit/evidence','/sources/onboarding/review','/providers/access/review'}]

def test_health_requires_exact_commit_and_allowed_mode():
    t=FakeTransport('b'*40)
    with pytest.raises(mod.AccessReviewError,match='RUNTIME_IDENTITY_MISMATCH'):mod.verify_health(t,HEAD)
