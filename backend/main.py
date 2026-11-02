"""StayZen API server.

Run from the backend folder:
    py -m uvicorn main:app --reload
Then open http://127.0.0.1:8000
"""
import asyncio
import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import connect
from routes import admin, auth_routes, guest, staff

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
SIMULATE = os.getenv("SIMULATE_CROWD", "true").lower() == "true"


def nudge_demo_counts():
    """Demo only: small changes to the demo hotel's counts every minute, so the heat map moves
    on stage. The pool is left alone so the 'may be outdated' warning still shows."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT f.id, f.capacity, f.current_count FROM facilities f JOIN hotels h ON h.id=f.hotel_id "
                        "WHERE h.source='demo' AND h.status='approved' AND f.code<>'pool'")
            for f in cur.fetchall():
                new = max(0, min(f["capacity"], f["current_count"] + random.choice([-1, 0, 0, 1])))
                cur.execute("UPDATE facilities SET current_count=%s, last_updated=NOW() WHERE id=%s", (new, f["id"]))
        conn.commit()
    finally:
        conn.close()


async def simulator():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(nudge_demo_counts)
        except Exception as exc:  # keep the server running if MySQL blips
            print("Crowd simulator skipped:", exc)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(simulator()) if SIMULATE else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="StayZen API", version="1.0", lifespan=lifespan)
app.include_router(auth_routes.router)
app.include_router(guest.router)
app.include_router(staff.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# The website itself. Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
