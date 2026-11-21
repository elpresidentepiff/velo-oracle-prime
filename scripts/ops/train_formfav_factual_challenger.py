#!/usr/bin/env python3
"""Fit an isolated FormFav factual challenger from verified pre-off snapshots.

Does NOT replace any deployed Velo model. Requires DATABASE_URL and sklearn.
Only runner-number AND normalized-name joined final, non-scratched labels qualify.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

SQL = """
WITH chosen AS (
 SELECT DISTINCT ON (provider_race_key,provider_runner_number)
 provider_race_key,provider_runner_number,provider_runner_name,captured_at,off_time_utc,
 source_payload,source_payload_sha256
 FROM formfav_factual_captures
 WHERE captured_at < off_time_utc - interval '10 minutes'
 AND source_payload_sha256 IS NOT NULL
 ORDER BY provider_race_key,provider_runner_number,captured_at DESC,id DESC
), joined AS (
 SELECT c.*,p.value AS result_item
 FROM chosen c
 JOIN formfav_results r ON r.provider_race_key=c.provider_race_key
 AND r.result_stage='final' AND r.interim=false
 CROSS JOIN LATERAL jsonb_array_elements(coalesce(r.results_payload->'placings','[]'::jsonb)) p(value)
 WHERE p.value->>'number'=c.provider_runner_number::text
 AND lower(regexp_replace(c.provider_runner_name,'[^a-zA-Z0-9]','','g'))
 =lower(regexp_replace(p.value->>'name','[^a-zA-Z0-9]','','g'))
 AND coalesce(p.value->>'scratched','false')='false'
)
SELECT provider_race_key,provider_runner_number,source_payload,
 (result_item->>'position')::integer=1 AS won
FROM joined
WHERE result_item->>'position' ~ '^[0-9]+$'
ORDER BY provider_race_key,provider_runner_number
"""

# Strict numeric source allowlist. No placings, finish, results, post-race odds,
# provider predictions or arbitrary JSON flattening.
FEATURES = ("barrier","weight","age","rating","officialRating","earlySpeedIndex")
def features(payload):
    runner = payload.get("runner") if isinstance(payload.get("runner"),dict) else payload
    values=[]
    for name in FEATURES:
        v=runner.get(name)
        try:
            values.append(float(v) if v is not None and not isinstance(v,bool) else float("nan"))
        except (ValueError,TypeError):
            values.append(float("nan"))
    return values

def main():
    import numpy as np
    import psycopg
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import log_loss, roc_auc_score
    import joblib
    url=os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL required; no training attempted")
    with psycopg.connect(url,connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL)
            rows=cur.fetchall()
    # Race-level chronological split, never runner-level random split.
    by_race={}
    for race,number,payload,won in rows:
        if not isinstance(payload,dict): continue
        by_race.setdefault(race,[]).append((number,features(payload),int(won)))
    # Keys encode YYYY-MM-DD for FormFav provider races; parse and reject unknown.
    dated=[]
    for race,entries in by_race.items():
        parts=race.split(":")
        if len(parts)<5 or len(parts[2])!=10: continue
        dated.append((parts[2],race,entries))
    dated.sort()
    if len(dated)<100: raise SystemExit("Insufficient verified race-level cohort")
    split=int(len(dated)*0.8)
    train,test=dated[:split],dated[split:]
    def unpack(items):
        x=[];y=[]
        for _,_,entries in items:
            for _,f,w in entries:
                x.append(f);y.append(w)
        return np.array(x,dtype=float),np.array(y,dtype=int)
    xtrain,ytrain=unpack(train)
    xtest,ytest=unpack(test)
    if len(set(ytrain))<2 or len(set(ytest))<2:
        raise SystemExit("Training or holdout has one class")
    model=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,l2_regularization=5,random_state=42)
    model.fit(xtrain,ytrain)
    probs=model.predict_proba(xtest)[:,1]
    report={"model":"FORMFAV_FACTUAL_CHALLENGER_V0","status":"SHADOW_OFFLINE_NOT_PROMOTED",
            "features":FEATURES,"train_races":len(train),"holdout_races":len(test),
            "train_runners":len(ytrain),"holdout_runners":len(ytest),
            "holdout_log_loss":float(log_loss(ytest,probs,labels=[0,1])),
            "holdout_roc_auc":float(roc_auc_score(ytest,probs)),
            "train_last_date":train[-1][0],"holdout_first_date":test[0][0],
            "staking_authorised":False,"production_promoted":False}
    out=Path("data/new_build/models/formfav_factual_challenger_v0")
    out.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,out/"model.joblib")
    (out/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
