from __future__ import annotations
import hashlib,json,urllib.request
API='https://api.duffel.com/air/offer_requests?return_offers=true&view=offers'
ALLOWED_CABINS={'economy','premium_economy','business','first'}

def build_request(query:dict)->dict:
    slices=query.get('slices') or []
    passengers=query.get('passengers') or []
    if not slices or not passengers: raise ValueError('DUFFEL_QUERY_INCOMPLETE')
    data={'slices':slices,'passengers':passengers}
    cabin=query.get('cabin_class')
    if cabin:
        if cabin not in ALLOWED_CABINS: raise ValueError('DUFFEL_CABIN_INVALID')
        data['cabin_class']=cabin
    if 'max_connections' in query: data['max_connections']=query['max_connections']
    return {'data':data}

def default_transport(url:str,headers:dict,body:bytes,timeout:int=35)->dict:
    req=urllib.request.Request(url,data=body,headers=headers,method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def search(query:dict,token:str,transport=default_transport)->dict:
    if not token: raise ValueError('DUFFEL_TOKEN_MISSING')
    payload=build_request(query)
    headers={'Accept':'application/json','Content-Type':'application/json','Duffel-Version':'v2','Authorization':f'Bearer {token}','User-Agent':'FareRadar/1.3'}
    response=transport(API,headers,json.dumps(payload,separators=(',',':')).encode())
    data=response.get('data') or {}
    offers=data.get('offers') or []
    if not isinstance(offers,list): raise ValueError('DUFFEL_RESPONSE_INVALID')
    return {'offer_request_id':data.get('id'),'offers':offers}


def canonical_structure(offer:dict):
    slices=[]
    for sl in offer.get('slices') or []:
        segs=[]
        for sg in sl.get('segments') or []:
            origin=(sg.get('origin') or {}).get('iata_code'); dest=(sg.get('destination') or {}).get('iata_code')
            dep=sg.get('departing_at'); arr=sg.get('arriving_at')
            if not all((origin,dest,dep,arr)): continue
            marketing=(sg.get('marketing_carrier') or {}).get('iata_code'); operating=(sg.get('operating_carrier') or {}).get('iata_code')
            segs.append({'origin':origin,'destination':dest,'departing_at':dep,'arriving_at':arr,'marketing_carrier':marketing,'operating_carrier':operating,'flight_number':sg.get('marketing_carrier_flight_number')})
        slices.append({'segments':segs})
    return {'slices':slices} if slices else None

def normalize_offer(offer:dict,query:dict,query_fingerprint:str,job_id:str,observed_at:str)->dict:
    oid=offer.get('id'); cur=offer.get('total_currency'); amount=offer.get('total_amount')
    if not oid or not cur or amount is None: raise ValueError('DUFFEL_OFFER_INVALID')
    raw=json.dumps(offer,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    return {
      'provider_offer_id':oid,'itinerary_id':None,'query_fingerprint':query_fingerprint,'provider':'duffel',
      'market':query.get('market'),'locale':query.get('locale'),'currency':cur,
      'passenger_mix':json.dumps(query.get('passengers',[]),separators=(',',':')),
      'baggage_query':json.dumps(query.get('baggage_query'),separators=(',',':')) if query.get('baggage_query') is not None else None,
      'observed_at':observed_at,'expires_at':offer.get('expires_at'),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
      'source_snapshot_id':job_id,'offer_total':float(amount),'fare_freshness':'LIVE','cached_or_live':'LIVE','offer_structure':canonical_structure(offer)
    }
