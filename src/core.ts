import { REQUIRED_FACETS, type CostComponentInput, type ReadinessFacetInput, type VerificationState } from "./types.js";

export function cashTripCost(offerTotalTwd:number, components:CostComponentInput[]) {
  let total = offerTotalTwd;
  let complete = true;
  const seen = new Set<string>();
  for (const c of components) {
    if (seen.has(c.dedupe_key)) continue;
    seen.add(c.dedupe_key);
    if (c.inclusion_state === "UNKNOWN") complete = false;
    if (c.inclusion_state === "ADD_ON") {
      if (c.twd_amount == null || !Number.isFinite(c.twd_amount)) complete = false;
      else total += c.twd_amount;
    }
  }
  return { cash_trip_cost_twd: total, cost_complete: complete };
}

export function actionable(verificationState:VerificationState, facets:ReadinessFacetInput[], at = new Date()):boolean {
  if (verificationState !== "CONFIRMED") return false;
  const byType = new Map(facets.map(f => [f.facet_type, f]));
  for (const type of REQUIRED_FACETS) {
    const facet = byType.get(type);
    if (!facet || facet.status !== "PASS") return false;
    const expires = Date.parse(facet.expires_at);
    if (!Number.isFinite(expires) || expires <= at.getTime()) return false;
  }
  return true;
}

export function validateScenarioCost(s:{low:number;base:number;high:number}|null|undefined) {
  if (!s) return true;
  return Number.isFinite(s.low) && Number.isFinite(s.base) && Number.isFinite(s.high) && s.low <= s.base && s.base <= s.high;
}
