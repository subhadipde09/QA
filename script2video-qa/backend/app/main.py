from __future__ import annotations

import asyncio, csv, html, json, os, sqlite3, uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv("S2VQA_DATA_DIR", str(ROOT / "artifacts"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "qa.sqlite3"

class Result(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"

class SourceProvenance(BaseModel):
    source_type: str
    source_record: str
    source_url: str | None = None
    field_name: str
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    derivation: str = "explicit"

class MediaMetadata(BaseModel):
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_video: bool | None = None
    has_audio: bool | None = None

class DialogueRecord(BaseModel):
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    provenance: SourceProvenance | None = None

class CharacterRecord(BaseModel):
    character_id: str
    name: str

class SceneRecord(BaseModel):
    scene_id: str
    order: int
    start_seconds: float | None = None
    end_seconds: float | None = None
    description: str | None = None
    characters: list[str] = []

class GenerationJob(BaseModel):
    job_id: str
    status: str
    created_at: datetime | None = None

class ClipRecord(BaseModel):
    clip_id: str
    clip_number: str
    generation_job: GenerationJob | None = None
    description: str | None = None
    original_script: str | None = None
    characters: list[CharacterRecord] = []
    scenes: list[SceneRecord] = []
    dialogue: list[DialogueRecord] = []
    subtitles: list[DialogueRecord] = []
    video_path: str | None = None
    expected_media: MediaMetadata = Field(default_factory=MediaMetadata)
    provenance: list[SourceProvenance] = []
    connector: str = "mock_fixture"

class ValidationCheck(BaseModel):
    check_id: str
    name: str
    status: Result
    expected: Any = None
    actual: Any = None
    rule: str | None = None
    provenance: list[SourceProvenance] = []
    evidence: list[str] = []
    explanation: str
    duration_ms: float = 0

class TestReport(BaseModel):
    run_id: str
    clip: ClipRecord
    result: Result
    started_at: datetime
    finished_at: datetime
    checks: list[ValidationCheck]
    errors: list[dict[str, str]] = []
    actual_media: MediaMetadata = Field(default_factory=MediaMetadata)
    connector: str
    voice_testing_enabled: bool = False

class RunRequest(BaseModel):
    clip_number: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    voice_testing: bool = False

class YoutubeVideoRequest(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    page_hostname: str = Field(pattern=r"^(?:www\.|m\.)?youtube\.com$|^youtu\.be$", max_length=120)
    page_title: str = Field(default="", max_length=300)
    ready_state: int = Field(ge=0, le=4)
    duration_seconds: float | None = Field(default=None, ge=0, le=86400)
    width: int = Field(default=0, ge=0, le=20000)
    height: int = Field(default=0, ge=0, le=20000)
    media_error: int | None = Field(default=None, ge=1, le=10)
    voice_testing: bool = False

app = FastAPI(title="Script2Video QA", version="0.1.0", description="Local deterministic QA for existing generated clips. Mock connector unless explicitly configured.")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
jobs: dict[str, dict[str, Any]] = {}

def db_init() -> None:
    with sqlite3.connect(DB) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, clip_number TEXT NOT NULL, result TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT NOT NULL, report_json TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES ('voice_testing','false')")
        if not c.execute("SELECT 1 FROM schema_version").fetchone(): c.execute("INSERT INTO schema_version VALUES (1)")
db_init()

def fixture_path() -> Path:
    return ROOT / "fixtures" / "clips.json"

def discover(number: str) -> ClipRecord:
    data = json.loads(fixture_path().read_text(encoding="utf-8"))
    matches = [c for c in data["clips"] if c["clip_number"].lower() == number.lower()]
    if not matches: raise HTTPException(404, detail={"code":"CLIP_NOT_FOUND", "message":f"No clip {number} found in the mock fixture connector."})
    if len(matches) > 1: raise HTTPException(409, detail={"code":"AMBIGUOUS_CLIP", "candidates":[c["clip_id"] for c in matches]})
    return ClipRecord.model_validate(matches[0])

def probe(path: Path) -> tuple[MediaMetadata, str | None]:
    # FFprobe is optional and invoked with a fixed executable/argument list; absence is reported as unavailable.
    import shutil, subprocess
    exe = shutil.which("ffprobe")
    if not exe: return MediaMetadata(), "FFprobe is not installed; media inspection could not run."
    try:
        p = subprocess.run([exe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True, timeout=30, check=True)
        obj = json.loads(p.stdout); streams = obj.get("streams", []); v = next((x for x in streams if x.get("codec_type")=="video"), None); a = next((x for x in streams if x.get("codec_type")=="audio"), None)
        fr = (v or {}).get("avg_frame_rate")
        return MediaMetadata(duration_seconds=float(obj.get("format",{}).get("duration",0)) or None, width=(v or {}).get("width"), height=(v or {}).get("height"), frame_rate=fr, video_codec=(v or {}).get("codec_name"), audio_codec=(a or {}).get("codec_name"), has_video=bool(v), has_audio=bool(a)), None
    except Exception as e: return MediaMetadata(), f"FFprobe inspection failed: {type(e).__name__}."

def build_report(number: str, voice_testing: bool = False) -> TestReport:
    started = datetime.now(timezone.utc); clip = discover(number); checks: list[ValidationCheck] = []; errors = []; actual = MediaMetadata()
    def add(cid: str, name: str, status: Result, expected: Any, value: Any, rule: str, message: str, provenance=None):
        checks.append(ValidationCheck(check_id=cid,name=name,status=status,expected=expected,actual=value,rule=rule,explanation=message,provenance=provenance or []))
    add("job-status","Existing generation job completed", Result.PASS if clip.generation_job.status.lower() in {"complete","completed","succeeded"} else Result.INCONCLUSIVE, "completed", clip.generation_job.status,"status in completed/succeeded","Read-only fixture status; no generation is started.")
    if clip.original_script:
        add("script-present","Original script available",Result.PASS, "non-empty script", "present", "presence only", "Script was supplied by the mock fixture.")
    else: add("script-present","Original script available",Result.INCONCLUSIVE,"non-empty script",None,"presence only","Fixture contains no original script.")
    if clip.video_path:
        video = (ROOT / clip.video_path).resolve()
        if not video.is_relative_to(ROOT.resolve()):
            errors.append({"category":"video_retrieval","message":"Fixture video path escapes the project root."})
            add("video-file","Video file available",Result.FAIL,"safe existing file",str(video),"path containment","Rejected unsafe fixture path.")
        elif video.is_file():
            add("video-file","Video file available",Result.PASS,"existing file",video.name,"exists and contained","Fixture video is available.")
            actual, err = probe(video)
            if err: add("ffprobe","Media inspection",Result.INCONCLUSIVE,"ffprobe-readable media",None,"FFprobe",err); errors.append({"category":"test_infrastructure","message":err})
            else:
                add("video-stream","Video stream present",Result.PASS if actual.has_video else Result.FAIL,True,actual.has_video,"stream exists","Inspected with FFprobe.")
                exp=clip.expected_media
                for key, title in (("duration_seconds","Duration"),("width","Width"),("height","Height"),("frame_rate","Frame rate"),("video_codec","Video codec")):
                    wanted=getattr(exp,key); got=getattr(actual,key)
                    if wanted is None: add("media-"+key,"Expected "+title,Result.INCONCLUSIVE,None,got,"no expectation supplied",f"No explicit expected {title.lower()} was provided.")
                    elif got is None: add("media-"+key,title,Result.INCONCLUSIVE,wanted,None,"exact comparison",f"Actual {title.lower()} unavailable.")
                    else:
                        ok=abs(wanted-got)<=0.25 if isinstance(wanted,(int,float)) and not isinstance(wanted,bool) else str(wanted)==str(got)
                        add("media-"+key,title,Result.PASS if ok else Result.FAIL,wanted,got,"duration tolerance 0.25s; other values exact",f"{title} {'matches' if ok else 'does not match'} explicit expectation.")
        else: add("video-file","Video file available",Result.INCONCLUSIVE,"existing file",str(clip.video_path),"exists and contained","Mock fixture references a video that is not present.")
    else: add("video-file","Video file available",Result.INCONCLUSIVE,"existing video",None,"source-provided video path","Fixture does not contain a video path; retrieval is not configured.")
    # Visual semantics and dialogue-in-audio are unsupported by deterministic checks.
    add("semantic-content","Character/action semantic correctness",Result.INCONCLUSIVE,"trusted structured renderer metadata",None,"no visual AI/ML used","Pixel inspection does not establish character identity or intended action.")
    add("voice-transcription","Local voice transcription and script comparison",Result.INCONCLUSIVE if voice_testing else Result.SKIPPED,"local transcript compared with verified source script" if voice_testing else None,None,"faster-whisper unavailable; never uses cloud transcription" if voice_testing else "voice testing disabled","Voice test enabled but no transcription implementation is installed." if voice_testing else "Voice testing is off; no audio or speech processing was run.")
    failed=any(c.status==Result.FAIL for c in checks); uncertain=any(c.status==Result.INCONCLUSIVE for c in checks)
    result=Result.FAIL if failed else Result.INCONCLUSIVE if uncertain else Result.PASS
    return TestReport(run_id=str(uuid.uuid4()),clip=clip,result=result,started_at=started,finished_at=datetime.now(timezone.utc),checks=checks,errors=errors,actual_media=actual,connector=clip.connector,voice_testing_enabled=voice_testing)

def build_youtube_report(item: YoutubeVideoRequest) -> TestReport:
    started=datetime.now(timezone.utc); checks=[]
    provenance=[SourceProvenance(source_type="active_browser_tab",source_record=item.page_hostname,field_name="video_element_metadata",derivation="read from current page video element by extension content script")]
    def add(cid,name,status,expected,actual,explanation):
        checks.append(ValidationCheck(check_id=cid,name=name,status=status,expected=expected,actual=actual,rule="Browser-visible HTMLMediaElement fields; no stream URL or cookies sent",provenance=provenance,explanation=explanation))
    if item.media_error is not None:
        add("youtube-player","Browser video playback",Result.FAIL,"no HTMLMediaElement error",item.media_error,"The active page's video element reports a playback error.")
    elif item.ready_state>=2 and item.width>0 and item.height>0:
        add("youtube-player","Browser video playback",Result.PASS,"loaded media data and non-zero dimensions",{"ready_state":item.ready_state,"width":item.width,"height":item.height},"The active tab's video element has loaded media data and reports dimensions.")
    else:
        add("youtube-player","Browser video playback",Result.INCONCLUSIVE,"loaded media data and non-zero dimensions",{"ready_state":item.ready_state,"width":item.width,"height":item.height},"The video is not sufficiently loaded in the active tab. Play it briefly and try again.")
    if item.duration_seconds is not None and item.duration_seconds>0:
        add("youtube-duration","Duration available",Result.PASS,"> 0 seconds",item.duration_seconds,"Duration is available from the browser video element; no expected duration was supplied for comparison.")
    else:
        add("youtube-duration","Duration available",Result.INCONCLUSIVE,"finite positive duration",item.duration_seconds,"The browser has not exposed a usable duration.")
    add("youtube-stream-inspection","Codec, full decode and stream integrity",Result.INCONCLUSIVE,"FFprobe/full decode evidence",None,"The extension cannot expose YouTube's browser-only media stream to the local media inspector.")
    add("youtube-visual-checks","Black/frozen frames and visual content",Result.INCONCLUSIVE,"decoded frame evidence and defined thresholds",None,"This run inspects browser metadata only; it does not capture or analyze frames.")
    add("youtube-script-match","Narration/script match",Result.INCONCLUSIVE,"verified expected script and local transcript",None,"No verified source script or local transcription result is available for this YouTube URL.")
    if item.voice_testing:
        add("voice-transcription","Local voice transcription",Result.INCONCLUSIVE,"local speech transcription",None,"Voice testing is enabled, but no local transcription worker is installed.")
    else:
        add("voice-transcription","Local voice transcription",Result.SKIPPED,None,None,"Voice testing is off; no audio or speech processing was run.")
    result=Result.FAIL if any(c.status==Result.FAIL for c in checks) else Result.INCONCLUSIVE
    clip=ClipRecord(clip_id=f"youtube-{item.video_id}",clip_number=f"YT-{item.video_id}",generation_job=None,description=item.page_title or None,connector="youtube_browser_inspection")
    return TestReport(run_id=str(uuid.uuid4()),clip=clip,result=result,started_at=started,finished_at=datetime.now(timezone.utc),checks=checks,actual_media=MediaMetadata(duration_seconds=item.duration_seconds,width=item.width or None,height=item.height or None,has_video=item.ready_state>=2),connector="youtube_browser_inspection",voice_testing_enabled=item.voice_testing)

def save(report: TestReport) -> None:
    obj=report.model_dump(mode="json")
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)",(report.run_id,report.clip.clip_number,report.result.value,report.started_at.isoformat(),report.finished_at.isoformat(),json.dumps(obj)))
    (DATA / f"{report.run_id}.json").write_text(json.dumps(obj,indent=2),encoding="utf-8")
    rows=[x.model_dump(mode="json") for x in report.checks]
    with (DATA / f"{report.run_id}.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["check_id"]); w.writeheader(); w.writerows(rows)
    checks="".join(f"<tr><td>{html.escape(c.check_id)}</td><td>{html.escape(c.name)}</td><td>{html.escape(c.status.value)}</td><td>{html.escape(c.explanation)}</td></tr>" for c in report.checks)
    page=f"<!doctype html><meta charset='utf-8'><title>Script2Video QA {html.escape(report.run_id)}</title><h1>{html.escape(report.result.value)} — {html.escape(report.clip.clip_number)}</h1><p>Connector: {html.escape(report.connector)} · Run {html.escape(report.run_id)}</p><table border='1' cellpadding='6'><tr><th>ID</th><th>Check</th><th>Status</th><th>Explanation</th></tr>{checks}</table>"
    (DATA / f"{report.run_id}.html").write_text(page,encoding="utf-8")

async def execute(run_id: str, number: str, voice_testing: bool = False):
    jobs[run_id].update(state="running", progress=10, stage="Discovering clip")
    try:
        await asyncio.sleep(0)
        jobs[run_id].update(progress=50,stage="Inspecting existing media")
        report=await asyncio.to_thread(build_report,number,voice_testing); save(report)
        jobs[run_id].update(state="completed",progress=100,stage="Report saved",report=report.model_dump(mode="json"))
    except HTTPException as e: jobs[run_id].update(state="failed",error=e.detail,progress=100)
    except Exception as e: jobs[run_id].update(state="failed",error={"category":"test_infrastructure","message":type(e).__name__},progress=100)

async def execute_youtube(run_id: str, item: YoutubeVideoRequest):
    jobs[run_id].update(state="running",progress=50,stage="Evaluating browser-visible YouTube metadata")
    try:
        report=await asyncio.to_thread(build_youtube_report,item);save(report)
        jobs[run_id].update(state="completed",progress=100,stage="Browser metadata report saved",report=report.model_dump(mode="json"))
    except Exception as e: jobs[run_id].update(state="failed",error={"category":"test_infrastructure","message":type(e).__name__},progress=100)

@app.get("/api/health")
def health(): return {"status":"ok","connector":"mock_fixture","database":str(DB)}

@app.get("/health")
def health_alias(): return health()

@app.get("/api/v1/clip/current")
def current_page_context():
    return {"available":False,"connector":"mock_fixture","message":"No live application adapter or page-to-backend metadata bridge is configured."}

@app.get("/api/config")
def config(): return {"connector":"mock_fixture","live_integration_configured":False,"ffprobe_available":__import__("shutil").which("ffprobe") is not None}

@app.get("/api/clips/{clip_number}")
def clip(clip_number: str): return discover(clip_number)

@app.post("/api/runs",status_code=202)
async def start(req: RunRequest):
    for jid,j in jobs.items():
        if j.get("clip_number")==req.clip_number and j.get("state") in {"queued","running"}: return {"job_id":jid,"state":j["state"],"duplicate":True}
    active=sum(j.get("state") in {"queued","running"} for j in jobs.values())
    if active >= int(os.getenv("S2VQA_MAX_JOBS", "2")): raise HTTPException(429,"Maximum concurrent test jobs reached")
    jid=str(uuid.uuid4()); jobs[jid]={"job_id":jid,"clip_number":req.clip_number,"state":"queued","progress":0,"stage":"Queued"}; asyncio.create_task(execute(jid,req.clip_number,req.voice_testing)); return {"job_id":jid,"state":"queued"}

@app.post("/api/v1/tests",status_code=202)
async def start_v1(req: RunRequest): return await start(req)

@app.post("/api/v1/tests/youtube",status_code=202)
async def start_youtube(item: YoutubeVideoRequest):
    active=sum(j.get("state") in {"queued","running"} for j in jobs.values())
    if active>=int(os.getenv("S2VQA_MAX_JOBS","2")): raise HTTPException(429,"Maximum concurrent test jobs reached")
    jid=str(uuid.uuid4());clip_number=f"YT-{item.video_id}";jobs[jid]={"job_id":jid,"clip_number":clip_number,"state":"queued","progress":0,"stage":"Queued"};asyncio.create_task(execute_youtube(jid,item));return {"job_id":jid,"state":"queued"}

@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    if job_id not in jobs: raise HTTPException(404,"Job not found")
    return {k:v for k,v in jobs[job_id].items() if k!="report"} | ({"report_url":f"/api/runs/{jobs[job_id]['report']['run_id']}"} if jobs[job_id].get("report") else {})

@app.delete("/api/jobs/{job_id}")
def cancel(job_id: str):
    if job_id not in jobs: raise HTTPException(404,"Job not found")
    if jobs[job_id]["state"] in {"queued","running"}: jobs[job_id].update(state="cancelled",stage="Cancelled")
    return {"job_id":job_id,"state":jobs[job_id]["state"]}

@app.get("/api/v1/tests/{test_id}")
def test_status_v1(test_id: str):
    if test_id in jobs: return job(test_id)
    try: return get_report(test_id)
    except HTTPException: raise HTTPException(404,"Test not found")

@app.post("/api/v1/tests/{test_id}/cancel")
def cancel_v1(test_id: str): return cancel(test_id)

def get_report(run_id: str):
    with sqlite3.connect(DB) as c: row=c.execute("SELECT report_json FROM runs WHERE run_id=?",(run_id,)).fetchone()
    if not row: raise HTTPException(404,"Run not found")
    return json.loads(row[0])

@app.get("/api/runs")
def history():
    with sqlite3.connect(DB) as c: rows=c.execute("SELECT run_id,clip_number,result,started_at,finished_at FROM runs ORDER BY started_at DESC LIMIT 100").fetchall()
    return [{"run_id":a,"clip_number":b,"result":c,"started_at":d,"finished_at":e} for a,b,c,d,e in rows]

@app.get("/api/v1/reports")
def reports_v1(): return history()

@app.get("/api/runs/{run_id}")
def report(run_id: str): return get_report(run_id)

@app.get("/api/v1/reports/{test_id}")
def report_v1(test_id: str):
    if test_id in jobs and jobs[test_id].get("report"): return jobs[test_id]["report"]
    return get_report(test_id)

@app.get("/api/v1/settings")
def settings_v1():
    with sqlite3.connect(DB) as c: row=c.execute("SELECT value FROM settings WHERE key='voice_testing'").fetchone()
    return {"voice_testing": bool(row and row[0]=="true"),"voice_testing_available":False,"connector":"mock_fixture"}

@app.put("/api/v1/settings")
def update_settings_v1(value: dict[str, bool]):
    if set(value) != {"voice_testing"} or not isinstance(value["voice_testing"], bool): raise HTTPException(422,"Expected a boolean voice_testing setting")
    with sqlite3.connect(DB) as c: c.execute("INSERT INTO settings(key,value) VALUES('voice_testing',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",("true" if value["voice_testing"] else "false",))
    return settings_v1()

@app.get("/api/runs/{run_id}/download/{fmt}")
def download(run_id: str, fmt: str):
    if fmt not in {"json","html","csv"}: raise HTTPException(400,"Format must be json, html, or csv")
    get_report(run_id); p=DATA / f"{run_id}.{fmt}"
    if not p.exists(): raise HTTPException(404,"Artifact not found")
    return Response(p.read_bytes(),media_type={"json":"application/json","html":"text/html","csv":"text/csv"}[fmt],headers={"Content-Disposition":f'attachment; filename="{run_id}.{fmt}"'})

@app.get("/api/runs/{run_id}/compare/{other_id}")
def compare(run_id: str,other_id: str):
    a=get_report(run_id); b=get_report(other_id); by={c["check_id"]:c for c in a["checks"]}
    return {"run_a":run_id,"run_b":other_id,"changes":[{"check_id":c["check_id"],"a":by.get(c["check_id"],{}).get("status"),"b":c["status"]} for c in b["checks"] if by.get(c["check_id"],{}).get("status")!=c["status"]]}
