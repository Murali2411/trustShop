from __future__ import annotations
import json,re,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from .validation import parse_price, validate_product
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36','Accept-Language':'en-IN,en;q=0.9','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
CACHE={}; TTL=180
def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def fetch(url):
    now=time.time(); c=CACHE.get(url)
    if c and now-c[0]<TTL:return c[1]
    r=requests.get(url,headers=HEADERS,timeout=18); r.raise_for_status(); CACHE[url]=(now,r.text); return r.text
def money(text):
    return parse_price(text)
def cc(text):
    m=re.search(r'(\d{2,4}(?:\.\d+)?)\s*cc\b',text or '',re.I); return int(float(m.group(1))) if m else None

def cc_from_name(name):
    """Infer engine displacement from bike model name, e.g. 'Pulsar 150' → 150."""
    # Match displacement numbers that appear after make/model words
    m=re.search(r'(?<![.\d])(\b(?:1[0-9][0-9]|2[0-9][0-9]|3[0-9][0-9]|4[0-9][0-9]|[5-9][0-9]{2}|[12][0-9]{3})\b)(?![.\d])',name or '')
    if m:
        n=int(m.group(1))
        if 50<=n<=1400: return n
    return None
def jld(soup):
    out=[]
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            x=json.loads(s.string or s.get_text())
            out += x if isinstance(x,list) else [x]
        except: pass
    return [x for x in out if isinstance(x,dict)]
def key(url):return urlparse(url).path.rstrip('/').lower()
def dedupe(items):
    seen=set(); out=[]
    for x in items:
        k=key(x.get('source_url','')) or x.get('name','').lower()
        if k not in seen:seen.add(k);out.append(x)
    return out
def price_from_page(soup):
    token=r'(?:₹\s*)?\d[\d,]*(?:\.\d+)?\s*(?:lakh|lakhs|lac|crore|cr|k)?'
    for node in soup.select('[class*="price"], [id*="price"], [data-testid*="price"]'):
        text=clean(node.get_text(' ',strip=True))
        if re.search(r'emi|monthly|down\s*payment|finance|interest',text,re.I): continue
        if not re.search(r'₹|rs\.?|,|lakh|lac|crore|\bk\b', text, re.I): continue
        value=money(text)
        if value is not None:return value
    page=clean(soup.get_text(' ',strip=True))
    for label in ('ex[- ]showroom','on[- ]road','starting\s+from','starts?\s+at','price'):
        match=re.search(rf'(?i){label}\s*[:\-]?\s*({token})',page)
        if match:
            if not re.search(r'₹|rs\.?|,|lakh|lac|crore|\bk\b', match.group(1), re.I): continue
            value=money(match.group(1))
            if value is not None:return value
    return None
class Source:
    base=''
    def links(self,html):
        soup=BeautifulSoup(html,'html.parser'); out=[]
        for a in soup.find_all('a',href=True):
            href=urljoin(self.base,a['href']); text=clean(a.get_text(' ',strip=True))
            if self.is_link(href): out.append((href,text))
        return out
    def detail(self,url,hint):
        html=fetch(url); soup=BeautifulSoup(html,'html.parser'); text=clean(soup.get_text(' ',strip=True)); name=hint; price=None; image=None
        structured_price=None
        for x in jld(soup):
            if x.get('@type') in ('Product','Car','Vehicle'):
                name=name or x.get('name',''); image=x.get('image') if isinstance(x.get('image'),str) else None
                off=x.get('offers')
                if isinstance(off,dict):
                    structured_price=off.get('price') or off.get('lowPrice') or off.get('highPrice') or structured_price
                break
        h=soup.find('h1'); name=clean(h.get_text(' ',strip=True)) if h else (name or 'Vehicle')
        price=int(float(structured_price)) if structured_price is not None else price_from_page(soup)
        return name,price,text,image
    def filter(self,items,q,kind): return items,{'upgrade':None,'explanation':f'Live {kind} retrieval.'}
