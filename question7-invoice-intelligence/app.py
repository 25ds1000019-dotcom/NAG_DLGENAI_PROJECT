import json,os,re
from datetime import datetime
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel,Field
app=FastAPI();app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
K=("vendor","currency","total_amount","invoice_date","due_in_days","is_paid","priority","contact_email","line_items","item_count")
class R(BaseModel):
 document_id:str;text:str=Field(min_length=1);schema_:dict=Field(alias="schema")
 model_config={"populate_by_name":True}
def num(v):
 if v is None:return None
 s=str(v).lower().replace(',','');m=re.search(r'(\d+(?:\.\d+)?)\s*([km])?',s)
 return int(round(float(m.group(1))*{'k':1000,'m':1000000}.get(m.group(2),1))) if m else None
def date(v):
 if not v:return None
 s=str(v).strip()
 for f in ('%Y-%m-%d','%d %B %Y','%B %d, %Y','%d/%m/%Y','%m/%d/%Y'):
  try:return datetime.strptime(s,f).date().isoformat()
  except:pass
 return s if re.fullmatch(r'\d{4}-\d\d-\d\d',s) else None
def norm(x):
 items=[]
 for z in x.get('line_items',[]) if isinstance(x.get('line_items'),list) else []:
  if isinstance(z,dict):items.append({'sku':str(z.get('sku')).strip() if z.get('sku') is not None else None,'quantity':num(z.get('quantity')),'unit_price':num(z.get('unit_price'))})
 cur=str(x.get('currency','')).upper();cm={'$':'USD','€':'EUR','£':'GBP','₹':'INR','RS':'INR','¥':'JPY'};c=next((v for k,v in cm.items() if k in cur),cur if cur in ('USD','EUR','GBP','INR','JPY') else None)
 return {'vendor':str(x['vendor']).strip().rstrip('.,;:') if x.get('vendor') is not None else None,'currency':c,'total_amount':num(x.get('total_amount')),'invoice_date':date(x.get('invoice_date')),'due_in_days':num(x.get('due_in_days')),'is_paid':x.get('is_paid') if isinstance(x.get('is_paid'),bool) else None,'priority':str(x.get('priority')).lower() if str(x.get('priority')).lower() in ('low','normal','high','urgent') else None,'contact_email':str(x.get('contact_email')).lower() if x.get('contact_email') else None,'line_items':items,'item_count':len(items)}
async def go(r):
 key=os.getenv('GEMINI_API_KEY')
 if not key:raise HTTPException(503,'GEMINI_API_KEY missing')
 p='Return JSON only matching this invoice schema exactly. Normalize dates YYYY-MM-DD, all amounts to integer main units, lower-case email, preserve line item order. Infer payment and priority. Schema='+json.dumps(r.schema_)+'\nInvoice:\n'+r.text
 try:return norm(json.loads(genai.Client(api_key=key).models.generate_content(model='gemini-3.1-flash-lite',contents=p,config=types.GenerateContentConfig(response_mime_type='application/json')).text or '{}'))
 except Exception as e:raise HTTPException(502,'extraction failed')
@app.post('/')
async def root(r:R):return await go(r)
@app.post('/extract')
async def extract(r:R):return await go(r)
