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

def bond_data():
    html=get(BONDS).text
    soup=BeautifulSoup(html,'html.parser');rows=[]
    for table in soup.select('table'):
        heads=[x.get_text(' ',strip=True).lower() for x in table.select('thead th')]
        # Verify the numeric field by its header, rather than assuming a column position.
        pos=next((i for i,x in enumerate(heads) if x in ('yield','last')),None)
        if pos is None: continue
        for tr in table.select('tbody tr'):
            cells=tr.find_all('td')
            link=tr.find('a',href=re.compile(r'/government-bond-yield'))
            if not link or len(cells)<=pos: continue
            name=link.get_text(' ',strip=True)
            value=cells[pos].get_text(strip=True).replace('%','').replace(',','')
            try: rate=float(value)/100
            except ValueError: continue
            dates=[c.get_text(' ',strip=True) for c in cells if c.get('id','').lower()=='date']
            rows.append({'Country':name,'Yield':rate,'Observation date':dates[0] if dates else 'Not published in table'})
    if not rows: raise ValueError('No verified 10-year yield table found. Enter yields manually from Trading Economics.')
    return pd.DataFrame(rows).drop_duplicates('Country'), {'source':BONDS,'as_of':'Per-row dates; missing dates explicitly marked','fetched_utc':stamp()}
