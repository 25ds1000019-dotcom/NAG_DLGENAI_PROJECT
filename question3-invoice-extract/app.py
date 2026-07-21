from __future__ import annotations
import re
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="IITM Finance Invoice Extraction API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
class InvoiceRequest(BaseModel):
    invoice_text: str = Field(min_length=1, max_length=30000)
class InvoiceResult(BaseModel):
    invoice_no: str | None = None
    date: str | None = None
    vendor: str | None = None
    amount: float | None = None
    tax: float | None = None
    currency: str | None = None

def grab(pattern, text):
    match = re.search(pattern, text, re.I | re.M)
    return match.group(1).strip() if match else None

def iso(value):
    if not value: return None
    value = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", value.strip(), flags=re.I)
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
        try: return datetime.strptime(value, fmt).date().isoformat()
        except ValueError: pass
    return None

def money(value):
    if not value: return None
    vals = re.findall(r"(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?", value)
    return float(vals[-1].replace(",", "")) if vals else None

def currency(text, explicit):
    if explicit:
        val = explicit.strip().upper()
        if val in {"INR", "USD", "EUR", "GBP", "JPY"}: return val
        if val in {"RS", "RUPEES"}: return "INR"
        if val == "DOLLARS": return "USD"
        if val == "EUROS": return "EUR"
        if val == "POUNDS": return "GBP"
    text = text.upper()
    if re.search(r"₹|\bINR\b|\bRS\.?", text): return "INR"
    if re.search(r"\$|\bUSD\b|\bUS DOLLAR", text): return "USD"
    if re.search(r"€|\bEUR\b|\bEURO", text): return "EUR"
    if re.search(r"£|\bGBP\b|\bPOUND", text): return "GBP"
    if re.search(r"¥|\bJPY\b|\bYEN", text): return "JPY"
    return None

@app.post("/extract", response_model=InvoiceResult)
def extract(request: InvoiceRequest):
    text = request.invoice_text
    inv = grab(r"^\s*(?:invoice\s*(?:no\.?|number|#)?|inv\.?|ref(?:erence)?|bill\s*(?:no\.?|#)?)\s*[:#\-.]*\s*(.+?)\s*$", text)
    if inv: inv = re.sub(r"^(?:invoice|inv|reference|ref|bill)\s*(?:no\.?|number)?\s*[#:.\-]?\s*", "", inv, flags=re.I).strip().strip(". ") or None
    date = grab(r"^\s*(?:date|issued|issue\s*date|invoice\s*date)\s*[:#\-.]*\s*(.+?)\s*$", text)
    vendor = grab(r"^\s*(?:vendor|seller|supplier|billed\s*by|from)\s*[:#\-.]*\s*(.+?)\s*$", text)
    subtotal = grab(r"^\s*(?:subtotal|sub\s*total|net\s*amount|amount\s*before\s*tax)\s*[:#\-.]*\s*(.+?)\s*$", text)
    tax = grab(r"^\s*(?:(?:gst|igst|cgst|sgst|vat|sales\s*tax|tax)(?:\s*\([^\n)]*\))?)\s*[:#\-.]*\s*(.+?)\s*$", text)
    explicit = grab(r"^\s*currency\s*[:#\-.]*\s*(.+?)\s*$", text)
    return InvoiceResult(invoice_no=inv, date=iso(date), vendor=vendor.strip().strip(". ") if vendor else None, amount=money(subtotal), tax=money(tax), currency=currency(text, explicit))

@app.get("/healthz")
def healthz(): return {"status":"ok"}
