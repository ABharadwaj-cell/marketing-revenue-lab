"""Read-only, deterministic marketing-to-revenue metrics on SYNTHETIC CRM records.

No attribution model can prove incremental causal lift from marketing touchpoints.
"""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT / "docs" / "data.json"
STAGES={"open","closed_won","closed_lost","unqualified"}

def load_data(path=FIXTURE):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    validate(data)
    return data

def validate(data):
    required={"leads","opportunities","marketing_channels","channel_spend_usd"}
    if not required.issubset(data): raise ValueError("Dataset missing keys: "+str(sorted(required-set(data))))
    leads={}; opportunities=set()
    for lead in data["leads"]:
        if lead.get("id") in leads: raise ValueError("Duplicate lead")
        if not lead.get("id") or not lead.get("source_channel"):raise ValueError("Incomplete lead")
        leads[lead["id"]]=lead
    channels=set(data["marketing_channels"])
    for channel,amount in data["channel_spend_usd"].items():
        if channel not in channels or not isinstance(amount,(int,float)) or isinstance(amount,bool) or not math.isfinite(amount) or amount<0:
            raise ValueError("Invalid spend entry")
    for opp in data["opportunities"]:
        for key in ("id","lead_id","source_channel","touch_channels","sales_accepted","stage","value_usd","recognized_revenue_usd","created_at"):
            if key not in opp:raise ValueError("Missing opportunity key "+key)
        if not opp["id"] or opp["id"] in opportunities:raise ValueError("Duplicate or missing opportunity id")
        opportunities.add(opp["id"])
        if opp["lead_id"] not in leads:raise ValueError("Opportunity lead not present")
        if opp["source_channel"]!=leads[opp["lead_id"]]["source_channel"]:raise ValueError("Lead and opportunity source mismatch")
        touches=opp["touch_channels"]
        if not isinstance(touches,list) or not touches or any(not isinstance(t,str) or not t.strip() for t in touches):
            raise ValueError("Touch channels must be a non-empty list of channel names")
        if opp["source_channel"] not in opp["touch_channels"]:raise ValueError("Acquisition source must be in recorded touches")
        if len(set(opp["touch_channels"]))!=len(opp["touch_channels"]):raise ValueError("Duplicate touch")
        if opp["stage"] not in STAGES:raise ValueError("Unknown stage")
        if type(opp["sales_accepted"]) is not bool:raise ValueError("Acceptance must be bool")
        if (opp["stage"]=="unqualified") == opp["sales_accepted"]:raise ValueError("Unqualified stage must not be sales accepted")
        for f in ("value_usd","recognized_revenue_usd"):
            if not isinstance(opp[f],(int,float)) or isinstance(opp[f],bool) or not math.isfinite(opp[f]) or opp[f]<0:raise ValueError("Invalid financial amount")
        if opp["stage"]!="closed_won" and opp["recognized_revenue_usd"]!=0:
            raise ValueError("Non-won opportunity records recognized revenue")
    return True

def metrics(data,channel=None,attribution="sourced"):
    validate(data)
    if attribution not in ("sourced","influenced"):raise ValueError("Unknown attribution view")
    permitted=set(data["marketing_channels"])
    if channel is not None and channel not in permitted:raise ValueError("Unknown marketing channel")
    accepted=[o for o in data["opportunities"] if o["sales_accepted"]]
    if attribution=="sourced":
        selected=[o for o in accepted if o["source_channel"] in permitted and
                  (channel is None or o["source_channel"]==channel)]
    else:
        selected=[o for o in accepted if (channel in o["touch_channels"] if channel else
                   bool(set(o["touch_channels"]) & permitted))]
    won=[o for o in selected if o["stage"]=="closed_won"]
    lost=[o for o in selected if o["stage"]=="closed_lost"]
    open_opps=[o for o in selected if o["stage"]=="open"]
    src_leads=[l for l in data["leads"] if l["source_channel"] in permitted and
            (channel is None or l["source_channel"]==channel)]
    spend=sum(data["channel_spend_usd"].values()) if channel is None else data["channel_spend_usd"].get(channel,0)
    count=len(selected)
    result={
      "attribution":attribution,"channel":channel or "All marketing channels",
      "qualified_opportunities":count,
      "qualified_pipeline_created_usd":sum(o["value_usd"] for o in selected),
      "open_pipeline_usd":sum(o["value_usd"] for o in open_opps),
      "closed_won_bookings_usd":sum(o["value_usd"] for o in won),
      "recognized_revenue_usd":sum(o["recognized_revenue_usd"] for o in won),
      "won":len(won),"lost":len(lost),"open":len(open_opps),
      "win_rate_closed_only":round(len(won)/(len(won)+len(lost)),4) if won or lost else None,
      "opportunity_ids":[o["id"] for o in selected]
    }
    if attribution=="sourced":
        result.update({
          "sourced_leads":len(src_leads),
          "marketing_spend_usd":spend,
          "cost_per_accepted_opportunity_usd":round(spend/count,2) if count else None,
          "lead_to_accepted_opportunity_rate":round(count/len(src_leads),4) if src_leads else None
        })
    else:
        result["note"]="Influence is non-exclusive. Do not sum influenced amounts across channels or add to sourced."
    return result

def channel_breakdown(data):
    return {c:{"sourced":metrics(data,c,"sourced"),"influenced":metrics(data,c,"influenced")}
            for c in data["marketing_channels"]}

if __name__=="__main__":
    data=load_data()
    print(json.dumps({"dataset":data["dataset_name"],
      "marketing_sourced":metrics(data,attribution="sourced"),
      "marketing_influenced":metrics(data,attribution="influenced"),
      "by_channel":channel_breakdown(data)},indent=2))

