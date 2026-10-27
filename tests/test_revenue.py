import copy
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from revenue import load_data,metrics,validate,channel_breakdown

class TestRevenue(unittest.TestCase):
    def setUp(self):
        self.data=load_data()

    def test_reject_nonfinite_financial_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            for field in ("value_usd", "recognized_revenue_usd"):
                data=copy.deepcopy(self.data)
                data["opportunities"][0][field]=value
                with self.assertRaises(ValueError):
                    validate(data)
            data=copy.deepcopy(self.data)
            channel=next(iter(data["channel_spend_usd"]))
            data["channel_spend_usd"][channel]=value
            with self.assertRaises(ValueError):
                validate(data)

    def test_fixtures_valid(self):
        self.assertTrue(validate(self.data))

    def test_sourced_pipeline_excludes_sales_and_unqualified(self):
        x=metrics(self.data)
        self.assertEqual(x["qualified_pipeline_created_usd"],680000)
        self.assertEqual(x["qualified_opportunities"],7)
        self.assertEqual(x["closed_won_bookings_usd"],200000)
        self.assertEqual(x["recognized_revenue_usd"],70000)
        self.assertEqual(x["marketing_spend_usd"],49000)

    def test_influence_includes_sales_origin_with_marketing_touch(self):
        x=metrics(self.data,attribution="influenced")
        self.assertEqual(x["qualified_pipeline_created_usd"],990000)
        self.assertEqual(x["qualified_opportunities"],9)
        self.assertNotIn("marketing_spend_usd",x)

    def test_organic_source_vs_influence(self):
        self.assertEqual(metrics(self.data,"Organic Search","sourced")["qualified_pipeline_created_usd"],230000)
        self.assertEqual(metrics(self.data,"Organic Search","influenced")["qualified_pipeline_created_usd"],380000)

    def test_paid_search_influenced(self):
        self.assertEqual(metrics(self.data,"Paid Search","influenced")["qualified_pipeline_created_usd"],220000)

    def test_cost_per_accepted_opportunity_not_cac(self):
        self.assertEqual(metrics(self.data,"Organic Search")["cost_per_accepted_opportunity_usd"],6000)
        self.assertIsNone(metrics(self.data,"Community")["cost_per_accepted_opportunity_usd"])

    def test_won_booking_different_from_recognized_revenue(self):
        x=metrics(self.data,"Organic Search")
        self.assertEqual(x["closed_won_bookings_usd"],110000)
        self.assertEqual(x["recognized_revenue_usd"],40000)

    def test_reject_malformed_touch_channels(self):
        for touches in ("Organic Search", [], ["Organic Search", None], ["Organic Search", ""], {"Organic Search": True}):
            with self.subTest(touches=touches):
                data=copy.deepcopy(self.data)
                data["opportunities"][0]["touch_channels"]=touches
                with self.assertRaises(ValueError):
                    validate(data)

    def test_reject_duplicate_opportunity(self):
        data=copy.deepcopy(self.data)
        data["opportunities"].append(data["opportunities"][0])
        with self.assertRaises(ValueError):validate(data)

    def test_reject_lead_source_mismatch(self):
        data=copy.deepcopy(self.data)
        data["opportunities"][0]["source_channel"]="Email"
        with self.assertRaises(ValueError):validate(data)

    def test_reject_unrecognized_revenue_on_open_deal(self):
        data=copy.deepcopy(self.data)
        data["opportunities"][0]["recognized_revenue_usd"]=100
        with self.assertRaises(ValueError):validate(data)

    def test_reject_invalid_attribution(self):
        with self.assertRaises(ValueError):metrics(self.data,attribution="last_touch")

    def test_distinct_ids_per_channel(self):
        for row in channel_breakdown(self.data).values():
            for result in row.values():
                self.assertEqual(len(set(result["opportunity_ids"])),len(result["opportunity_ids"]))

if __name__=="__main__":
    unittest.main()

