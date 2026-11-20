"""Webflow University MCP/HTTP offline-first connector."""
import hashlib,hmac,os,re,sqlite3,threading,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit,urlunsplit
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI,Depends,Header,HTTPException
from pydantic import BaseModel,Field
from mcp.server.fastmcp import FastMCP

ORIGIN="https://university.webflow.com"
BASE_URL=ORIGIN+"/courses"
DB_PATH=os.getenv("WEBFLOW_UNI_DB",str(Path.home()/".local/share/webflow-university/catalog.db"))
LOCK=threading.RLock()
HEADERS={"User-Agent":"SelmaWebflowUniversityConnector/1.1","Accept":"text/html"}

def canonical_url(value,course=False):
    p=urlsplit(urljoin(ORIGIN+"/",value))
    if p.scheme!="https" or p.hostname!="university.webflow.com" or p.port not in (None,443) or p.username or p.password:
        raise ValueError("Only HTTPS university.webflow.com URLs are allowed")
    path=p.path.rstrip("/")
    if course and not path.startswith("/courses/"):
        raise ValueError("Expected a Webflow University course URL")
    return urlunsplit(("https","university.webflow.com",path or "/","",""))

def connection():
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB_PATH,timeout=20)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=20000")
    c.execute("PRAGMA journal_mode=WAL")
    return c

