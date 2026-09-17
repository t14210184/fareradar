export function onboardingCandidates(newRoutes:string[]){return newRoutes.map(route=>({route,state:"DISCOVERED",confirmed_fare:false}));}
