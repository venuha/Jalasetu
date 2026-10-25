"""Read-only public evidence retrieval. No synthetic fallback is emitted as an observation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from html.parser import HTMLParser
from io import BytesIO
import hashlib
import json
import math
import re
import httpx
from urllib.parse import urljoin,urlparse
from pypdf import PdfReader
from . import store
from .connections import tavily_key

NPP='https://npp.gov.in/publishedReports'
KRMB='https://krmb.gov.in/krmb/home'
SECONDARY='https://ap-reservoirs.vercel.app/reservoirs/srisailam-r'
IMD='https://api.imd.gov.in/api/v1/subdivision_rainfall_forecast'
ALLOWED={'npp.gov.in','krmb.gov.in','www.krmb.gov.in','api.open-meteo.com','api.imd.gov.in','ap-reservoirs.vercel.app'}

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.skip=0;self.parts=[];self.links=[];self.row=[];self.cell=[];self.rows=[];self.in_cell=False
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag in ['script','style']:self.skip+=1
        if tag=='a' and d.get('href'):self.links.append(d['href'])
        if tag=='tr':self.row=[]
        if tag in ['td','th']:self.in_cell=True;self.cell=[]
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.skip=max(0,self.skip-1)
        if tag in ['td','th']:
            self.row.append(' '.join(self.cell));self.in_cell=False
        if tag=='tr' and self.row:self.rows.append(self.row)
    def handle_data(self,data):
        if not self.skip:
            clean=' '.join(data.split())
            if clean:
                self.parts.append(clean)
                if self.in_cell:self.cell.append(clean)
    @property
    def text(self):return '\n'.join(self.parts)


def page(text):
    p=Page();p.feed(text);return p

def get(url,client=None,max_bytes=6_000_000):
    host=urlparse(url).hostname
    if host not in ALLOWED or urlparse(url).scheme!='https':raise ValueError('Source outside public-data allowlist')
    def call(c):
        with c.stream('GET',url,follow_redirects=False,timeout=18) as response:
            response.raise_for_status();chunks=[];size=0
            for part in response.iter_bytes():
                size+=len(part)
                if size>max_bytes:raise ValueError('Source response exceeds size limit')
                chunks.append(part)
            return b''.join(chunks)
    if client:return call(client)
    with httpx.Client(headers={'User-Agent':'JalaSetu/0.2 public-evidence-client'}) as c:return call(c)


def record(source,kind,value=None,unit=None,date=None,url=None,metric=None,name=None,excerpt=None,quality='official',page_number=None):
    age=None
    if date:
        try:age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(date).date()).days
        except ValueError:pass
    return dict(id=hashlib.sha256(f'{source}|{name}|{metric}|{date}'.encode()).hexdigest()[:16],
        source=source,source_type=quality,kind=kind,name=name,metric=metric,value=value,unit=unit,
        observed_date=date,retrieved_at=store.now(),age_days=age,
        freshness='unknown' if age is None else 'future date - investigate' if age<0 else 'dated - refresh required' if age>1 else 'recent dated report',
        url=url,excerpt=excerpt,page=page_number,operationally_verified=False)


def pdf_text(data):
    reader=PdfReader(BytesIO(data))
    if len(reader.pages)>90:raise ValueError('Report exceeds page limit')
    return [p.extract_text(extraction_mode='layout') or '' for p in reader.pages]


def parse_hydro(data,url):
    pages=pdf_text(data);out=[]
    for idx,text in enumerate(pages,1):
        match=re.search(r'Reservoir\s+For-\s*(\d{2}-[A-Za-z]{3}-\d{4})',text,re.I)
        date=datetime.strptime(match[1],'%d-%b-%Y').date().isoformat() if match else None
        for line in text.splitlines():
            name='Srisailam' if re.match(r'^\s*SRISAILAM\s+',line) else 'Nagarjuna Sagar' if re.match(r'^\s*NAGARJUN\s+SAGAR\s+',line) else None
            if not name:continue
            values=re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?',line)
            if len(values)!=16:raise ValueError('Hydro report column count changed; engineer review required')
            nums=list(map(float,values))
            if not all(math.isfinite(n) and n>=0 for n in nums):raise ValueError('Invalid report quantity')
            out.append(record('CEA / National Power Portal','reservoir',nums[3],'ft',date,url,'reservoir_level',name,line.strip(),page_number=idx))
            out.append(record('CEA / National Power Portal','reservoir',nums[13],'MCM',date,url,'effective_capacity_at_present_level',name,line.strip(),page_number=idx))
    if not out:raise ValueError('Expected Telangana/Krishna hydro rows missing')
    return out


def parse_generation(data,url):
    pages=pdf_text(data);out=[];in_telangana=False
    for idx,text in enumerate(pages,1):
        m=re.search(r'GENERATION REPORT FOR\s+(\d{2}/\d{2}/\d{4})',text)
        date=datetime.strptime(m[1],'%d/%m/%Y').date().isoformat() if m else None
        for line in text.splitlines():
            if line.strip()=='TELANGANA':in_telangana=True;continue
            if in_telangana and line.strip()=='EASTERN':in_telangana=False
            if in_telangana and line.strip().startswith('STATE TOTAL'):
                nums=list(map(float,re.findall(r'\d+(?:\.\d+)?',line)))
                if len(nums)<6:raise ValueError('Generation summary columns changed')
                out.append(record('CEA / National Power Portal','power',nums[2],'MU',date,url,'daily_generation_actual','Telangana monitored stations',line.strip(),page_number=idx))
            if line.strip().startswith('SRISAILAM LB HPS'):
                nums=list(map(float,re.findall(r'\d+(?:\.\d+)?',line)))
                if len(nums)>=6:out.append(record('CEA / National Power Portal','power',nums[2],'MU',date,url,'daily_generation_actual','Srisailam left-bank HPS',line.strip(),page_number=idx))
    if not out:raise ValueError('Telangana generation rows missing')
    return out


def collect_npp():
    p=page(get(NPP).decode('utf-8',errors='replace'));links={}
    for href in p.links:
        for num in [2,6]:
            if re.search(rf'/dgr{num}-\d{{4}}-\d{{2}}-\d{{2}}\.pdf$',href):
                candidate=urljoin(NPP,href)
                if num not in links or candidate.rsplit('/',1)[-1]>links[num].rsplit('/',1)[-1]:links[num]=candidate
    observations=[];errors=[]
    for num,fn in [(6,parse_hydro),(2,parse_generation)]:
        try:
            if num not in links:raise ValueError('Expected report link absent from official index')
            observations+=fn(get(links[num]),links[num])
        except Exception as e:
            errors.append(dict(source='NPP report '+str(num),status='unavailable',reason=type(e).__name__,url=links.get(num,NPP)))
    return dict(source='National Power Portal',status='retrieved' if observations else 'no validated observations',observations=observations,issues=errors,
        scope='Dated generation and effective hydro capacity, not feeder status, gross irrigation storage or dispatch availability.')


def collect_krmb():
    p=page(get(KRMB).decode('utf-8',errors='replace'));obs=[]
    for row in p.rows:
        joined=' '.join(row).lower()
        name='Srisailam' if 'srisailam' in joined else 'Nagarjuna Sagar' if 'nagarjuna' in joined else 'Jurala' if 'jurala' in joined else None
        if not name or len(row)!=4:continue
        try:
            level=float(row[1].replace(',',''));storage=float(row[2].replace(',',''))
            date=datetime.strptime(row[3].strip(),'%d/%m/%Y').date().isoformat()
        except ValueError:continue
        obs += [record('Krishna River Management Board','reservoir',level,'ft',date,KRMB,'reservoir_level',name,' | '.join(row)),
                record('Krishna River Management Board','reservoir',storage,'TMC',date,KRMB,'reported_storage',name,' | '.join(row))]
    if not obs:raise ValueError('Daily table unavailable or schema changed')
    return dict(source='KRMB',status='retrieved',observations=obs,issues=[],scope='Reported storage with reading date; operating reserves and command access still require verification.')


def collect_secondary():
    p=page(get(SECONDARY).decode('utf-8',errors='replace'));text=p.text
    # Scope to the latest information section, never search historical rows for a convenient value.
    m=re.search(r'Latest\s+SRISAILAM R\s+Reservoir Information\s+(.+?)Historical\s+SRISAILAM R',text,re.S)
    if not m:raise ValueError('Secondary reservoir layout changed')
    block=m[1];d=re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})',block)
    date=datetime.strptime(d[1],'%d %b %Y').date().isoformat() if d else None
    observations=[]
    for label,metric,unit in [('Storage','reported_storage','TMC'),('Water level','reservoir_level','ft')]:
        match=re.search(r'(?:^|\n)'+label+r'\s+([\d,.]+)',block)
        if match:observations.append(record('AP Reservoirs independent dashboard','reservoir',float(match[1].replace(',','')),unit,date,SECONDARY,metric,'Srisailam',match[0].strip(),quality='secondary - corroboration required'))
    if not observations:raise ValueError('No validated latest secondary observation')
    return dict(source='Independent reservoir dashboard',status='retrieved',observations=observations,issues=[],scope='Secondary source attributing APWRIMS; not independently authenticated government telemetry.')


def collect_weather(lat,lon):
    from .integrations import weather
    result=weather(lat,lon)
    if result.get('error'):raise ValueError(result['error'])
    dates=result['daily']['time'];result['retrieved_at']=store.now()
    return dict(source='Open-Meteo',status='retrieved',observations=[],forecast=result,issues=[],scope='Model forecast at selected reservoir coordinates; not observed farm rainfall.',forecast_period=[dates[0],dates[-1]])


def safe_call(name,fn):
    try:return fn()
    except Exception as e:
        return dict(source=name,status='unavailable',observations=[],issues=[dict(source=name,status='unavailable',reason=type(e).__name__,message=str(e)[:180])])


def refresh(lat=16.08,lon=78.90,include_secondary=True):
    jobs=[('NPP',collect_npp),('KRMB',collect_krmb),('Weather',lambda:collect_weather(lat,lon))]
    jobs.append(('IMD',lambda:dict(source='IMD',status='retrieved',observations=[],raw=json.loads(get(IMD)),issues=[],scope='Subdivision rainfall forecast; district and field mapping require verification.')))
    if include_secondary:jobs.append(('Secondary reservoir',collect_secondary))
    with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda item:safe_call(*item),jobs))
    report=dict(id=store.now(),retrieved_at=store.now(),coordinates=dict(latitude=lat,longitude=lon),sources=results,
        observations=[o for r in results for o in r.get('observations',[])],
        boundaries=['No synthetic fallback is labelled as a public observation.','Effective hydro capacity is not interchangeable with gross reservoir storage.','State generation cannot guarantee village feeder supply.','Forecast rain is not measured effective rain.'],
        issues=[i for r in results for i in r.get('issues',[])])
    with store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS public_evidence (id INTEGER PRIMARY KEY, body TEXT)')
        c.execute('INSERT INTO public_evidence(body) VALUES(?)',(json.dumps(report),))
    return report


def latest():
    with store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS public_evidence (id INTEGER PRIMARY KEY, body TEXT)')
        row=c.execute('SELECT body FROM public_evidence ORDER BY id DESC LIMIT 1').fetchone()
        return json.loads(row[0]) if row else None


def search_public(query):
    key=tavily_key()
    if not key:return dict(status='not configured',results=[],message='Add a Tavily key in Connections. Direct public-source fetches still work without it.')
    try:
        r=httpx.post('https://api.tavily.com/search',headers={'Authorization':'Bearer '+key},json=dict(query=query[:500],max_results=5,search_depth='basic',include_answer=False,include_domains=['krmb.gov.in','cwc.gov.in','npp.gov.in','telangana.gov.in','imd.gov.in','tgtransco.com']),timeout=20)
        r.raise_for_status();data=r.json()
        return dict(status='retrieved',query=query,results=[dict(title=x.get('title'),url=x.get('url'),excerpt=x.get('content','')[:1200],score=x.get('score'),published_date=x.get('published_date')) for x in data.get('results',[])],
            note='Search excerpts are leads, not validated operating measurements. Follow the source date and scope.')
    except (httpx.HTTPError,ValueError):return dict(status='unavailable',results=[],message='Tavily request failed. No substitute search result was fabricated.')
