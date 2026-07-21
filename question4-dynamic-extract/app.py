import re
from datetime import datetime
from typing import Any
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"],allow_credentials=False)
T={"string","integer","float","boolean","date","array[string]","array[integer]"}
class R(BaseModel):
 text:str=Field(min_length=1,max_length=30000)
 schema_:dict[str,str]=Field(alias="schema",min_length=1,max_length=50)
 model_config={"populate_by_name":True}
def date(v):
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
  if k=="integer":
   x=re.search(r"-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?",str(v));return int(float(x.group(0).replace(",",""))) if x else None
  if k=="float":
   x=re.search(r"-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?",str(v));return float(x.group(0).replace(",","")) if x else None
  if k=="boolean":
   z=str(v).lower().strip();return True if z in {"true","yes","y","1","paid","active"} else False if z in {"false","no","n","0","unpaid","inactive"} else None
  if k=="date":return date(v)
  if k.startswith("array["):
   inner="integer" if k=="array[integer]" else "string";xs=v if isinstance(v,list) else re.split(r"\s*,\s*",str(v));return [x for x in (cast(i,inner) for i in xs) if x is not None]
 except:return None
 return None
def value(text,key,kind):
 lab=re.escape(key).replace("_",r"[ _-]?")
 m=re.search(rf"(?im)\b{lab}\b\s*[:#-]\s*([^\n]+)",text)
 if m:return m.group(1).strip()
 a={"order_id":r"order\s*#?\s*([A-Za-z0-9/_-]+)","reference":r"(?:reference|ref|transaction|txn)\s*(?:no\.?)?\s*[:#-]?\s*([A-Za-z0-9/_-]+)","event_time":r"\bat\s+(\d{1,2}:\d{2})", "root_cause":r"root\s*cause\s*:\s*([^\n.;]+)","city":r"shipped\s+to\s*:\s*([^\n.;]+)","store":r"from\s+([^\n.;]+)","customer_name":r"^\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:bought|purchased|ordered)","student":r"(?:student|name)\s*:\s*([^\n.;]+)","property_type":r"(?:property\s*type|property)\s*:\s*([^\n.;]+)"}
 if key in a:
  m=re.search(a[key],text,re.I|re.M)
  if m:return m.group(1).strip()
 if kind=="date":
  m=re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}\b",text)
  return m.group(0) if m else None
 return None
@app.post("/dynamic-extract")
def extract(r:R)->dict[str,Any]:
 bad=set(r.schema_.values())-T
 if bad:raise HTTPException(422,detail="Unsupported schema types")
 return {key:cast(value(r.text,key,kind),kind) for key,kind in r.schema_.items()}
@app.get("/healthz")
def healthz():return {"status":"ok"}
