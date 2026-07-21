import re
from datetime import datetime
from typing import Any
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
app=FastAPI();app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"],allow_credentials=False)
T={"string","integer","float","boolean","date","array[string]","array[integer]"}
class R(BaseModel):
 text:str=Field(min_length=1,max_length=30000);schema_:dict[str,str]=Field(alias="schema",min_length=1,max_length=50)
 model_config={"populate_by_name":True}
def dt(v):
 if not v:return None
 v=re.sub(r"(\d)(st|nd|rd|th)\b",r"\1",str(v).strip(),flags=re.I)
 for f in ("%Y-%m-%d","%d %B %Y","%B %d, %Y","%d %b %Y","%b %d, %Y","%d/%m/%Y","%m/%d/%Y"):
  try:return datetime.strptime(v,f).date().isoformat()
  except:pass
 return None
def cast(v,k):
 if v is None or v=="":return None
 try:
  if k=="string":return str(v).strip().rstrip(".,;:") or None
  if k in {"integer","float"}:
   m=re.search(r"-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?",str(v));x=float(m.group(0).replace(",","")) if m else None;return int(x) if x is not None and k=="integer" else x
  if k=="boolean":
   x=str(v).lower().strip();return True if x in {"true","yes","y","1","paid","active"} else False if x in {"false","no","n","0","unpaid","inactive"} else None
  if k=="date":return dt(v)
  if k.startswith("array["):
   q="integer" if k=="array[integer]" else "string";return [z for z in (cast(i,q) for i in re.split(r"\s*,\s*",str(v))) if z is not None]
 except:return None
 return None
def val(t,k,typ):
 p=re.escape(k).replace("_",r"[ _-]?");m=re.search(rf"(?im)\b{p}\b\s*[:#-]\s*([^\n]+)",t)
 if m:return m.group(1).strip()
 a={"order_id":r"order\s*#?\s*([A-Za-z0-9/_-]+)","reference":r"(?:reference|ref|transaction|txn)\s*(?:no\.?)?\s*[:#-]?\s*([A-Za-z0-9/_-]+)","event_time":r"\bat\s+(\d{1,2}:\d{2})","root_cause":r"root\s*cause\s*:\s*([^\n.;]+)","city":r"shipped\s+to\s*:\s*([^\n.;]+)","store":r"from\s+([^\n.;]+)","customer_name":r"^\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:bought|purchased|ordered)","student":r"(?:student|name)\s*:\s*([^\n.;]+)","property_type":r"(?:property\s*type|property)\s*:\s*([^\n.;]+)","from_bank":r"(?:from\s*bank|from|debited\s*from|source\s*bank)\s*[:#-]?\s*([A-Za-z][A-Za-z .&-]*?)(?=\s+(?:acct|account|a/c)\b|[.,;\n]|$)","to_bank":r"(?:to\s*bank|to|credited\s*to|destination\s*bank)\s*[:#-]?\s*([A-Za-z][A-Za-z .&-]*?)(?=\s+(?:acct|account|a/c)\b|[.,;\n]|$)"}
 if k in a:
  m=re.search(a[k],t,re.I|re.M)
  if m:return m.group(1).strip()
 if typ=="date":
  m=re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}\b",t);return m.group(0) if m else None
 return None
@app.post("/dynamic-extract")
def extract(r:R)->dict[str,Any]:
 if set(r.schema_.values())-T:raise HTTPException(422,detail="Unsupported schema types")
 return {k:cast(val(r.text,k,t),t) for k,t in r.schema_.items()}
@app.get("/healthz")
def healthz():return {"status":"ok"}
