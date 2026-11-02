"""Guest portal: search, compare, pre-booking, in-hotel crowd view, queue tokens, chat, feedback."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require
from db import get_db
from services import chatbot
from services.llm import ask_ai
from services.crowd import load_facilities
from services.hotels import (BOOKING_SELECT, booking_public, hotel_public, marks, new_booking_code, notify,
                             rooms_and_amenities)
from services.scoring import distance_km, evaluate, nights_between, rooms_needed

router = APIRouter(prefix="/api")
guest = require("guest")


# ---------- search ----------
@router.get("/hotels/search")
def search(district: str = "", lat: float | None = None, lng: float | None = None,
           budget: int = Query(2500, gt=0), guests: int = Query(2, ge=1, le=8),
           check_in: date = Query(...), check_out: date = Query(...), wants: str = "",
           user=Depends(guest), db=Depends(get_db)):
    nights = nights_between(check_in, check_out)
    if nights < 1:
        raise HTTPException(400, "Check-out must be at least one day after check-in.")
    want_list = [w for w in wants.split(",") if w]

    if lat is not None and lng is not None:
        origin = (lat, lng)
        rows = db.all("SELECT * FROM hotels WHERE status IN ('approved','listed')")
        rows = [h for h in rows if distance_km(origin, (float(h["latitude"]), float(h["longitude"]))) <= 25]
    else:
        rows = db.all("SELECT * FROM hotels WHERE status IN ('approved','listed') AND district=%s", (district,))
        c = db.one("SELECT AVG(latitude) a, AVG(longitude) b FROM hotels WHERE district=%s", (district,))
        if not c or c["a"] is None:
            raise HTTPException(404, "No hotels found for that district.")
        origin = (float(c["a"]), float(c["b"]))

    ids = [h["id"] for h in rows]
    rooms, amen = rooms_and_amenities(db, ids)
    dists = sorted({h["district"] for h in rows})
    rest = db.all(f"SELECT name, cuisine, latitude, longitude, district FROM restaurants WHERE district IN ({marks(len(dists))})",
                  dists) if dists else []

    out = []
    for h in rows:
        r = evaluate(h, rooms.get(h["id"], []), amen.get(h["id"], []), origin, budget, guests, nights, want_list)
        hp = (float(h["latitude"]), float(h["longitude"]))
        food = sorted(((distance_km(hp, (float(x["latitude"]), float(x["longitude"]))), x) for x in rest
                       if x["district"] == h["district"]), key=lambda t: t[0])
        food = [(d, x) for d, x in food if d <= 1]
        r["hotel"] = hotel_public(h, amen.get(h["id"], []))
        r["bookable"] = h["status"] == "approved"
        r["food"] = {"count": len(food), "top": [{"name": x["name"], "cuisine": x["cuisine"] or "", "km": round(d, 1)}
                                                 for d, x in food[:3]]}
        out.append(r)
    out.sort(key=lambda r: (not r["bookable"], -r["score"]))
    return {"origin": {"lat": origin[0], "lng": origin[1]}, "results": out}


@router.get("/hotels/{hotel_id}")
def hotel_detail(hotel_id: int, user=Depends(guest), db=Depends(get_db)):
    """Everything on the hotel page: rooms, full facility details, nearby food, contact."""
    h = db.one("SELECT * FROM hotels WHERE id=%s AND status IN ('approved','listed')", (hotel_id,))
    if not h:
        raise HTTPException(404, "This hotel is not available.")
    rooms, amen = rooms_and_amenities(db, [hotel_id])
    facs = db.all(
        "SELECT f.code, t.name, f.open_hours, f.staff_help, f.equipment, f.notes FROM facilities f "
        "JOIN facility_types t ON t.code=f.code WHERE f.hotel_id=%s AND f.code<>'reception' "
        "ORDER BY t.grid_row, t.grid_col", (hotel_id,))
    hp = (float(h["latitude"]), float(h["longitude"]))
    rest = db.all("SELECT name, cuisine, latitude, longitude FROM restaurants WHERE district=%s", (h["district"],))
    food = sorted(((distance_km(hp, (float(x["latitude"]), float(x["longitude"]))), x) for x in rest), key=lambda t: t[0])
    food = [{"name": x["name"], "cuisine": x["cuisine"] or "", "km": round(d, 1)} for d, x in food if d <= 1][:10]
    return {
        "hotel": hotel_public(h, amen.get(hotel_id, [])),
        "rooms": [{"id": r["id"], "type": r["room_type"], "ac": r["ac"], "price": r["price_per_night"],
                   "avail": r["rooms_available"]} for r in rooms.get(hotel_id, [])],
        "facilities": [{k: (f[k] or "") for k in ("code", "name", "open_hours", "staff_help", "equipment", "notes")} for f in facs],
        "food": food,
    }


# ---------- bookings ----------
class BookingIn(BaseModel):
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=8)


@router.post("/bookings")
def create_booking(body: BookingIn, user=Depends(guest), db=Depends(get_db)):
    h = db.one("SELECT * FROM hotels WHERE id=%s", (body.hotel_id,))
    if not h or h["status"] != "approved":
        raise HTTPException(400, "Pre-booking opens only for hotels with a verified owner.")
    room = db.one("SELECT * FROM rooms WHERE id=%s AND hotel_id=%s", (body.room_id, body.hotel_id))
    if not room:
        raise HTTPException(400, "That room type is not available at this hotel.")
    nights = nights_between(body.check_in, body.check_out)
    if nights < 1:
        raise HTTPException(400, "Check-out must be at least one day after check-in.")
    need = rooms_needed(body.guests)
    if room["rooms_available"] < need:
        raise HTTPException(400, "Not enough rooms left for your group. Pick another hotel.")
    total = room["price_per_night"] * nights * need  # the system calculates the price, never the chatbot
    code = new_booking_code(db)
    db.run("INSERT INTO bookings (booking_code, guest_id, hotel_id, room_id, room_type, rooms_count, check_in, "
           "check_out, nights, guests, total_cost) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
           (code, user["id"], h["id"], room["id"], f"{room['room_type']} {room['ac']}", need, body.check_in,
            body.check_out, nights, body.guests, total))
    b = db.one(BOOKING_SELECT + "WHERE b.booking_code=%s", (code,))
    return booking_public(b)


@router.get("/bookings/mine")
def my_bookings(user=Depends(guest), db=Depends(get_db)):
    rows = db.all(BOOKING_SELECT + "WHERE b.guest_id=%s ORDER BY b.id DESC", (user["id"],))
    return [booking_public(b) for b in rows]


def _my_booking(db, user, code):
    b = db.one("SELECT * FROM bookings WHERE booking_code=%s AND guest_id=%s", (code, user["id"]))
    if not b:
        raise HTTPException(404, "Booking not found.")
    return b


@router.post("/bookings/{code}/checkin")
def self_checkin(code: str, user=Depends(guest), db=Depends(get_db)):
    b = _my_booking(db, user, code)
    if b["status"] != "confirmed":
        raise HTTPException(400, "You can check in only after the hotel confirms your booking.")
    db.run("UPDATE bookings SET status='checked_in' WHERE id=%s", (b["id"],))
    return {"ok": True}


@router.post("/bookings/{code}/finish")
def finish_trip(code: str, user=Depends(guest), db=Depends(get_db)):
    b = _my_booking(db, user, code)
    if b["status"] != "checked_in":
        raise HTTPException(400, "Only a checked-in stay can be finished.")
    db.run("UPDATE bookings SET status='completed' WHERE id=%s", (b["id"],))
    db.run("UPDATE queue_tokens q JOIN facilities f ON f.id=q.facility_id SET q.status='cancelled' "
           "WHERE q.guest_id=%s AND f.hotel_id=%s AND q.status='waiting'", (user["id"], b["hotel_id"]))
    return {"ok": True}


class FeedbackIn(BaseModel):
    overall: int = Field(ge=1, le=5)
    clean: int = Field(ge=1, le=5)
    facilities: int = Field(ge=1, le=5)
    staff: int = Field(ge=1, le=5)
    accuracy: int = Field(ge=1, le=5)
    nav: int = Field(ge=1, le=5)
    crowd: int = Field(ge=1, le=5)
    queue: int = Field(ge=1, le=5)
    comments: str = ""


@router.post("/bookings/{code}/feedback")
def feedback(code: str, body: FeedbackIn, user=Depends(guest), db=Depends(get_db)):
    b = _my_booking(db, user, code)
    if b["status"] != "completed":
        raise HTTPException(400, "Finish your trip before giving feedback.")
    if db.one("SELECT id FROM feedback WHERE booking_id=%s", (b["id"],)):
        raise HTTPException(409, "You already sent feedback for this stay.")
    db.run("INSERT INTO feedback (booking_id, hotel_id, overall, clean, facilities, staff, accuracy, nav, crowd, queue, comments) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
           (b["id"], b["hotel_id"], body.overall, body.clean, body.facilities, body.staff, body.accuracy, body.nav,
            body.crowd, body.queue, body.comments.strip()[:1000]))
    return {"ok": True}


@router.post("/demo-stay")
def demo_stay(user=Depends(guest), db=Depends(get_db)):
    """Skip ahead for the demo: a confirmed, checked-in stay at the demo hotel."""
    h = db.one("SELECT * FROM hotels WHERE source='demo' AND status='approved' ORDER BY id LIMIT 1")
    room = db.one("SELECT * FROM rooms WHERE hotel_id=%s ORDER BY price_per_night LIMIT 1", (h["id"],))
    code = new_booking_code(db)
    db.run("INSERT INTO bookings (booking_code, guest_id, hotel_id, room_id, room_type, rooms_count, check_in, check_out, "
           "nights, guests, total_cost, status) VALUES (%s,%s,%s,%s,%s,1,CURDATE(),CURDATE()+INTERVAL 2 DAY,2,2,%s,'checked_in')",
           (code, user["id"], h["id"], room["id"], f"{room['room_type']} {room['ac']}", room["price_per_night"] * 2))
    return {"code": code, "hotel": h["name"]}


# ---------- in-hotel ----------
def _stay(db, user):
    return db.one("SELECT b.booking_code, h.* FROM bookings b JOIN hotels h ON h.id=b.hotel_id "
                  "WHERE b.guest_id=%s AND b.status='checked_in' ORDER BY b.id DESC LIMIT 1", (user["id"],))


def _booked(db, user):
    """The hotel the guest has an active booking at (checked in first, then confirmed, then pending)."""
    return db.one("SELECT b.booking_code, b.status AS booking_status, h.* FROM bookings b JOIN hotels h ON h.id=b.hotel_id "
                  "WHERE b.guest_id=%s AND b.status IN ('checked_in','confirmed','pending') "
                  "ORDER BY FIELD(b.status,'checked_in','confirmed','pending'), b.id DESC LIMIT 1", (user["id"],))


@router.get("/stay")
def stay(code: str = "", user=Depends(guest), db=Depends(get_db)):
    """Crowd heat map for the hotel of the Booking ID the guest enters. Queue tokens need check-in."""
    if not code.strip():
        return {"stay": None}
    h = db.one("SELECT b.booking_code, b.status AS booking_status, h.* FROM bookings b JOIN hotels h ON h.id=b.hotel_id "
               "WHERE b.booking_code=%s AND b.guest_id=%s AND b.status IN ('checked_in','confirmed','pending')",
               (code.strip().upper(), user["id"]))
    if not h:
        raise HTTPException(404, "No active booking found with that ID. Check My bookings for your Booking ID.")
    return {"stay": {"booking_code": h["booking_code"], "status": h["booking_status"], "hotel": hotel_public(h),
                     "facilities": load_facilities(db, h["id"], user["id"])}}


class TokenIn(BaseModel):
    facility: str


@router.post("/stay/tokens")
def get_token(body: TokenIn, user=Depends(guest), db=Depends(get_db)):
    h = _stay(db, user)
    if not h:
        raise HTTPException(400, "Check in first to get a queue token.")
    f = next((x for x in load_facilities(db, h["id"], user["id"]) if x["code"] == body.facility), None)
    if not f:
        raise HTTPException(404, "This hotel does not have that facility.")
    if f["my_token"]:
        return {"token": f["my_token"]}
    if f["level"] != "high":
        raise HTTPException(400, "This facility is not crowded. You can go now.")
    tid = db.run("INSERT INTO queue_tokens (token_code, facility_id, guest_id) VALUES ('', %s, %s)", (f["id"], user["id"]))
    token = f"Q-{tid:03d}"
    db.run("UPDATE queue_tokens SET token_code=%s WHERE id=%s", (token, tid))
    return {"token": token}


@router.delete("/stay/tokens/{facility}")
def cancel_token(facility: str, user=Depends(guest), db=Depends(get_db)):
    h = _stay(db, user)
    if h:
        db.run("UPDATE queue_tokens q JOIN facilities f ON f.id=q.facility_id SET q.status='cancelled' "
               "WHERE q.guest_id=%s AND f.hotel_id=%s AND f.code=%s AND q.status='waiting'", (user["id"], h["id"], facility))
    return {"ok": True}


# ---------- notifications & chat ----------
@router.get("/notifications")
def notifications(user=Depends(guest), db=Depends(get_db)):
    return db.all("SELECT id, message, kind FROM notifications WHERE user_id=%s AND seen=FALSE ORDER BY id", (user["id"],))


@router.post("/notifications/{nid}/seen")
def seen(nid: int, user=Depends(guest), db=Depends(get_db)):
    db.run("UPDATE notifications SET seen=TRUE WHERE id=%s AND user_id=%s", (nid, user["id"]))
    return {"ok": True}


class ChatIn(BaseModel):
    message: str
    lang: str = "en"
    history: list[dict] = []


@router.post("/chat")
def chat(body: ChatIn, user=Depends(guest), db=Depends(get_db)):
    msg = body.message[:500]
    ai = ask_ai(db, user, msg, body.lang, body.history)  # AI chat when a key is set in .env
    return {"reply": ai or chatbot.reply(db, user, msg, body.lang)}


@router.get("/places/last-hotel")
def last_hotel(user=Depends(guest), db=Depends(get_db)):
    """Location used by the Safety tab: the current stay, else the latest booking."""
    h = db.one("SELECT h.name, h.latitude, h.longitude FROM bookings b JOIN hotels h ON h.id=b.hotel_id "
               "WHERE b.guest_id=%s ORDER BY (b.status='checked_in') DESC, b.id DESC LIMIT 1", (user["id"],))
    return {"hotel": {"name": h["name"], "lat": float(h["latitude"]), "lng": float(h["longitude"])} if h else None}