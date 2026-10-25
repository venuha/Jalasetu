import concurrent.futures,json,httpx
from pathlib import Path
urls={'npp_hydro':'https://npp.gov.in/public-reports/cea/daily/dgr/22-10-2026/dgr6-2026-10-22.pdf','npp_generation':'https://npp.gov.in/public-reports/cea/daily/dgr/22-10-2026/dgr2-2026-10-22.pdf','secondary':'https://ap-reservoirs.vercel.app/reservoirs/srisailam-r','reservoir_index':'https://ap-reservoirs.vercel.app/reservoirs','apwrims':'https://apwrims.ap.gov.in/'}
def f(pair):
 name,url=pair
 try:
  r=httpx.get(url,timeout=20,follow_redirects=True)
  print(json.dumps(dict(name=name,status=r.status_code,bytes=len(r.content),type=r.headers.get('content-type'))),flush=True)
  if r.status_code==200:Path('/private/tmp/jalasetu-'+name+('.pdf' if r.content.startswith(b'%PDF') else '.txt')).write_bytes(r.content)
 except httpx.HTTPError as e:print(json.dumps(dict(name=name,error=type(e).__name__)),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(f,urls.items()))
