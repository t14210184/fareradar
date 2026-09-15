export type VerificationState = "DETECTED" | "PARSED" | "STRATEGY_EXPANDED" | "COST_ESTIMATED" | "VERIFYING" | "PROBABLE" | "CONFIRMED" | "GHOST" | "EXPIRED" | "NEEDS_HUMAN";
export type FacetStatus = "PASS" | "FAIL" | "UNKNOWN" | "STALE";
export type RequiredFacet = "FARE_VERIFIED" | "DOCUMENT_CLEAR" | "CONNECTION_ACCEPTABLE" | "BAGGAGE_FEASIBLE" | "COST_COMPLETE" | "COUPON_SEQUENCE_CLEAR" | "POLICY_FRESH";
export const REQUIRED_FACETS: RequiredFacet[] = ["FARE_VERIFIED","DOCUMENT_CLEAR","CONNECTION_ACCEPTABLE","BAGGAGE_FEASIBLE","COST_COMPLETE","COUPON_SEQUENCE_CLEAR","POLICY_FRESH"];

export interface ItineraryCandidateInput {
  itinerary_id: string;
  strategy_type: string;
  cash_trip_cost_twd: number | null;
  cost_complete: boolean;
  risk_adjusted_cost_twd?: number | null;
  scenario_cost_twd?: { low: number; base: number; high: number } | null;
  generalized_cost_twd?: number | null;
  risk_class: string;
  verification_state: VerificationState;
}
export interface TicketComponentInput { ticket_id:string; pnr_group:string; provider:string; ticket_type:string; connection_protection_type:string; validating_carrier?:string|null; ticket_stock?:string|null; segments:unknown[]; fare_brand?:string|null; refund_rule?:string|null; change_rule?:string|null; }
export interface TransferBoundaryInput { boundary_id:string; from_ticket_id:string; to_ticket_id:string; airport:string; self_transfer:boolean; protection_type:string; validating_carrier?:string|null; mct_status?:string|null; requires_entry:boolean; requires_bag_reclaim:boolean; through_bag_status?:string|null; terminal_change:boolean; airport_change:boolean; scheduled_buffer_minutes:number; required_buffer_minutes:number; buffer_confidence:string; reaccommodation_basis?:string|null; evidence_id:string; }
export interface CostComponentInput { cost_id:string; type:string; amount:number; currency:string; twd_amount:number|null; inclusion_state:"INCLUDED_IN_OFFER"|"ADD_ON"|"UNKNOWN"; source_offer_id?:string|null; policy_evidence_id?:string|null; dedupe_key:string; certainty:string; effective_event_at?:string|null; paid_state:string; refundable:boolean; fx_snapshot_id?:string|null; observed_at:string; }
export interface ReadinessFacetInput { facet_type:RequiredFacet; status:FacetStatus; reason_code:string; observed_at:string; expires_at:string; authority:string; evidence_id:string; }
export interface DocumentRequirementInput { document_id:string; jurisdiction:string; travel_event:string; traveler_document_class:string; status:string; announced_at?:string|null; observed_at:string; effective_from?:string|null; effective_to?:string|null; valid_for_event_at:string; jurisdiction_timezone:string; authority_source:string; source_snapshot_id:string; }
export interface FourLegLiabilityInput { liability_id:string; cycle_id:string; component_type:"POSITIONING"|"MAIN_TICKET"|"TAIL_RETURN"|"HOTEL"|"DOCUMENT"; amount:number; paid_state:string; refundable:boolean; booking_deadline?:string|null; travel_deadline?:string|null; remaining_exposure:number; recoverable_amount:number; }
export interface CandidatePlanInput { intake_id:string; discovery_evidence_ids?:string[]; itinerary:ItineraryCandidateInput; tickets:TicketComponentInput[]; transfers:TransferBoundaryInput[]; costs:CostComponentInput[]; readiness:ReadinessFacetInput[]; documents:DocumentRequirementInput[]; four_leg_liabilities:FourLegLiabilityInput[]; }

export interface D1Result { success?: boolean; meta?: unknown; }
export interface D1PreparedStatement { bind(...values:unknown[]):D1PreparedStatement; run():Promise<D1Result>; first<T=unknown>():Promise<T|null>; all<T=unknown>():Promise<{results:T[]}>; }
export interface D1Database { prepare(sql:string):D1PreparedStatement; batch(statements:D1PreparedStatement[]):Promise<D1Result[]>; }
