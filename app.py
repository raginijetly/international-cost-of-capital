import json
import pandas as pd
import pycountry
import streamlit as st
from model import calculate
import data_sources as ds

st.set_page_config(page_title='International Cost of Capital',page_icon='🌎',layout='wide')
st.title('International Cost of Capital')
st.write('Compare the same project in USD and the selected country’s currency.')
st.caption('Class formulas: CasePacket2026-part9, slides 574 and 577–587. Annual nominal rates; full precision calculations.')

@st.cache_data(ttl=3600,show_spinner=False)
def fetch(name, *args):
    return getattr(ds,name)(*args)

if st.button('Refresh source data',help='Clears cached source data and retries all four requests.'):
    fetch.clear()
    st.session_state.pop('sources',None)
if 'sources' not in st.session_state:
    loaded={}
    with st.spinner('Fetching the latest available source data…'):
        for name in ['beta_data','spread_data','tax_data']:
            try: loaded[name]={'data':fetch(name),'error':None}
            except Exception as exc: loaded[name]={'data':None,'error':str(exc),'attempted_utc':ds.stamp()}
    st.session_state.sources=loaded
sources=st.session_state.sources
for name,item in sources.items():
    if name != 'bond_data' and item['error']: st.warning(f"{name.replace('_data','').title()} fetch failed: {item['error']}. Use manual inputs below. Refresh to retry.")

def source(name):
    x=sources[name]['data'];return x[0] if x else None
betas=source('beta_data');taxes=source('tax_data');bonds=None
# All ISO countries remain selectable even when a source has no observation.
countries={c.name:c.alpha_3 for c in pycountry.countries}
alias={'United Kingdom':'GBR','South Korea':'KOR','Russia':'RUS','Taiwan':'TWN','Vietnam':'VNM','Turkey':'TUR','Türkiye':'TUR','United States':'USA'}
countries.update(alias)
with st.sidebar:
    st.header('Project choices')
    options=betas.Industry.tolist() if betas is not None else ['Software (System & Application)']
    default='Software (System & Application)'
    industry=st.selectbox('Industry',options,index=options.index(default) if default in options else 0)
    country=st.selectbox('Target country',sorted(countries),index=sorted(countries).index('United States'))
    currency=st.text_input('Currency label (optional)',value='',help='For example COP for Colombia. Country name labels results if blank.')
    erp=st.number_input('Equity risk premium (%)',0.0,100.0,6.5,0.1)/100
    debt=st.slider('Target debt share (%)',0,99,30)/100
    tax_choice=st.radio('Project tax rate', ['U.S.','Selected country'],horizontal=True)

# Fetch only the two countries needed, once the user has selected the target.
try:
    with st.spinner('Loading 10-year government yields…'):
        bond_result=fetch('bond_data',country)
    sources['bond_data']={'data':bond_result,'error':None}
    bonds=bond_result[0]
    for error in bond_result[1].get('fetch_errors',[]):
        st.warning('Government yield unavailable: '+error+'. Enter the missing yield manually.')
except Exception as exc:
    sources['bond_data']={'data':None,'error':str(exc),'attempted_utc':ds.stamp()}
    st.warning('Government yields could not be retrieved. Enter them manually from Trading Economics. '+str(exc))

def tax_for(code):
    if taxes is None:return None
    x=taxes[taxes.REF_AREA==code]
    return None if x.empty else float(x.iloc[0].OBS_VALUE)/100

def yield_for(code):
    if bonds is None:return None
    for _,r in bonds.iterrows():
        if countries.get(r.Country)==code:return float(r.Yield)
    return None

inputs=[]
def field(label,auto,key,percent=True,minval=0.0,maxval=100.0):
    missing=auto is None
    manual=st.toggle('Enter manually: '+label,value=missing,key='toggle_'+key,disabled=missing)
    scale=100 if percent else 1
    if manual:
        v=st.number_input(label+(' (%)' if percent else ''),min_value=minval,max_value=maxval,
                          value=None,placeholder='Enter value',key='value_'+key,step=0.1)
        value=None if v is None else v/scale
    else:
        value=auto;st.caption(f'{label}: {auto*scale:.4f}'+('%' if percent else ''))
    inputs.append({'Input':label,'Value (decimal rates)':value,'Mode':'Manual' if manual else 'Fetched'})
    return value

st.subheader('Inputs and overrides')
a,b=st.columns(2)
with a:
    beta_auto=None if betas is None else float(betas.loc[betas.Industry==industry,'Unlevered beta'].iloc[0])
    beta=field('Unlevered beta',beta_auto,'beta',False,0.0,20.0)
    us_tax=field('U.S. corporate tax rate',tax_for('USA'),'ustax')
    foreign_tax=field('Selected-country corporate tax rate',tax_for(countries[country]),'ftax_'+countries[country])
