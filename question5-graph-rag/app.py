"""Deterministic GraphRAG extraction, traversal, and community summaries."""
from __future__ import annotations
import re
from collections import deque
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="GraphMind GraphRAG")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["POST", "OPTIONS"], allow_headers=["*"])

CAP = r"([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)"
VERBS = {"CREATED": "created", "FOUNDED": "founded", "DEVELOPED": "developed", "INTEGRATED_INTO": "integrates with", "HIRED": "hired", "AUTHORED": "authored"}

class ExtractRequest(BaseModel):
    chunk_id: str = ""
    text: str = Field(default="", max_length=20000)
class GraphRequest(BaseModel):
    question: str = ""
    graph: dict[str, Any] = Field(default_factory=dict)
class CommunityRequest(BaseModel):
    community_id: str = ""
    entities: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)

def entity_type(name: str, text: str) -> str:
    low, around = name.lower(), text.lower()
    if low in {"langchain", "llamaindex", "haystack", "react", "django", "pytorch", "tensorflow"} or re.search(re.escape(name.lower()) + r"\s+(?:is|was)\s+(?:an?\s+)?framework", around): return "Framework"
    if low in {"openai", "google", "microsoft", "meta", "anthropic", "apple", "amazon"} or any(x in name for x in ("Inc", "Corp", "Labs", "AI")): return "Organization"
    if re.search(r"(?:by|founded by|created by|developed by|hired)\s+" + re.escape(name), text, re.I): return "Person"
    if " " in name and not any(x in name for x in ("OpenAI", "Google", "Microsoft")): return "Person"
    return "Product"

def add_rel(found: list[dict[str,str]], source: str, target: str, relation: str) -> None:
    item={"source":source.strip(),"target":target.strip(),"relation":relation}
    if item not in found: found.append(item)

@app.post('/extract-graph')
def extract_graph(req: ExtractRequest) -> dict[str, list[dict[str,str]]]:
    text=req.text
    rels=[]
    # Subject first: LangChain was created by Harrison Chase.
    for m in re.finditer(CAP + r"\s+(?:was|is)\s+(?:created|founded|developed|authored)\s+by\s+" + CAP, text, re.I):
        subject, verb, obj=m.group(1), m.group(0).lower(), m.group(2)
        relation="FOUNDED" if "founded" in verb else "DEVELOPED" if "developed" in verb else "AUTHORED" if "authored" in verb else "CREATED"
        add_rel(rels,obj,subject,relation)
    for m in re.finditer(CAP + r"\s+(?:created|founded|developed|authored)\s+" + CAP, text, re.I):
        source, verb, target=m.group(1),m.group(0).lower(),m.group(2)
        add_rel(rels,source,target,"FOUNDED" if "founded" in verb else "DEVELOPED" if "developed" in verb else "AUTHORED" if "authored" in verb else "CREATED")
    for m in re.finditer(CAP + r"\s+(?:integrates?\s+with|was\s+integrated\s+into|integrated\s+into)\s+" + CAP, text, re.I): add_rel(rels,m.group(1),m.group(2),"INTEGRATED_INTO")
    for m in re.finditer(CAP + r"\s+hired\s+" + CAP, text, re.I): add_rel(rels,m.group(1),m.group(2),"HIRED")
    names=[]
    for rel in rels:
        for name in (rel['source'],rel['target']):
            if name not in names: names.append(name)
    for name in re.findall(CAP, text):
        if name not in names and name.lower() not in {'the','this','a','an'}: names.append(name)
    return {"entities":[{"name":n,"type":entity_type(n,text)} for n in names],"relationships":rels}

def graph_parts(graph: dict[str,Any]):
    ents=graph.get('entities',[]) if isinstance(graph,dict) else []
    names=[]; types={}
    for e in ents:
        if isinstance(e,dict) and e.get('name'):
            names.append(str(e['name'])); types[str(e['name'])]=str(e.get('type',''))
        elif isinstance(e,str): names.append(e)
    rels=[r for r in graph.get('relationships',[]) if isinstance(r,dict) and r.get('source') and r.get('target')]
    return names,types,rels

@app.post('/graph-query')
def graph_query(req: GraphRequest) -> dict[str,Any]:
    names,types,rels=graph_parts(req.graph); q=req.question.lower()
    anchors=sorted([n for n in names if n.lower() in q], key=lambda n:(-len(n),n))
    if not anchors: return {"answer":"I don't know","reasoning_path":[],"hops":0}
    start=anchors[0]; adj={n:[] for n in names}
    for r in rels:
        a,b=str(r['source']),str(r['target']); adj.setdefault(a,[]).append(b); adj.setdefault(b,[]).append(a)
    wanted="Person" if q.startswith('who') else "Organization" if 'organization' in q or 'company' in q else ""
    queue=deque([(start,[start])]); seen={start}; candidates=[]
    while queue:
        node,path=queue.popleft()
        if node!=start and (not wanted or types.get(node)==wanted): candidates.append((path,node))
        for nxt in sorted(adj.get(node,[])):
            if nxt not in seen and len(path)<5: seen.add(nxt); queue.append((nxt,path+[nxt]))
    if not candidates: return {"answer":"I don't know","reasoning_path":[],"hops":0}
    path,answer=sorted(candidates,key=lambda x:(len(x[0]),x[1]))[0]
    return {"answer":answer,"reasoning_path":path,"hops":len(path)-1}

@app.post('/community-summary')
def community_summary(req: CommunityRequest) -> dict[str,str]:
    entities=list(dict.fromkeys(req.entities)); rels=[r for r in req.relationships if isinstance(r,dict)]
    facts=[]
    for r in rels:
        s,t,kind=str(r.get('source','')),str(r.get('target','')),str(r.get('relation','')).upper()
        if s and t: facts.append(f"{s} {VERBS.get(kind,kind.lower().replace('_',' '))} {t}")
    if facts: summary="This community centers around " + "; ".join(facts) + "."
    elif entities: summary="This community contains " + ", ".join(entities) + "."
    else: summary="This community has no entities or relationships."
    return {"community_id":req.community_id,"summary":summary}
