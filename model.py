"""Class packet slides 574 and 577–585. All rates are decimals."""
import math

def calculate(beta, tax, debt, erp, us_yield, foreign_yield, spread, foreign_spread=None):
    vals = (beta, tax, debt, erp, us_yield, foreign_yield, spread)
    if not all(math.isfinite(v) for v in vals):
        raise ValueError('Inputs must be finite numbers.')
    if not (0 <= tax <= 1 and 0 <= debt < 1 and beta >= 0 and erp >= 0 and spread >= 0):
        raise ValueError('Check tax, debt share, beta, ERP and spread ranges.')
    if min(us_yield, foreign_yield) <= -1:
        raise ValueError('Government yields must exceed -100%.')
    if foreign_spread is not None and (not math.isfinite(foreign_spread) or foreign_spread < 0):
        raise ValueError('Foreign spread must be finite and nonnegative.')
    levered = beta * (1 + (1-tax)*debt/(1-debt))
    factor = (1+foreign_yield)/(1+us_yield)
    local_spread = spread*factor if foreign_spread is None else foreign_spread
    equity_us = us_yield + levered*erp
    equity_local = (1+equity_us)*factor-1
    def result(equity, borrowing, credit):
        after = borrowing*(1-tax)
        return {'Cost of equity':equity, 'Pretax debt cost':borrowing,
                'After-tax debt cost':after, 'WACC':(1-debt)*equity+debt*after,
                'BBB spread':credit}
    return {'levered_beta':levered, 'factor':factor,
            'USD':result(equity_us,us_yield+spread,spread),
            'Local':result(equity_local,foreign_yield+local_spread,local_spread)}
