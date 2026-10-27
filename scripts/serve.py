"""Starter API-et lokalt: python scripts/serve.py  ->  http://localhost:8000/docs"""
import os

import uvicorn
from _common import ROOT

if __name__ == "__main__":
    os.chdir(ROOT)
    uvicorn.run("klatreforhold.api:app", host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")), reload=bool(os.environ.get("RELOAD")))
