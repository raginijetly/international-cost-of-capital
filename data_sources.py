"""Validated source parsers. Missing data raises errors; no invented fallback rates."""
from datetime import datetime, timezone
from io import BytesIO, StringIO
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

BETAS='https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
SPREAD='https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
TAX='https://sdmx.oecd.org/public/rest/v1/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A.CIT_C.ST..S13...?format=csvfile'
BONDS='https://tradingeconomics.com/bonds'

def get(url):
    r=requests.get(url,timeout=35,headers={'User-Agent':'Mozilla/5.0 (educational cost-of-capital app)'})
    r.raise_for_status()
    return r

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def beta_data():
    book=pd.ExcelFile(BytesIO(get(BETAS).content),engine='xlrd')
    for sheet in book.sheet_names:
        raw=pd.read_excel(book,sheet_name=sheet,header=None)
        for i,row in raw.iterrows():
            cols=[str(c).strip() for c in row]
            if 'Industry Name' not in cols or not any(c.lower()=='unlevered beta' for c in cols):
                continue
            b=next(j for j,c in enumerate(cols) if c.lower()=='unlevered beta')
            n=cols.index('Industry Name')
            out=raw.iloc[i+1:,[n,b]].copy();out.columns=['Industry','Unlevered beta']
            out['Unlevered beta']=pd.to_numeric(out['Unlevered beta'],errors='coerce')
            out=out.dropna();out=out[~out.Industry.astype(str).str.contains('Total Market',case=False)]
            if len(out)<10: raise ValueError('Unexpected beta table.')
            meta='Not published'
            for _, header in raw.iloc[:i].iterrows():
                if any('date updated' in str(v).lower() for v in header):
                    meta=' '.join(str(v) for v in header.dropna().tolist()[:2])
            return out.reset_index(drop=True), {'source':BETAS,'as_of':meta.strip(),'fetched_utc':stamp()}
    raise ValueError('Industry / unlevered beta columns not found.')

def spread_data():
    soup=BeautifulSoup(get(SPREAD).text,'html.parser')
    for tr in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
        for i,c in enumerate(cells):
            if c.replace(' ','')=='Baa2/BBB':
                value=float(cells[i+1].replace('%','').strip())/100
                if not 0<=value<=1: raise ValueError('Invalid spread.')
                date=re.search(r'Data used is as of\s+([^\n]+)',soup.get_text('\n',strip=True))
                return value, {'source':SPREAD,'as_of':date.group(1) if date else 'Not published','fetched_utc':stamp()}
    raise ValueError('Baa2/BBB row not found.')

def tax_data():
    df=pd.read_csv(StringIO(get(TAX).text))
    df=df[(df.MEASURE=='CIT_C')&(df.SECTOR=='S13')&(df.TARGETING=='ST')].copy()
    df['OBS_VALUE']=pd.to_numeric(df.OBS_VALUE,errors='coerce');df=df.dropna(subset=['OBS_VALUE'])
    df=df.sort_values('TIME_PERIOD').groupby('REF_AREA',as_index=False).tail(1)
    if df.REF_AREA.duplicated().any() or not (df.OBS_VALUE.between(0,100)).all():
        raise ValueError('Unexpected OECD tax rows.')
    return df[['REF_AREA','TIME_PERIOD','OBS_VALUE']], {'source':TAX,'as_of':'Latest available year for each country (shown below)','fetched_utc':stamp()}

def parse_country_bond(html, country, url):
    """Match the exact 10-year link inside a Yield table, never the first price."""
    soup=BeautifulSoup(html,'html.parser')
    from urllib.parse import urlsplit
    path=urlsplit(url).path.rstrip('/')
    for table in soup.select('table'):
        heads=[x.get_text(' ',strip=True).lower() for x in table.select('thead th')]
        if 'yield' not in heads: continue
        pos=heads.index('yield')
        for tr in table.select('tr'):
            cells=tr.find_all('td',recursive=False)
            link=tr.find('a',href=lambda h: bool(h) and urlsplit(h).path.rstrip('/')==path)
            if not link or len(cells)<=pos: continue
            if not re.search(r'10\s*(?:Y|year)',link.get_text(' ',strip=True),re.I): continue
            value=float(cells[pos].get_text(strip=True).replace('%','').replace(',',''))/100
            if not -1<value<2: raise ValueError('Unexpected government yield.')
            date=tr.find('td',id='date')
            observed=date.get_text(' ',strip=True) if date else 'Not published'
            # The table's month/day omits a year. Preserve the full dated observation
            # from the page description when present; do not label fetch time as data time.
            meta=soup.find('meta',attrs={'name':'description'})
            match=re.search(r'on ([A-Z][a-z]+ \d{1,2}, \d{4})',meta.get('content','') if meta else '')
            if match: observed=match.group(1)
            return {'Country':country,'Yield':value,'Observation date':observed,'Source':url,'Fetched UTC':stamp()}
    raise ValueError('No matching 10-year yield row found on the country page.')


def country_bond(country):
    slugs={'United States':'united-states','United Kingdom':'united-kingdom',
           'Korea, Republic of':'south-korea','South Korea':'south-korea',
           'Russian Federation':'russia',
           'Türkiye':'turkey','Turkey':'turkey','Viet Nam':'vietnam',
           'Taiwan, Province of China':'taiwan','Iran, Islamic Republic of':'iran',
           'Venezuela, Bolivarian Republic of':'venezuela','Czechia':'czech-republic'}
    slug=slugs.get(country,country.lower().replace(' ','-'))
    base='https://tradingeconomics.com/'+slug+'/government-bond-yield'
    errors=[]
    # Public embedded view is an alternative rendering of the same source page.
    for url in [base,base+'?embed']:
        try:
            response=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
            response.raise_for_status()
            return parse_country_bond(response.text,country,url)
        except (requests.RequestException,ValueError) as exc:
            errors.append(str(exc))
    raise ValueError(country+': '+errors[-1])


def bond_data(country='United States'):
    rows=[];errors=[]
    for name in dict.fromkeys(['United States',country]):
        try: rows.append(country_bond(name))
        except ValueError as exc: errors.append(str(exc))
    if not rows: raise ValueError('; '.join(errors))
    return pd.DataFrame(rows), {'source':'Trading Economics country 10-year government yield pages',
        'as_of':'Per-row observation dates shown in source table',
        'fetched_utc':stamp(),'fetch_errors':errors}
