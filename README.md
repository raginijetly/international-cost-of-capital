# International Cost of Capital

Compare one project's equity cost, borrowing cost and WACC in USD and another country's currency. Class formulas follow CasePacket2026-part9, slides 574 and 577–587.

## Run locally

Use Python 3.11 or 3.12. Put all project files in one folder, then run:

```sh
pip install -r requirements.txt
streamlit run app.py
```

## Upload and deploy

1. Sign in to GitHub and create a repository named `international-cost-of-capital`.
2. Upload **all** files in this folder, including `model.py` and `data_sources.py`. The app needs these helper files as well as `app.py` and `requirements.txt`.
3. In Streamlit Community Cloud, create an app, connect the repository, select branch `main` and main file `app.py`. Select Python 3.11 or 3.12 and deploy.
4. Open the deployed app and check source status. Enter any missing yields from Trading Economics using the manual controls.
5. Test the Colombia example below, then the three assignment checks.
6. Fill in the submission document with your real links and chat screenshots. Print the HTML document to PDF from your browser if needed.

## Data

- Industry beta: https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls — standard **Unlevered beta**, not the cash-corrected column. Tested: 94 industries, January 5, 2026 update.
- BBB spread: https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html — first Baa2/BBB entry, for large nonfinancial firms. Tested: 1.11%, January 2026.
- Corporate tax: OECD current combined statutory CIT feed, linked in the app. Uses `CIT_C`, statutory `ST`, general government `S13`, and latest nonmissing year per country. Tested: 146 country observations. Fetch time is distinct from the tax observation year.
- Yields: https://tradingeconomics.com/bonds — attempts to read the public 10-year table without an API key. **Live scraping was blocked or returned no table in this environment. Automatic yield retrieval is not verified and remains an assignment limitation.** The app requires manual yields if that happens; no market yields are fabricated. Public pages may block Streamlit servers too. Refresh retries all requests.

A failed source does not prevent using the others. Successful requests are cached for an hour. Refresh clears the cache. Manual input values persist while enabled; disabling an override restores the fetched value. A source without data requires manual input. All ISO countries are selectable, including countries absent from the feeds. The optional currency label is a display label only.

## Formulas (rates as decimals)

```
D/E = d / (1-d)
beta_E = beta_U * (1 + (1-tax)*D/E)
Re_USD = US_yield + beta_E*ERP
Rd_USD = US_yield + USD_spread
F = (1+foreign_yield)/(1+US_yield)
Re_local = (1+Re_USD)*F - 1
spread_local = USD_spread*F  # unless manually overridden
Rd_local = foreign_yield + spread_local
WACC = (1-d)*Re + d*Rd*(1-tax)  # separately in each currency
```

Debt share must be below 100% because D/E would otherwise divide by zero. Government yields are proxies, not pure risk-free rates. The conversion assumes equal real interest rates and relative purchasing power parity. No separate country equity premium is added. Debt beta is zero and tax deductions are immediately usable. ERP is a shared USD input; the foreign equity return is converted as a whole, not recalculated by adding the unchanged ERP to the foreign yield.

Do not convert WACC directly with F: first convert equity and debt costs, apply the tax shield, then calculate WACC.

## Verification and learning

Equity cost is the return shareholders require. Beta measures exposure to market movements. More debt raises the risk borne by the remaining shareholders. WACC averages equity cost and after-tax borrowing cost using the project's financing weights. Currency changes the nominal discount rate, so match cash flows and discount rates in the same currency.

Illustrative Colombia inputs from class, not current market data: beta 0.8, tax 35%, debt 30%, ERP 6.5%, US yield 4%, Colombia yield 12%, USD spread 1.5%.

| Result | USD | COP |
|---|---:|---:|
| Equity cost | 10.648571% | 19.160000% |
| Pretax debt cost | 5.500000% | 13.615385% |
| After-tax debt cost | 3.575000% | 8.850000% |
| WACC | 8.526500% | 16.067000% |

Automated tests compare these results with class values and check equal yields, zero debt, override isolation and invalid full-debt input:

```sh
python -m unittest discover -v
```

For your own independent check, use a separate calculator and follow `submission.html`. AI-written tests are useful but do not replace your independent verification. Repeat the test in the deployed app. Keep screenshots of the inputs and results.

## Downloads

Project JSON includes inputs, manual/fetched flags, effective foreign spread and source metadata. All-industry CSV uses each fetched industry beta with common project assumptions; the selected-project manual beta does not overwrite every industry's beta. Rates in JSON are decimals; CSV headings explicitly mark percentages.