class BikeWaleSource(Source):
    base='https://www.bikewale.com'
    pages=['https://www.bikewale.com/new-bikes-in-india/']+[f'https://www.bikewale.com/new-bikes-in-india/page/{i}/' for i in range(2,9)]
    def is_link(self, u):
        p = urlparse(u).path.lower().strip('/')

        if 'bikewale.com' not in u:
            return False

        if not p:
            return False

        blocked = (
            'new-bikes-in-india',
            'new-bike-search',
            'upcoming-bikes',
            'electric-bikes',
            'used-bikes',
            'compare',
            'news',
            'reviews',
            'videos',
            'loan',
            'emi',
            'showroom',
            'sell',
            'user'
        )

        if any(x in p for x in blocked):
            return False

        parts = p.split('/')

        if len(parts) != 2:
            return False

        return (
            parts[0].endswith('-bikes')
            or parts[0].endswith('-scooters')
        )
    def search(self,q):
        try:
            links=[]
            for p in self.pages:
                try: links+=self.links(fetch(p))
                except: pass
            seen=set(); cand=[]
            for u,t in links:
                k=key(u)
                if k not in seen:seen.add(k);cand.append((u,t))
            cand=cand[:220]
            def work(z):
                try:
                    u,h=z;n,p,t,img=self.detail(u,h)
                    engine_cc=cc(t) or cc_from_name(n)
                    item={'id':'bikewale:'+key(u),'name':n,'brand':n.split()[0] if n else '','model':n,'price':p,'price_type':'BikeWale live price' if p is not None else 'Price unavailable','engine_cc':engine_cc,'store':'BikeWale','source':'BikeWale','source_url':u,'verified_at':'live retrieval','image':img}
                    return item if validate_product(item,'bike') else None
                except:return None
            out=[]
            with ThreadPoolExecutor(max_workers=10) as ex:
                for f in as_completed([ex.submit(work,x) for x in cand]):
                    x=f.result()
                    if x:out.append(x)
            return self.filter(dedupe(out),q,'BikeWale')
        except Exception as e:return [],{'upgrade':None,'explanation':f'BikeWale live retrieval failed: {e}. No local bike data was substituted.'}
    def filter(self,items,q,kind):
        b=q.get('budget'); brand=(q.get('brand') or '').lower(); model=(q.get('model') or '').lower(); category=(q.get('category_type') or '').lower(); keywords=(q.get('keywords') or '').lower(); mn=q.get('cc_min'); mx=q.get('cc_max'); target=q.get('target_cc')
        if brand:items=[x for x in items if brand in x['name'].lower() or brand in x['brand'].lower()]
        if model:items=[x for x in items if model in x.get('name','').lower()]
        if category:
            category_terms={
                'sports':('sport','r15','mt-15','apache','pulsar','gixxer','duke','rc','ninja','rs200','r3','ninja300','cbr'),
                'commuter':('splendor','shine','passion','platina','ct 100','raider','sp125','glamour','dream','livo','cb shine'),
                'cruiser':('classic','bullet','hunter','meteor','avenger','rebel','intruder','bonneville','fat boy'),
                'scooter':('scooter','activa','jupiter','access','ntorq','maestro','dio','ray','burgman','fascino'),
                'adventure':('adventure','xpulse','himalayan','v-strom','390 adventure','versys','tiger','africa twin','gs'),
                'electric':('ola','ather','tvs iq','bajaj ev','bounce','simple one','vida'),
            }.get(category,(category,))
            items=[x for x in items if any(term in x.get('name','').lower() for term in category_terms)]
        if keywords:
            stop={'bike','bikes','motorcycle','cc','engine','speed','mileage','fuel'}
            items=[x for x in items if all(token in x.get('name','').lower() for token in keywords.split() if token not in stop and len(token)>2)]
        # CC filtering — keep bikes with unknown cc (cc_from_name may have helped, but still allow unknowns)
        if mn is not None and mx is not None:
            items=[x for x in items if x.get('engine_cc') is None or mn<=x['engine_cc']<=mx]
        elif mn is not None:
            items=[x for x in items if x.get('engine_cc') is None or x['engine_cc']>=mn]
        elif mx is not None:
            items=[x for x in items if x.get('engine_cc') is None or x['engine_cc']<=mx]
        within=[x for x in items if b is None or (x.get('price') is not None and x['price']<=b)]
        # Compute cc_score for each item: how close to target cc
        if target:
            for x in within:
                ecc=x.get('engine_cc') or 0
                x['cc_delta']=abs(ecc-target) if ecc else 9999
                x['cc_score']=max(0,100-int(x['cc_delta']/target*100)) if target else 0
            within.sort(key=lambda x:(x.get('cc_delta',9999),x.get('price') is None,x.get('price') or float('inf')))
        else:
            within.sort(key=lambda x:(x.get('price') is None,x.get('price') or float('inf')))
        cc_note=f' Filtered to {mn or 0}–{mx or "any"}cc engine range.' if (mn or mx) else (f' Sorted by proximity to {target}cc.' if target else '')
        return within[:80],{'upgrade':None,'explanation':f'Live BikeWale retrieval. {len(within)} matching models found.{cc_note}'}
