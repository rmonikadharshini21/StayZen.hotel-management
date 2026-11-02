"""Stays Admin portal: verify hotels, review updates, watch data freshness and feedback."""
from fastapi import APIRouter, Depends, HTTPException

from auth import require
from db import get_db

router = APIRouter(prefix="/api/admin")
admin = require("admin")

RATINGS = ["overall", "clean", "facilities", "staff", "accuracy", "nav", "crowd", "queue"]


@router.get("/summary")
def summary(user=Depends(admin), db=Depends(get_db)):
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) n FROM hotels GROUP BY status")}
    stale = db.all(
        "SELECT h.name AS hotel, t.name AS facility, TIMESTAMPDIFF(MINUTE, f.last_updated, NOW()) AS mins "
        "FROM facilities f JOIN hotels h ON h.id=f.hotel_id JOIN facility_types t ON t.code=f.code "
        "WHERE h.status='approved' AND f.last_updated < NOW() - INTERVAL 15 MINUTE ORDER BY mins DESC LIMIT 200")
    updates = db.all(
        "SELECT u.id, h.name AS hotel, u.change_text AS text, u.reviewed, "
        "TIMESTAMPDIFF(MINUTE, u.created_at, NOW()) AS mins_ago "
        "FROM hotel_updates u JOIN hotels h ON h.id=u.hotel_id ORDER BY u.id DESC LIMIT 100")
    fb_rows = db.all(
        "SELECT f.*, h.name AS hotel, b.booking_code FROM feedback f JOIN hotels h ON h.id=f.hotel_id "
        "JOIN bookings b ON b.id=f.booking_id ORDER BY f.id DESC")
    groups = {}
    for f in fb_rows:
        g = groups.setdefault(f["hotel"], {"hotel": f["hotel"], "rows": []})
        g["rows"].append(f)
    feedback = []
    for g in groups.values():
        rows = g["rows"]
        feedback.append({
            "hotel": g["hotel"], "count": len(rows),
            "avg": {k: round(sum(r[k] for r in rows) / len(rows), 1) for k in RATINGS},
            "comments": [{"code": r["booking_code"], "text": r["comments"]} for r in rows if r["comments"]],
        })
    return {
        "stats": {"live": counts.get("approved", 0), "pending": counts.get("pending", 0), "listed": counts.get("listed", 0),
                  "bookings": db.one("SELECT COUNT(*) n FROM bookings")["n"], "stale": len(stale)},
        "stale": stale, "updates": updates, "feedback": feedback,
    }


@router.get("/hotels")
def hotels(district: str = "", status: str = "", q: str = "", user=Depends(admin), db=Depends(get_db)):
    where, args = ["1=1"], []
    if district:
        where.append("h.district=%s"); args.append(district)
    if status:
        where.append("h.status=%s"); args.append(status)
    if q:
        where.append("h.name LIKE %s"); args.append(f"%{q}%")
    rows = db.all(
        "SELECT h.id, h.name, h.district, h.area, h.phone, h.status, h.source, MIN(r.price_per_night) AS min_price "
        "FROM hotels h LEFT JOIN rooms r ON r.hotel_id=h.id WHERE " + " AND ".join(where) +
        " GROUP BY h.id ORDER BY FIELD(h.status,'pending','approved','listed','suspended','rejected'), h.name LIMIT 60", args)
    return rows


def _set_status(db, hotel_id, status):
    if not db.one("SELECT id FROM hotels WHERE id=%s", (hotel_id,)):
        raise HTTPException(404, "Hotel not found.")
    db.run("UPDATE hotels SET status=%s WHERE id=%s", (status, hotel_id))
    return {"ok": True}


@router.post("/hotels/{hotel_id}/approve")
def approve(hotel_id: int, user=Depends(admin), db=Depends(get_db)):
    return _set_status(db, hotel_id, "approved")


@router.post("/hotels/{hotel_id}/reject")
def reject(hotel_id: int, user=Depends(admin), db=Depends(get_db)):
    return _set_status(db, hotel_id, "rejected")


@router.post("/hotels/{hotel_id}/suspend")
def suspend(hotel_id: int, user=Depends(admin), db=Depends(get_db)):
    return _set_status(db, hotel_id, "suspended")


@router.delete("/hotels/{hotel_id}")
def remove(hotel_id: int, user=Depends(admin), db=Depends(get_db)):
    db.run("UPDATE users SET hotel_id=NULL WHERE hotel_id=%s", (hotel_id,))
    db.run("DELETE FROM hotels WHERE id=%s", (hotel_id,))
    return {"ok": True}


@router.post("/updates/{uid}/reviewed")
def reviewed(uid: int, user=Depends(admin), db=Depends(get_db)):
    db.run("UPDATE hotel_updates SET reviewed=TRUE WHERE id=%s", (uid,))
    return {"ok": True}
