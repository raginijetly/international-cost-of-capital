import unittest
from model import calculate

class Verification(unittest.TestCase):
    args=dict(beta=.8,tax=.35,debt=.3,erp=.065,us_yield=.04,foreign_yield=.12,spread=.015)
    def test_class_example(self):
        r=calculate(**self.args)
        for cur,expected in [('USD',[.1064857142857143,.055,.03575,.085265]),('Local',[.1916,.13615384615384615,.0885,.16067])]:
            for k,v in zip(['Cost of equity','Pretax debt cost','After-tax debt cost','WACC'],expected):
                self.assertAlmostEqual(r[cur][k],v,places=10)
    def test_equal_yields(self):
        r=calculate(**{**self.args,'foreign_yield':.04})
        for k in r['USD']:self.assertAlmostEqual(r['USD'][k],r['Local'][k])
    def test_no_debt(self):
        r=calculate(**{**self.args,'debt':0})
        for c in ['USD','Local']:self.assertAlmostEqual(r[c]['WACC'],r[c]['Cost of equity'])
    def test_override_isolated(self):
        a=calculate(**self.args);b=calculate(**self.args,foreign_spread=.05)
        self.assertEqual(a['USD'],b['USD']);self.assertNotEqual(a['Local']['WACC'],b['Local']['WACC'])
    def test_full_debt_rejected(self):
        with self.assertRaises(ValueError):calculate(**{**self.args,'debt':1})
if __name__=='__main__':unittest.main()