class CarDekhoSource(Source):
    base='https://www.cardekho.com'
    pages=['https://www.cardekho.com/newcars']+[f'https://www.cardekho.com/newcars?page={i}' for i in range(2,13)]
    def is_link(self,u):
        p=urlparse(u).path.lower(); parts=[x for x in p.split('/') if x]
        bad=('newcars','usedcars','compare','latestcars','mostpopularcars','electric-cars','news','advisory','sell','loan')
        return 'cardekho.com' in u and len(parts)==2 and not any(x in p for x in bad)
    def search(self,q):
        try:
            links=[]
            for p in self.pages:
                try:links+=self.links(fetch(p))
                except:pass
            seen=set();cand=[]
            for u,t in links:
                k=key(u)
                if k not in seen:seen.add(k);cand.append((u,t))
            cand=cand[:320]
            def work(z):
                try:
                    u,h=z;n,p,t,img=self.detail(u,h); low=t.lower(); fuel=next((v for v in ('electric','ev','diesel','petrol','cng','hybrid') if v in low),None); body=next((v for v in ('suv','hatchback','sedan','muv','coupe','convertible','pickup') if v in low),None); trans=next((v for v in ('automatic','manual') if v in low),None); sm=re.search(r'(\d)\s*(?:seater|seats|seat)',t,re.I)
                    # Extract engine displacement in cc
                    eng_cc=None
                    m_cc=re.search(r'(\d{3,4})\s*cc\b',t,re.I)
                    if m_cc: eng_cc=int(m_cc.group(1))
                    else:
                        m_l=re.search(r'(\d+(?:\.\d+)?)\s*(?:litre|liter|l)\b(?!\s*(?:boot|trunk|cargo))',t,re.I)
                        if m_l:
                            v=float(m_l.group(1))
                            if 0.5<v<6.0: eng_cc=int(v*1000)
                    item={'id':'cardekho:'+key(u),'name':n,'brand':n.split()[0] if n else '','model':n,'price':p,'price_type':'CarDekho live price' if p is not None else 'Price unavailable','body_type':body,'fuel':fuel,'transmission':trans,'seats':int(sm.group(1)) if sm else None,'engine_cc':eng_cc,'store':'CarDekho','source':'CarDekho','source_url':u,'verified_at':'live retrieval','image':img}
                    return item if validate_product(item,'car') else None
                except:return None
            out=[]
            with ThreadPoolExecutor(max_workers=12) as ex:
                for f in as_completed([ex.submit(work,x) for x in cand]):
                    x=f.result()
                    if x:out.append(x)
            return self.filter(dedupe(out),q,'CarDekho')
        except Exception as e:return [],{'upgrade':None,'explanation':f'CarDekho live retrieval failed: {e}. No local car data was substituted.'}
    def filter(self,items,q,kind):
        b=q.get('budget'); brand=(q.get('brand') or '').lower(); body=(q.get('body_type') or '').lower(); fuel=(q.get('fuel') or '').lower(); trans=(q.get('transmission') or '').lower(); seats=q.get('seats'); mn=q.get('cc_min'); mx=q.get('cc_max'); target=q.get('target_cc')
        if brand:items=[x for x in items if brand in x['name'].lower() or brand in x['brand'].lower()]
        if body:items=[x for x in items if x.get('body_type') and body in x['body_type']]
        if fuel:items=[x for x in items if x.get('fuel') and (fuel=='ev' and x['fuel']=='electric' or fuel!='ev' and fuel in x['fuel'])]
        if trans:items=[x for x in items if x.get('transmission') and trans in x['transmission']]
        if seats:items=[x for x in items if x.get('seats') is None or x['seats']>=seats]
        if mn is not None and mx is not None:
            items=[x for x in items if x.get('engine_cc') is None or mn<=x['engine_cc']<=mx]
        elif mn is not None:
            items=[x for x in items if x.get('engine_cc') is None or x['engine_cc']>=mn]
        elif mx is not None:
            items=[x for x in items if x.get('engine_cc') is None or x['engine_cc']<=mx]
        within=[x for x in items if b is None or (x.get('price') is not None and x['price']<=b)]
        if target:
            for x in within:
                ecc=x.get('engine_cc') or 0
                x['cc_delta']=abs(ecc-target) if ecc else 9999
            within.sort(key=lambda x:(x.get('cc_delta',9999),x.get('price') is None,x.get('price') or float('inf')))
        else:
            within.sort(key=lambda x:(x.get('price') is None,x.get('price') or float('inf')))
        cc_note=f' Filtered to {mn or 0}–{mx or "any"}cc engine.' if (mn or mx) else (f' Sorted by proximity to {target}cc engine.' if target else '')
        return within[:80],{'upgrade':None,'explanation':f'Live CarDekho retrieval. {len(within)} matching models found.{cc_note}'}
