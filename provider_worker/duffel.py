from __future__ import annotations
import hashlib,json,urllib.request
SEARCH_API='https://api.duffel.com/air/offer_requests?return_offers=true&view=offers'
OFFER_API='https://api.duffel.com/air/offers/{offer_id}?return_available_services=true'
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
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def default_get_transport(url:str,headers:dict,timeout:int=25)->dict:
    req=urllib.request.Request(url,headers=headers,method='GET')
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def headers(token:str)->dict:
    return {'Accept':'application/json','Content-Type':'application/json','Duffel-Version':'v2','Authorization':f'Bearer {token}','User-Agent':'FareRadar/1.3'}

def search(query:dict,token:str,transport=default_transport)->dict:
    if not token: raise ValueError('DUFFEL_TOKEN_MISSING')
    response=transport(SEARCH_API,headers(token),json.dumps(build_request(query),separators=(',',':')).encode())
    data=response.get('data') or {}; offers=data.get('offers') or []
    if not isinstance(offers,list): raise ValueError('DUFFEL_RESPONSE_INVALID')
    return {'offer_request_id':data.get('id'),'offers':offers}

def refresh_offer(offer_id:str,token:str,transport=default_get_transport)->dict:
    if not offer_id or not token: raise ValueError('DUFFEL_OFFER_REFRESH_INPUT_INVALID')
    response=transport(OFFER_API.format(offer_id=offer_id),headers(token)); data=response.get('data') or {}
    if data.get('id')!=offer_id: raise ValueError('DUFFEL_OFFER_REFRESH_INVALID')
    return data

def _bag_list(passengers):
    out=[]
    for p in passengers or []:
        bags=[]
        for b in p.get('baggages') or []:
            if not isinstance(b,dict): continue
            bags.append({k:b.get(k) for k in ('type','quantity') if b.get(k) is not None})
        out.append({'passenger_id':p.get('passenger_id'),'baggages':bags})
    return out

def _services(services):
    out=[]
    for s in services or []:
        if not isinstance(s,dict): continue
        out.append({k:s.get(k) for k in ('id','type','total_currency','total_amount','segment_ids','passenger_ids','maximum_quantity','metadata') if s.get(k) is not None})
    return out

def canonical_structure(offer:dict):
    slices=[]
    for sl in offer.get('slices') or []:
        segs=[]
        for sg in sl.get('segments') or []:
            origin=(sg.get('origin') or {}).get('iata_code'); dest=(sg.get('destination') or {}).get('iata_code')
            dep=sg.get('departing_at'); arr=sg.get('arriving_at')
            if not all((origin,dest,dep,arr)): continue
            marketing=(sg.get('marketing_carrier') or {}).get('iata_code'); operating=(sg.get('operating_carrier') or {}).get('iata_code')
            segs.append({'segment_id':sg.get('id'),'origin':origin,'destination':dest,'departing_at':dep,'arriving_at':arr,'marketing_carrier':marketing,'operating_carrier':operating,'flight_number':sg.get('marketing_carrier_flight_number'),'passengers':_bag_list(sg.get('passengers'))})
        slices.append({'segments':segs})
    if not slices:return None
    return {'slices':slices,'available_services':_services(offer.get('available_services')),'price_scope':'FLIGHT_TOTAL_INCLUDES_TAX_EXCLUDES_SERVICES'}

def normalize_offer(offer:dict,query:dict,query_fingerprint:str,job_id:str,observed_at:str,fare_freshness='LIVE')->dict:
    oid=offer.get('id'); cur=offer.get('total_currency'); amount=offer.get('total_amount')
    if not oid or not cur or amount is None: raise ValueError('DUFFEL_OFFER_INVALID')
    raw=json.dumps(offer,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    return {
      'provider_offer_id':oid,'itinerary_id':None,'query_fingerprint':query_fingerprint,'provider':'duffel',
      'market':query.get('market'),'locale':query.get('locale'),'currency':cur,
      'passenger_mix':json.dumps(query.get('passengers',[]),separators=(',',':')),
      'baggage_query':json.dumps(query.get('baggage_query'),separators=(',',':')) if query.get('baggage_query') is not None else None,
      'observed_at':observed_at,'expires_at':offer.get('expires_at'),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
      'source_snapshot_id':job_id,'offer_total':float(amount),'fare_freshness':fare_freshness,'cached_or_live':'LIVE','offer_structure':canonical_structure(offer)
    }
