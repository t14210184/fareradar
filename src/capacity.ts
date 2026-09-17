export function quotaDegrade(usageRatio:number){return usageRatio>=0.95?{mode:"CRITICAL_ONLY",keep:["P0_INGEST","OUTBOX","HEARTBEAT"]}:{mode:"NORMAL",keep:["ALL"]};}
export function win11State(online:boolean){return online?{system:"HEALTHY",heavy_verifier:"AVAILABLE"}:{system:"DEGRADED",heavy_verifier:"UNAVAILABLE"};}
export function burstDecision(i:{queue:number;duplicates:number;schemaDrift:number}){if(i.schemaDrift>20)return "QUARANTINE";if(i.queue>1000||i.duplicates>500)return "DOWNSHIFT";return "KEEP";}

export function workerBudget(input:{batchItems:number;d1Statements:number;continuationCursor:boolean}){ const allowed=input.batchItems<=10&&input.d1Statements<=50; return {allowed,should_continue:input.continuationCursor||!allowed,max_batch_items:10,max_d1_statements:50}; }
