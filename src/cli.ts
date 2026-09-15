import { actionable, cashTripCost } from "./core.js";
import { validateCandidatePlan } from "./intake.js";
const input=JSON.parse(process.argv[3]??"null");
let out:unknown;
switch(process.argv[2]){
  case "actionable": out=actionable(input.verification_state,input.facets,new Date(input.at));break;
  case "cash": out=cashTripCost(input.offer_total_twd,input.components);break;
  case "validate-plan": out=validateCandidatePlan(input);break;
  default: throw new Error("UNKNOWN_COMMAND");
}
console.log(JSON.stringify(out));
