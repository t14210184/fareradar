export const ACTIVE_STRATEGIES=Array.from({length:20},(_,i)=>`S${String(i).padStart(2,"0")}`);
export function boundedExpand<T extends {cash:number;elapsed:number;risk:number;tickets:number}>(items:T[],maxTickets=4){
  const filtered=items.filter(x=>x.tickets<=maxTickets);
  return filtered.filter((a,i)=>!filtered.some((b,j)=>j!==i&&b.cash<=a.cash&&b.elapsed<=a.elapsed&&b.risk<=a.risk&&(b.cash<a.cash||b.elapsed<a.elapsed||b.risk<a.risk)));
}
export function foreignOriginCycleCost(x:{main:number;positioning:number;tail:number;taxes:number;hotel:number;ground:number;documents:number}){return x.main+x.positioning+x.tail+x.taxes+x.hotel+x.ground+x.documents;}
export function priceBeatEligible(x:{same_route:boolean;same_date:boolean;comparable_fare:boolean;competitor_official:boolean;within_window:boolean}){return Object.values(x).every(Boolean);}
