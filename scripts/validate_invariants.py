from __future__ import annotations
import pathlib, sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[1]
db=sqlite3.connect(':memory:')
for p in sorted((ROOT/'migrations').glob('*.sql')): db.executescript(p.read_text())
required={
'itinerary_candidates':{'itinerary_id','strategy_type','verification_state'},
'ticket_components':{'ticket_id','pnr_group','connection_protection_type'},
'transfer_boundaries':{'from_ticket_id','to_ticket_id','scheduled_buffer_minutes','required_buffer_minutes','evidence_id'},
'cost_components':{'inclusion_state','source_offer_id','dedupe_key','paid_state','refundable'},
'readiness_facets':{'facet_type','status','expires_at','authority','evidence_id'},
'document_requirements':{'jurisdiction','travel_event','traveler_document_class','valid_for_event_at','authority_source','source_snapshot_id'},
'four_leg_liabilities':{'cycle_id','component_type','remaining_exposure','recoverable_amount'},
'audit_evidence':{'gate_id','spec_version','test_report_hash','provider_readback'} }
for table, cols in required.items():
    got={r[1] for r in db.execute(f'pragma table_info({table})')}
    missing=cols-got
    if missing: raise SystemExit(f'{table}: missing {sorted(missing)}')
print('SCHEMA_INVARIANTS_PASS')
