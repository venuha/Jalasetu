import concurrent.futures,json,httpx
urls={
 'krmb':'https://krmb.gov.in/krmb/home',
 'ap_des':'https://desweather.ap.gov.in/Realtime/ReservoirData.jsp',
 'npp':'https://npp.gov.in/publishedReports',
 'imd':'https://api.imd.gov.in/api/v1/subdivision_rainfall_forecast',
 'weather':'https://api.open-meteo.com/v1/forecast?latitude=16.08&longitude=78.90&daily=precipitation_sum,et0_fao_evapotranspiration,precipitation_probability_max&timezone=Asia%2FKolkata&forecast_days=7',
}
def probe(pair):
 name,url=pair
 try:
  r=httpx.get(url,timeout=18,follow_redirects=True,headers={'User-Agent':'JalaSetu/0.2 public-data-research'})
  print(json.dumps(dict(source=name,status=r.status_code,bytes=len(r.content),type=r.headers.get('content-type'),sample=r.text[:250])),flush=True)
  if r.status_code==200:
   from pathlib import Path
   Path('/private/tmp/jalasetu-'+name+'.txt').write_text(r.text)
 except httpx.HTTPError as e: print(json.dumps(dict(source=name,error=type(e).__name__,detail=str(e)[:180])),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(probe,urls.items()))
