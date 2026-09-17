export const ACTIVE_STRATEGIES=Array.from({length:20},(_,i)=>`S${String(i).padStart(2,"0")}`);
export function boundedExpand<T extends {cash:number;elapsed:number;risk:number;tickets:number}>(items:T[],maxTickets=4){
  const filtered=items.filter(x=>x.tickets<=maxTickets);
  return filtered.filter((a,i)=>!filtered.some((b,j)=>j!==i&&b.cash<=a.cash&&b.elapsed<=a.elapsed&&b.risk<=a.risk&&(b.cash<a.cash||b.elapsed<a.elapsed||b.risk<a.risk)));
}
export function foreignOriginCycleCost(x:{main:number;positioning:number;tail:number;taxes:number;hotel:number;ground:number;documents:number}){return x.main+x.positioning+x.tail+x.taxes+x.hotel+x.ground+x.documents;}
export function priceBeatEligible(x:{same_route:boolean;same_date:boolean;comparable_fare:boolean;competitor_official:boolean;within_window:boolean}){return Object.values(x).every(Boolean);}

export interface StrategyCandidate {
  id:string;
  strategy_id:string;
  cash:number;
  elapsed:number;
  risk:number;
  tickets:number;
  estimated_saving_vs_baseline:number;
  route_prior?:number;
  self_transfers?:number;
  overnights?:number;
  hard_filters_pass?:boolean;
}
export interface StrategySearchOptions {
  expansion_threshold:number;
  max_tickets:number;
  max_self_transfers:number;
  max_overnights:number;
  max_nodes:number;
  mainland_enabled?:boolean;
  advanced_enabled?:boolean;
}
const STRATEGY_LEVEL:Record<string,number>={
  S00:0,S01:0,S02:0,S03:0,S04:1,S05:1,S06:2,S07:2,S08:2,S09:3,
  S10:2,S11:3,S12:3,S13:4,S14:4,S15:5,S16:0,S17:0,S18:0,S19:0
};
export function strategyLevel(strategyId:string){const level=STRATEGY_LEVEL[strategyId];if(level===undefined)throw new Error("UNKNOWN_STRATEGY");return level;}
export function boundedStrategySearch<T extends StrategyCandidate>(items:T[],options:StrategySearchOptions){
  if(!Number.isFinite(options.expansion_threshold)||options.expansion_threshold<0)throw new Error("EXPANSION_THRESHOLD_INVALID");
  if(!Number.isInteger(options.max_tickets)||options.max_tickets<1||!Number.isInteger(options.max_nodes)||options.max_nodes<1)throw new Error("SEARCH_BUDGET_INVALID");
  const active=new Set(ACTIVE_STRATEGIES);
  const eligible=items.filter(x=>{
    if(!active.has(x.strategy_id))return false;
    const level=strategyLevel(x.strategy_id);
    if(level>0&&x.estimated_saving_vs_baseline<options.expansion_threshold)return false;
    if((x.strategy_id==="S10"||x.strategy_id==="S11")&&!options.mainland_enabled)return false;
    if(x.strategy_id==="S15"&&!options.advanced_enabled)return false;
    if(x.hard_filters_pass===false)return false;
    if(x.tickets>options.max_tickets)return false;
    if((x.self_transfers??0)>options.max_self_transfers)return false;
    if((x.overnights??0)>options.max_overnights)return false;
    return Number.isFinite(x.cash)&&Number.isFinite(x.elapsed)&&Number.isFinite(x.risk)&&Number.isFinite(x.estimated_saving_vs_baseline);
  });
  const ordered=[...eligible].sort((a,b)=>
    a.cash-b.cash || a.risk-b.risk || a.elapsed-b.elapsed || (b.route_prior??0)-(a.route_prior??0) || strategyLevel(a.strategy_id)-strategyLevel(b.strategy_id) || a.id.localeCompare(b.id)
  ).slice(0,options.max_nodes);
  const pareto=ordered.filter((a,i)=>!ordered.some((b,j)=>j!==i&&b.cash<=a.cash&&b.elapsed<=a.elapsed&&b.risk<=a.risk&&(b.cash<a.cash||b.elapsed<a.elapsed||b.risk<a.risk)));
  return pareto.sort((a,b)=>a.cash-b.cash || a.elapsed-b.elapsed || a.risk-b.risk || a.id.localeCompare(b.id));
}
