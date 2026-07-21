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
 if a.startswith(b"RIFF"):return a,"audio/wav"
 if a.startswith(b"OggS"):return a,"audio/ogg"
 if a.startswith(b"fLaC"):return a,"audio/flac"
 if a.startswith(b"ID3") or a[:2]==b"\xff\xfb":return a,"audio/mpeg"
 if a.startswith(b"\x1aE\xdf\xa3"):return a,"audio/webm"
 if a[4:8]==b"ftyp":return a,"audio/mp4"
 return a,"audio/wav"
async def answer(req):
 key=os.getenv("GEMINI_API_KEY")
 if not key:raise HTTPException(503,"GEMINI_API_KEY missing")
 audio,mime=decode(req.audio_base64)
 prompt='''Korean audio describes a numeric table. Transcribe every row and calculate exact statistics. JSON only with keys rows, columns, mean, std, variance, min, max, median, mode, range, allowed_values, value_range, correlation. Score columns spoken as 점수 1 and 점수 2 must be named 점수1 and 점수2. They are numeric, never categories; allowed_values is {}. Use pandas sample std and variance (ddof=1), and range=max-min.'''
 try:
  out=genai.Client(api_key=key).models.generate_content(model="gemini-3.1-flash-lite",contents=[types.Part.from_bytes(data=audio,mime_type=mime),prompt],config=types.GenerateContentConfig(response_mime_type="application/json",max_output_tokens=1024))
  return normalize(json.loads(out.text or "{}"))
 except Exception as e:
  logging.exception("Gemini audio request failed")
  raise HTTPException(502,"audio analysis failed")
@app.post("/")
async def root(req:Request):return await answer(req)
@app.post("/analyze-audio")
async def analyze(req:Request):return await answer(req)
@app.get("/healthz")
def health():return {"status":"ok"}