def initialize():
    with LOCK,connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS courses(course_id TEXT PRIMARY KEY,title TEXT NOT NULL,url TEXT UNIQUE NOT NULL,level TEXT,duration TEXT,summary TEXT,updated_at TEXT NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts USING fts5(course_id UNINDEXED,title,level,summary,content='courses',content_rowid='rowid');
        CREATE TRIGGER IF NOT EXISTS courses_ai AFTER INSERT ON courses BEGIN
          INSERT INTO courses_fts(rowid,course_id,title,level,summary) VALUES(new.rowid,new.course_id,new.title,new.level,new.summary); END;
        CREATE TRIGGER IF NOT EXISTS courses_ad AFTER DELETE ON courses BEGIN
          INSERT INTO courses_fts(courses_fts,rowid,course_id,title,level,summary) VALUES('delete',old.rowid,old.course_id,old.title,old.level,old.summary); END;
        CREATE TRIGGER IF NOT EXISTS courses_au AFTER UPDATE ON courses BEGIN
          INSERT INTO courses_fts(courses_fts,rowid,course_id,title,level,summary) VALUES('delete',old.rowid,old.course_id,old.title,old.level,old.summary);
          INSERT INTO courses_fts(rowid,course_id,title,level,summary) VALUES(new.rowid,new.course_id,new.title,new.level,new.summary); END;
        """)
        c.execute("INSERT INTO courses_fts(courses_fts) VALUES('rebuild')")

def fetch_html(url):
    current=canonical_url(url)
    with httpx.Client(timeout=20,follow_redirects=False,headers=HEADERS) as client:
        for attempt in range(3):
            try:
                for _ in range(5):
                    response=client.get(current)
                    if response.status_code in (301,302,303,307,308):
                        current=canonical_url(urljoin(current,response.headers["location"]))
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("content-type","").lower():
                        raise ValueError("Expected HTML response")
                    return response.text
                raise ValueError("Too many redirects")
            except (httpx.TimeoutException,httpx.TransportError,httpx.HTTPStatusError):
                if attempt==2: raise
                time.sleep(0.5*(attempt+1))

def parse_courses_html(html):
    soup=BeautifulSoup(html,"html.parser")
    found={}
    for a in soup.select("a[href]"):
        try: url=canonical_url(a["href"],course=True)
        except ValueError: continue
        raw=" ".join(a.get_text(" ",strip=True).split())
        heading=a.find(["h2","h3","h4"])
        title=heading.get_text(" ",strip=True) if heading else raw[:100]
        if len(title)<4: continue
        duration=re.search(r"\b(?:\d+h\s*)?\d+m\b|\b\d+h\b",raw,re.I)
        level=re.search(r"\b(Beginner|Intermediate|Advanced)\b",raw,re.I)
        found[url]={"course_id":hashlib.sha256(url.encode()).hexdigest()[:16],"title":title,"url":url,
          "level":level.group(1).capitalize() if level else "All Levels",
          "duration":duration.group() if duration else "Self-paced","summary":raw.replace(title,"",1).strip()[:500]}
    return list(found.values())

def sync_catalog_from_web():
    parsed=parse_courses_html(fetch_html(BASE_URL))
    if not parsed: raise ValueError("No course cards found; cache preserved")
    now=datetime.now(timezone.utc).isoformat()
    initialize()
    with LOCK,connection() as c:
        for item in parsed:
            c.execute("""INSERT INTO courses(course_id,title,url,level,duration,summary,updated_at)
              VALUES(:course_id,:title,:url,:level,:duration,:summary,:updated_at)
              ON CONFLICT(course_id) DO UPDATE SET title=excluded.title,url=excluded.url,level=excluded.level,
              duration=excluded.duration,summary=excluded.summary,updated_at=excluded.updated_at""",{**item,"updated_at":now})
    return {"status":"synced","courses_indexed":len(parsed),"timestamp":now}

def query_courses(query="",level=None,limit=10):
    initialize()
    limit=max(1,min(int(limit),100))
    terms=re.findall(r"\w+",query,flags=re.UNICODE)
    with connection() as c:
        if terms:
            expr=" AND ".join('"'+t+' "*' for t in terms[:12]).replace('" *','"*')
            sql="SELECT c.* FROM courses c JOIN courses_fts ON courses_fts.rowid=c.rowid WHERE courses_fts MATCH ?"
            params=[expr]
        else:
            sql="SELECT c.* FROM courses c WHERE 1=1"
            params=[]
        if level:
            sql+=" AND LOWER(c.level)=LOWER(?)"
            params.append(level)
        sql+=" ORDER BY c.title LIMIT ?"
        params.append(limit)
        return [dict(r) for r in c.execute(sql,params)]

def fetch_course_lessons(course_url):
    course_url=canonical_url(course_url,course=True)
    soup=BeautifulSoup(fetch_html(course_url),"html.parser")
    title=soup.h1.get_text(" ",strip=True) if soup.h1 else course_url
    lessons={}
    for a in soup.select("a[href]"):
        try: url=canonical_url(urljoin(course_url,a["href"]))
        except ValueError: continue
        if "/lesson/" not in url and "/lessons/" not in url: continue
        label=" ".join(a.get_text(" ",strip=True).split())
        if label: lessons[url]={"lesson_title":label,"url":url}
    return {"course_title":title,"course_url":course_url,"lesson_count":len(lessons),"lessons":list(lessons.values())}

mcp=FastMCP("webflow-university-connector")
@mcp.tool()
def sync_webflow_courses()->dict:
    """Refresh public course metadata."""
    return sync_catalog_from_web()
@mcp.tool()
def search_webflow_courses(query:str="",level:str="",limit:int=10)->list[dict]:
    """Search cached course metadata offline."""
    return query_courses(query,level or None,limit)
@mcp.tool()
def get_course_outline(course_url:str)->dict:
    """Retrieve course lesson links."""
    return fetch_course_lessons(course_url)

app=FastAPI(title="Selma Webflow University Bridge",version="1.1.0")
def verify_token(authorization:str=Header(default="")):
    token=os.getenv("CONNECTOR_BEARER_TOKEN","")
    if not token or not hmac.compare_digest(authorization,"Bearer "+token):
        raise HTTPException(401,"Invalid or missing bearer token")
class SearchRequest(BaseModel):
    query:str=Field(default="",max_length=500)
    level:str|None=None
    limit:int=Field(default=10,ge=1,le=100)
@app.get("/health")
def health(): return {"status":"ok","service":"webflow-university","version":"1.1.0"}
@app.post("/v1/sync",dependencies=[Depends(verify_token)])
def http_sync():
    try: return sync_catalog_from_web()
    except (httpx.HTTPError,ValueError) as e: raise HTTPException(502,"Catalog sync failed") from e
@app.post("/v1/search",dependencies=[Depends(verify_token)])
def http_search(req:SearchRequest): return {"results":query_courses(req.query,req.level,req.limit)}
@app.get("/v1/outline",dependencies=[Depends(verify_token)])
def http_outline(url:str):
    try: return fetch_course_lessons(url)
    except ValueError as e: raise HTTPException(400,str(e)) from e
    except httpx.HTTPError as e: raise HTTPException(502,"Upstream request failed") from e
if __name__=="__main__":
    import uvicorn
    initialize()
    if os.getenv("CONNECTOR_MODE","mcp").lower()=="http":
        if not os.getenv("CONNECTOR_BEARER_TOKEN"): raise SystemExit("Set CONNECTOR_BEARER_TOKEN")
        uvicorn.run(app,host="127.0.0.1",port=int(os.getenv("CONNECTOR_PORT","8095")))
    else: mcp.run(transport="stdio")
