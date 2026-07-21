import math,os
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel,Field
app=FastAPI();app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
class R(BaseModel):
 query_id:str;query:str=Field(min_length=1);candidates:list[str]=Field(min_length=3)
def cos(a,b):
 d=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/d if d else 0
async def go(r):
 key=os.getenv('OPENAI_API_KEY')
 if not key:raise HTTPException(503,'OPENAI_API_KEY missing')
 try:
  e=OpenAI(api_key=key).embeddings.create(model='text-embedding-3-small',input=[r.query,*r.candidates]).data
  s=[cos(e[0].embedding,x.embedding) for x in e[1:]]
  return {'ranking':sorted(range(len(s)),key=lambda i:(-s[i],i))[:3]}
 except Exception as x:raise HTTPException(502,'OpenAI embedding failed')
@app.post('/')
async def root(r:R):return await go(r)
@app.post('/search')
async def search(r:R):return await go(r)
