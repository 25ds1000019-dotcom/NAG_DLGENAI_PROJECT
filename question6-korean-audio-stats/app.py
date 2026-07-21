import base64,binascii,json,os,re
from typing import Any
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel,Field
K=("rows","columns","mean","std","variance","min","max","median","mode","range","allowed_values","value_range","correlation")
app=FastAPI();app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"],allow_credentials=False)
class R(BaseModel):audio_id:str=Field(min_length=1,max_length=200);audio_base64:str=Field(min_length=1)
def empty():return {"rows":0,"columns":[],"mean":{},"std":{},"variance":{},"min":{},"max":{},"median":{},"mode":{},"range":{},"allowed_values":{},"value_range":{},"correlation":[]}
def decode(v):
 try:a=base64.b64decode(v.split(",",1)[-1].strip(),validate=True)
 except (binascii.Error,ValueError):raise HTTPException(422,detail="audio_base64 must be valid base64")
 if not a or len(a)>25*1024*1024:raise HTTPException(422,detail="invalid audio size")
 if a.startswith(b"RIFF") and a[8:12]==b"WAVE":return a,"audio/wav"
 if a.startswith(b"OggS"):return a,"audio/ogg"
 if a.startswith(b"fLaC"):return a,"audio/flac"
 if a.startswith(b"ID3") or a[:2]==b"\xff\xfb":return a,"audio/mpeg"
 if a.startswith(b"\x1aE\xdf\xa3"):return a,"audio/webm"
 return a,"audio/wadef clean(k):return re.sub(r"\s+","",str(k))
def rename(d):return {clean(k):v for k,v in d.items()} if isinstance(d,dict) else {}
def norm(x):
 d=empty();r={k:x.get(k,d[k]) for k in K};found=r["allowed_values"] if isinstance(r["allowed_values"],dict) else {};r["rows"]=int(r["rows"]) if isinstance(r["rows"],(int,float,str)) else 0;r["correlation"]=r["correlation"] if isinstance(r["correlation"],list) else []
 for k in K[2:-1]:r[k]=rename(r[k])
 cols=[clean(v) for v in r["columns"]] if isinstance(r["columns"],list) else []
 if not cols:
  for group in (found,r["mean"],r["std"],r["variance"],r["min"],r["max"],r["median"],r["mode"],r["range"],r["value_range"]):
   for key in group:
    if clean(key) not in cols:cols.append(clean(key))
 r["columns"]=cols;r["allowed_values"]={}
 return r

async def run(r):
 key=os.getenv("GEMINI_API_KEY")
 if not key:raise HTTPException(503,detail="GEMINI_API_KEY is not configured")
 audio,mime=decode(r.audio_base64)
 prompt="""The audio is Korean speech describing a numeric table. Transcribe every row and compute exact statistics. Return JSON only with exactly: rows, columns, mean, std, variance, min, max, median, mode, range, allowed_values, value_range, correlation. Spoken score fields such as 점수 1 and 점수 2 are numeric column names: use exactly 점수1 and 점수2, and use those names in every statistic mapping. allowed_values must be {}. Use pandas sample std/variance (ddof=1), range=max-min, JSON numeric values, no commentary."""
 try:
  c=genai.Client(api_key=key);out=c.models.generate_content(model="gemini-3.1-flash-lite",contents=[types.Part.from_bytes(data=audio,mime_type=mime),prompt],config=types.GenerateContentConfig(response_mime_type="application/json"));return norm(json.loads(out.text or "{}"))
 except Exception as e:raise HTTPException(502,detail="Audio analysis failed") from e
@app.post("/")
async def root(r:R):return await run(r)
