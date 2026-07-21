import json,os,re,urllib.request
from datetime import datetime
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
app=FastAPI();app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
class R(BaseModel):
 document_id:str;text:str=Field(min_length=1);schema_:dict=Field(alias="schema")
 model_config={"populate_by_name":True}
def n(v):
 m=re.search(r'\d+(?:\.\d+)?',str(v).replace(',','')) if v is not None else None
 return int(float(m.group())) if m else None
def norm(x):
 it=[]
 for z in x.get('line_items',[]) if isinstance(x.get('line_items'),list) else []:
  if isinstance(z,dict):it.append({'sku':str(z.get('sku')).strip() if z.get('sku') is not None else None,'quantity':n(z.get('quantity')),'unit_price':n(z.get('unit_price'))})
 cur=str(x.get('currency','')).upper();c=next((v for k,v in {'$':'USD','€':'EUR','£':'GBP','₹':'INR','¥':'JPY','RS':'INR'}.items() if k in cur),cur if cur in ('USD','EUR','GBP','INR','JPY') else None)
 d=x.get('invoice_date');ds=str(d).strip() if d else None
 for f in ('%d %B %Y','%B %d, %Y','%d/%m/%Y','%m/%d/%Y'):
  try:ds=datetime.strptime(ds,f).date().isoformat();break
  except:pass
 return {'vendor':str(x.get('vendor')).strip().rstrip('.,;:') if x.get('vendor') is not None else None,'currency':c,'total_amount':n(x.get('total_amount')),'invoice_date':ds,'due_in_days':n(x.get('due_in_days')),'is_paid':x.get('is_paid') if isinstance(x.get('is_paid'),bool) else None,'priority':str(x.get('priority')).lower() if str(x.get('priority')).lower() in ('low','normal','high','urgent') else None,'contact_email':str(x.get('contact_email')).lower() if x.get('contact_email') else None,'line_items':it,'item_count':len(it)}
async def go(r):
 key=os.getenv('GROQ_API_KEY')
 if not key:raise HTTPException(503,'GROQ_API_KEY missing')
 p='Return JSON only matching this schema exactly. Normalize date YYYY-MM-DD, amounts/invoice quantities/prices to integers, lower-case email, preserve item order. '+json.dumps(r.schema_)+' Invoice: '+r.text
 body=json.dumps({'model':'llama-3.3-70b-versatile','messages':[{'role':'system','content':'You are a precise invoice extractor. Return JSON only.'},{'role':'user','content':p}],'response_format':{'type':'json_object'},'temperature':0}).encode()
 try:
  q=urllib.request.Request('https://api.groq.com/openai/v1/chat/completions',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  data=json.loads(urllib.request.urlopen(q,timeout=10).read());return norm(json.loads(data['choices'][0]['message']['content']))
 except Exception as e:raise HTTPException(502,'Groq extraction failed')
@app.post('/')
async def root(r:R):return await go(r)
@app.post('/extract')
async def ext(r:R):return await go(r)