with b:
    usd_spread=field('USD BBB spread',source('spread_data'),'spread')
    us_yield=field('U.S. 10-year government yield',yield_for('USA'),'usy',minval=-99.0)
    fy=field('Selected-country 10-year government yield',yield_for(countries[country]),'fy_'+countries[country],minval=-99.0)
    override=st.toggle('Override foreign-currency BBB spread',value=False)
    fs=None
    if override:
        v=st.number_input('Foreign-currency BBB spread (%)',0.0,100.0,value=None,placeholder='Enter spread')
        fs=None if v is None else v/100
    elif None not in (usd_spread,us_yield,fy):
        st.info(f'Auto foreign spread: {usd_spread*(1+fy)/(1+us_yield):.4%}')

tax=us_tax if tax_choice=='U.S.' else foreign_tax
ready=None not in (beta,tax,usd_spread,us_yield,fy) and (not override or fs is not None)
if ready:
    r=calculate(beta,tax,debt,erp,us_yield,fy,usd_spread,fs)
    label=currency.strip() or country+' currency'
    st.subheader('Results')
    a,b=st.columns(2)
    for col,key,title in [(a,'USD','USD'),(b,'Local',label)]:
        with col:
            st.markdown('### '+title)
            st.metric('WACC',f"{r[key]['WACC']:.4%}")
            for k,v in r[key].items():
                if k!='WACC':st.write(f'{k}: **{v:.4%}**')
    st.caption(f'Project tax: {tax:.4%}; debt share: {debt:.1%}; ERP: {erp:.1%}; relevered beta: {r["levered_beta"]:.6f}; currency factor: {r["factor"]:.6f}.')
    payload={'industry':industry,'country':country,'local_currency_label':label,'inputs':inputs,
             'project_tax':tax,'debt_share':debt,'ERP':erp,'foreign_spread_override':fs,
             'results':r,'sources':{k:{x:y for x,y in v.items() if x!='data'} | ({'metadata':v['data'][1]} if v['data'] else {}) for k,v in sources.items()}}
    st.download_button('Download results and sources (JSON)',json.dumps(payload,indent=2).encode(),'project-results.json','application/json')
    st.subheader('All-industry comparison')
    st.caption('Uses each industry’s fetched beta and the same project assumptions. The selected-project beta override does not replace other industries’ betas.')
    if betas is not None:
        rows=[]
        for _,row in betas.iterrows():
            q=calculate(float(row['Unlevered beta']),tax,debt,erp,us_yield,fy,usd_spread,fs)
            rows.append({'Industry':row.Industry,'Unlevered beta':row['Unlevered beta'],**{f'{cur} {k} (%)':v*100 for cur in ['USD','Local'] for k,v in q[cur].items()}})
        table=pd.DataFrame(rows);st.dataframe(table,hide_index=True)
        st.download_button('Download all industries (CSV)',table.to_csv(index=False).encode(),'all-industries.csv','text/csv')
    else:st.info('Refresh beta data to enable the all-industry comparison.')
else:
    st.info('Enter the missing inputs to calculate. Source failures never become assumed market rates.')

with st.expander('Learn: formulas and assumptions',expanded=True):
    st.markdown('''**1. Adjust business risk for debt.** Unlevered beta measures the business’s market risk before debt. Borrowing concentrates risk on shareholders.

`D/E = d / (1 − d)`  
`Equity beta = Unlevered beta × [1 + (1 − tax) × D/E]`

**2. Calculate USD equity and borrowing costs.** ERP is the extra return investors demand for market risk.

`Equity_USD = US yield + Equity beta × ERP`  
`Debt_USD = US yield + USD BBB spread`

**3. Convert to the other currency.** The class uses government yields as risk-free proxies and the same USD ERP input.

`F = (1 + foreign yield) / (1 + US yield)`  
`Equity_local = (1 + Equity_USD) × F − 1`  
`Auto spread_local = USD spread × F`  
`Debt_local = foreign yield + spread_local`

**4. Combine financing costs in each currency.** The tax deduction lowers borrowing cost.

`WACC = (1 − d) × Equity cost + d × Debt cost × (1 − tax)`

Both scenarios share one project tax rate and debt share. Government yields can contain sovereign risk. The class conversion assumes equal real rates and relative purchasing power parity. No separate country equity premium is added. Debt beta is zero and interest deductions are fully usable. WACC is recomputed after conversion; converting USD WACC directly would give a different answer when taxes matter. Use discount rates with cash flows in the same currency.''')
with st.expander('Sources, observation dates and fetch status'):
    for name,item in sources.items():
        st.write(name)
        if item['data']:st.json(item['data'][1])
        else:st.json(item)
    if taxes is not None:st.dataframe(taxes,hide_index=True)
    if bonds is not None:st.dataframe(bonds,hide_index=True)
    st.caption('Fetched time is when the request succeeded, not the observation date. Cache lasts one hour; Refresh retries all sources. OECD uses combined central and subcentral statutory rates, latest nonmissing year for each country. Countries without published observations need manual entries.')
