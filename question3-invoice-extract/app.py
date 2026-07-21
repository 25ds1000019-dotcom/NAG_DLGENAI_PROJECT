import re
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"],allow_credentials=False)
class R(BaseModel):invoice_text:str=Field(min_length=1,max_length=30000)
class O(BaseModel):
 invoice_no:str|None=None;date:str|None=None;vendor:str|None=None;amount:float|None=None;tax:float|None=None;currency:str|None=None
def g(p,t):
 m=re.search(p,t,re.I|re.M);return m.group(1).strip() if m else None
def n(v):
 x=re.findall(r"(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?",v or "");return float(x[-1].replace(",","")) if x else None
def d(v):
 if not v:return None
 v=re.sub(r"(\d)(st|nd|rd|th)\b",r"\1",v.strip(),flags=re.I)
 for f in ("%Y-%m-%d","%d %B %Y","%B %d, %Y","%d %b %Y","%b %d, %Y","%d/%m/%Y","%m/%d/%Y"):
  try:return datetime.strptime(v,f).date().isoformat()
  except:pass
 return None
def c(t,v):
 z=(v or "").strip().upper();a={"RS":"INR","RUPEES":"INR","DOLLARS":"USD","EUROS":"EUR","POUNDS":"GBP"}
 if z in {"INR","USD","EUR","GBP","JPY"}:return z
 if z in a:return a[z]
 u=t.upper()
 if re.search(r"₹|\bINR\b|\bRS\.?",u):return "INR"
 if re.search(r"\$|\bUSD\b",u):return "USD"
 if re.search(r"€|\bEUR\b",u):return "EUR"
 if re.search(r"£|\bGBP\b",u):return "GBP"
 if re.search(r"¥|\bJPY\b",u):return "JPY"
 return None
@app.post("/extract",response_model=O)
def extract(r:R):
 t=r.invoice_text
 inv=g(r"^\s*(?:invoice\s*(?:no\.?|number|#)?|inv\.?|ref(?:erence)?|bill\s*(?:no\.?|#)?)\s*[:#\-.]*\s*(.+?)\s*$",t)
 if inv:inv=re.sub(r"^(?:invoice|inv|reference|ref|bill)\s*(?:no\.?|number)?\s*[#:.\-]?\s*","",inv,flags=re.I).strip().strip(". ") or None
 dt=g(r"^\s*(?:date|issued|issue\s*date|invoice\s*date)\s*[:#\-.]*\s*(.+?)\s*$",t)
 ven=g(r"^\s*(?:vendor|seller|supplier|billed\s*by|from)\s*[:#\-.]*\s*(.+?)\s*$",t)
 amt=g(r"^\s*(?:subtotal|sub\s*total|net\s*amount|amount\s*before\s*tax|pre[- ]?tax\s*total|taxable\s*(?:amount|value)|base\s*amount|amount\s*(?:excluding|excl\.?|without)\s*tax|goods\s*value|amount)\s*[:#\-.]*\s*(.+?)\s*$",t)
 tax=g(r"^\s*(?:(?:gst|igst|cgst|sgst|vat|sales\s*tax|tax)(?:\s*\([^\n)]*\))?)\s*[:#\-.]*\s*(.+?)\s*$",t)
 cur=g(r"^\s*currency\s*[:#\-.]*\s*(.+?)\s*$",t)
 return O(invoice_no=inv,date=d(dt),vendor=ven.strip().strip(". ") if ven else None,amount=n(amt),tax=n(tax),currency=c(t,cur))
@app.get("/healthz")
def healthz():return {"status":"ok"}
