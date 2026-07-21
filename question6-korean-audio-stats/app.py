import base64,binascii,json,os,re,logging
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel




KEYS=("rows","columns","mean","std","variance","min","max","median","mode","range","allowed_values","value_range","correlation")
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
class Request(BaseModel):
 audio_id:str
 audio_base64:str




def empty():
 return {"rows":0,"columns":[],"mean":{},"std":{},"variance":{},"min":{},"max":{},"median":{},"mode":{},"range":{},"allowed_values":{},"value_range":{},"correlation":[]}
def clean(k):return re.sub(r"\s+","",str(k))
def rename(d):return {clean(k):v for k,v in d.items()} if isinstance(d,dict) else {}
def normalize(x):
 d=empty();r={k:x.get(k,d[k]) for k in KEYS};found=r["allowed_values"] if isinstance(r["allowed_values"],dict) else {}
 r["rows"]=int(r["rows"]) if isinstance(r["rows"],(int,float,str)) else 0
 r["correlation"]=r["correlation"] if isinstance(r["correlation"],list) else []
 for k in KEYS[2:-1]:r[k]=rename(r[k])
 cols=[clean(v) for v in r["columns"]] if isinstance(r["columns"],list) else []
 if not cols:
  for group in (found,r["mean"],r["std"],r["variance"],r["min"],r["max"],r["median"],r["mode"],r["range"],r["value_range"]):
   for key in group:
    if clean(key) not in cols:cols.append(clean(key))
 r["columns"]=cols;r["allowed_values"]={}
 return r
def decode(value):
 try:a=base64.b64decode(value.split(",",1)[-1].strip(),validate=True)
 except (binascii.Error,ValueError):raise HTTPException(422,"invalid audio_base64")
 if not a:raise HTTPException(422,"empty audio")
