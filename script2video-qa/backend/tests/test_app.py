import asyncio
import httpx
from app.main import app

def test_health_marks_fixture():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            return await client.get("/api/health")
    response=asyncio.run(check())
    assert response.json()["connector"] == "mock_fixture"

def test_clip_discovery():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            return await client.get("/api/clips/CLIP-102")
    response = asyncio.run(check())
    assert response.status_code == 200
    assert response.json()["generation_job"]["job_id"] == "fixture-job-102"

def test_missing_clip_is_explicit():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            return await client.get("/api/clips/CLIP-999")
    assert asyncio.run(check()).status_code == 404

def test_run_persists_report():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            started = await client.post("/api/runs", json={"clip_number":"CLIP-102"})
            assert started.status_code == 202
            jid = started.json()["job_id"]
            for _ in range(100):
                status = (await client.get(f"/api/jobs/{jid}")).json()
                if status["state"] in {"completed","failed"}: break
                await asyncio.sleep(.01)
            assert status["state"] == "completed"
            report = (await client.get(status["report_url"])).json()
            assert report["connector"] == "mock_fixture"
            assert report["result"] == "INCONCLUSIVE"
            assert any(c["check_id"] == "semantic-content" and c["status"] == "INCONCLUSIVE" for c in report["checks"])
    asyncio.run(check())

def test_extension_settings_and_api_aliases():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            assert (await client.get("/health")).json()["status"] == "ok"
            current=(await client.get("/api/v1/clip/current")).json()
            assert current["available"] is False
            prefs=await client.put("/api/v1/settings",json={"voice_testing":True})
            assert prefs.json()["voice_testing"] is True
            assert prefs.json()["voice_testing_available"] is False
            started=await client.post("/api/v1/tests",json={"clip_number":"CLIP-102","voice_testing":True})
            assert started.status_code==202
            jid=started.json()["job_id"]
            for _ in range(100):
                status=(await client.get(f"/api/v1/tests/{jid}")).json()
                if status["state"] in {"completed","failed"}: break
                await asyncio.sleep(.01)
            report=(await client.get(f"/api/v1/reports/{jid}")).json()
            voice=[c for c in report["checks"] if c["check_id"]=="voice-transcription"][0]
            assert voice["status"]=="INCONCLUSIVE"
            assert report["voice_testing_enabled"] is True
            await client.put("/api/v1/settings",json={"voice_testing":False})
    asyncio.run(check())

def test_youtube_browser_metadata_path_is_labeled_and_limited():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            started=await client.post("/api/v1/tests/youtube",json={"video_id":"XF4I1T8kLUo","page_hostname":"www.youtube.com","page_title":"Sample short","ready_state":4,"duration_seconds":30.4,"width":1080,"height":1920,"voice_testing":False})
            assert started.status_code==202
            jid=started.json()["job_id"]
            for _ in range(100):
                status=(await client.get(f"/api/v1/tests/{jid}")).json()
                if status["state"] in {"completed","failed"}: break
                await asyncio.sleep(.01)
            assert status["state"]=="completed"
            report=(await client.get(f"/api/v1/reports/{jid}")).json()
            assert report["connector"]=="youtube_browser_inspection"
            assert report["clip"]["generation_job"] is None
            assert report["result"]=="INCONCLUSIVE"
            statuses={c["check_id"]:c["status"] for c in report["checks"]}
            assert statuses["youtube-player"]=="PASS"
            assert statuses["youtube-stream-inspection"]=="INCONCLUSIVE"
            assert statuses["voice-transcription"]=="SKIPPED"
            invalid=await client.post("/api/v1/tests/youtube",json={"video_id":"../bad","page_hostname":"evil.example","ready_state":4})
            assert invalid.status_code==422
    asyncio.run(check())
