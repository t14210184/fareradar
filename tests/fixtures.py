from datetime import datetime, timedelta, timezone

def plan():
    now=datetime(2026,9,15,tzinfo=timezone.utc)
    exp=(now+timedelta(hours=2)).isoformat()
    obs=now.isoformat()
    facets=[{"facet_type":x,"status":"PASS","reason_code":"OK","observed_at":obs,"expires_at":exp,"authority":"TEST","evidence_id":"ev-"+x.lower()} for x in ["FARE_VERIFIED","DOCUMENT_CLEAR","CONNECTION_ACCEPTABLE","BAGGAGE_FEASIBLE","COST_COMPLETE","COUPON_SEQUENCE_CLEAR","POLICY_FRESH"]]
    return {
      "intake_id":"intake-001",
      "itinerary":{"itinerary_id":"itin-001","strategy_type":"KR_SELF_TRANSFER","cash_trip_cost_twd":5900,"cost_complete":True,"risk_adjusted_cost_twd":None,"scenario_cost_twd":{"low":5900,"base":7600,"high":14500},"generalized_cost_twd":None,"risk_class":"HIGH","verification_state":"CONFIRMED"},
      "tickets":[
        {"ticket_id":"t1","pnr_group":"p1","provider":"airline-a","ticket_type":"ONE_WAY","connection_protection_type":"SEPARATE_UNPROTECTED","segments":[{"from":"TPE","to":"ICN"}]},
        {"ticket_id":"t2","pnr_group":"p2","provider":"airline-b","ticket_type":"ONE_WAY","connection_protection_type":"SEPARATE_UNPROTECTED","segments":[{"from":"ICN","to":"NRT"}]}
      ],
      "transfers":[{"boundary_id":"b1","from_ticket_id":"t1","to_ticket_id":"t2","airport":"ICN","self_transfer":True,"protection_type":"SEPARATE_UNPROTECTED","requires_entry":True,"requires_bag_reclaim":True,"terminal_change":False,"airport_change":False,"scheduled_buffer_minutes":300,"required_buffer_minutes":240,"buffer_confidence":"MEDIUM","evidence_id":"ev-transfer"}],
      "costs":[{"cost_id":"c1","type":"OFFER_TOTAL","amount":5000,"currency":"TWD","twd_amount":5000,"inclusion_state":"INCLUDED_IN_OFFER","source_offer_id":"off1","dedupe_key":"offer-total","certainty":"CONFIRMED","paid_state":"UNPAID","refundable":False,"observed_at":obs},{"cost_id":"c2","type":"BAGGAGE","amount":900,"currency":"TWD","twd_amount":900,"inclusion_state":"ADD_ON","source_offer_id":"off1","dedupe_key":"bag-20kg","certainty":"CONFIRMED","paid_state":"UNPAID","refundable":False,"observed_at":obs}],
      "readiness":facets,
      "documents":[{"document_id":"d1","jurisdiction":"KR","travel_event":"SELF_TRANSFER_ENTRY","traveler_document_class":"TW_PASSPORT","status":"CLEAR","observed_at":obs,"valid_for_event_at":"2026-11-10T00:00:00+09:00","jurisdiction_timezone":"Asia/Seoul","authority_source":"OFFICIAL","source_snapshot_id":"snap-kr"}],
      "four_leg_liabilities":[]
    }
