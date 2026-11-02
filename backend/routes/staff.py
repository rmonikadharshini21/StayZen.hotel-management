"""Hotel Management portal: pre-bookings, arrival check, head counts, queues, hotel details, registration."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require
from db import get_db
from services.catalog import AMENITIES
from services.crowd import load_facilities
from services.hotels import (BOOKING_SELECT, booking_public, hotel_public, notify, rooms_and_amenities,
                             sync_facilities)

router = APIRouter(prefix="/api/staff")
staff = require("staff")

# Demo convenience: one manager account can switch between verified hotels.
# Set STAFF_DEMO_SWITCH=false in .env so each manager only sees their own hotels.
DEMO_SWITCH = os.getenv("STAFF_DEMO_SWITCH", "true").lower() == "true"


def allowed_ids(db, user):
    own = {r["id"] for r in db.all("SELECT id FROM hotels WHERE id=%s", (user["hotel_id"],))} if user["hotel_id"] else set()
    if DEMO_SWITCH:
        own |= {r["id"] for r in db.all("SELECT id FROM hotels WHERE status IN ('approved','pending')")}
    return own


def check_hotel(db, user, hotel_id):
    if hotel_id not in allowed_ids(db, user):
        raise HTTPException(403, "You do not manage this hotel.")
    h = db.one("SELECT * FROM hotels WHERE id=%s", (hotel_id,))
    if not h:
        raise HTTPException(404, "Hotel not found.")
    return h


@router.get("/hotels")
def my_hotels(user=Depends(staff), db=Depends(get_db)):
    ids = allowed_ids(db, user)
    if not ids:
        return []
    rows = db.all(f"SELECT id, name, district, status FROM hotels WHERE id IN ({','.join(['%s'] * len(ids))}) "
                  "ORDER BY (id=%s) DESC, district, name", list(ids) + [user["hotel_id"] or 0])
    return rows


@router.get("/hotels/{hotel_id}")
def hotel_detail(hotel_id: int, user=Depends(staff), db=Depends(get_db)):
    h = check_hotel(db, user, hotel_id)
    rooms, amen = rooms_and_amenities(db, [hotel_id])
    bookings = db.all(BOOKING_SELECT + "WHERE b.hotel_id=%s ORDER BY b.id DESC", (hotel_id,))
    return {
        "hotel": hotel_public(h, amen.get(hotel_id, [])),
        "rooms": [{"id": r["id"], "type": r["room_type"], "ac": r["ac"], "price": r["price_per_night"],
                   "avail": r["rooms_available"]} for r in rooms.get(hotel_id, [])],
        "facilities": load_facilities(db, hotel_id),
        "bookings": [booking_public(b) for b in bookings],
    }


def _hotel_booking(db, user, code):
    b = db.one("SELECT * FROM bookings WHERE booking_code=%s", (code.strip().upper(),))
    if not b:
        raise HTTPException(404, f"No booking found for {code}.")
    check_hotel(db, user, b["hotel_id"])
    return b


@router.post("/bookings/{code}/accept")
def accept(code: str, user=Depends(staff), db=Depends(get_db)):
    b = _hotel_booking(db, user, code)
    if b["status"] != "pending":
        raise HTTPException(400, "Only pending requests can be accepted.")
    room = db.one("SELECT * FROM rooms WHERE id=%s", (b["room_id"],))
    if room and room["rooms_available"] < b["rooms_count"]:
        raise HTTPException(400, "Not enough rooms left. Update availability or reject the request.")
    if room:
        db.run("UPDATE rooms SET rooms_available=rooms_available-%s WHERE id=%s", (b["rooms_count"], room["id"]))
    db.run("UPDATE bookings SET status='confirmed' WHERE id=%s", (b["id"],))
    h = db.one("SELECT name FROM hotels WHERE id=%s", (b["hotel_id"],))
    notify(db, b["guest_id"], f"{b['booking_code']} confirmed by {h['name']}. Show this ID at the front desk.", "good")
    return {"ok": True}


@router.post("/bookings/{code}/reject")
def reject(code: str, user=Depends(staff), db=Depends(get_db)):
    b = _hotel_booking(db, user, code)
    if b["status"] != "pending":
        raise HTTPException(400, "Only pending requests can be rejected.")
    db.run("UPDATE bookings SET status='rejected' WHERE id=%s", (b["id"],))
    h = db.one("SELECT name FROM hotels WHERE id=%s", (b["hotel_id"],))
    notify(db, b["guest_id"], f"{b['booking_code']} was not accepted by {h['name']}. Try another hotel.", "alert")
    return {"ok": True}


@router.get("/hotels/{hotel_id}/arrival/{code}")
def arrival(hotel_id: int, code: str, user=Depends(staff), db=Depends(get_db)):
    check_hotel(db, user, hotel_id)
    b = db.one(BOOKING_SELECT + "WHERE b.booking_code=%s AND b.hotel_id=%s", (code.strip().upper(), hotel_id))
    if not b or b["status"] == "rejected":
        return {"valid": False}
    return {"valid": True, "booking": booking_public(b)}


@router.post("/bookings/{code}/checkin")
def staff_checkin(code: str, user=Depends(staff), db=Depends(get_db)):
    b = _hotel_booking(db, user, code)
    if b["status"] != "confirmed":
        raise HTTPException(400, "Only confirmed bookings can be checked in.")
    db.run("UPDATE bookings SET status='checked_in' WHERE id=%s", (b["id"],))
    h = db.one("SELECT name FROM hotels WHERE id=%s", (b["hotel_id"],))
    notify(db, b["guest_id"], f"You're checked in at {h['name']}. Open the In-hotel tab for live crowd levels.", "good")
    return {"ok": True}


class CountIn(BaseModel):
    count: int


@router.put("/hotels/{hotel_id}/facilities/{code}")
def update_count(hotel_id: int, code: str, body: CountIn, user=Depends(staff), db=Depends(get_db)):
    check_hotel(db, user, hotel_id)
    f = db.one("SELECT * FROM facilities WHERE hotel_id=%s AND code=%s", (hotel_id, code))
    if not f:
        raise HTTPException(404, "Facility not found.")
    if body.count < 0:
        raise HTTPException(400, "Count cannot be negative.")
    if body.count > f["capacity"]:
        raise HTTPException(400, f"Max is {f['capacity']} (capacity).")
    db.run("UPDATE facilities SET current_count=%s, last_updated=NOW() WHERE id=%s", (body.count, f["id"]))
    return {"ok": True}


@router.post("/hotels/{hotel_id}/queues/{code}/call-next")
def call_next(hotel_id: int, code: str, user=Depends(staff), db=Depends(get_db)):
    check_hotel(db, user, hotel_id)
    f = db.one("SELECT f.id, t.name FROM facilities f JOIN facility_types t ON t.code=f.code "
               "WHERE f.hotel_id=%s AND f.code=%s", (hotel_id, code))
    if not f:
        raise HTTPException(404, "Facility not found.")
    q = db.all("SELECT * FROM queue_tokens WHERE facility_id=%s AND status='waiting' ORDER BY id LIMIT 2", (f["id"],))
    if not q:
        raise HTTPException(400, "No one is waiting.")
    db.run("UPDATE queue_tokens SET status='called' WHERE id=%s", (q[0]["id"],))
    notify(db, q[0]["guest_id"], f"It's your turn at the {f['name']}. Token {q[0]['token_code']}, please go now.", "good")
    if len(q) > 1:
        notify(db, q[1]["guest_id"], f"Your turn at the {f['name']} is coming up. Token {q[1]['token_code']} is next.", "info")
    return {"called": q[0]["token_code"]}


class RoomEdit(BaseModel):
    id: int
    price: int = Field(ge=0)
    avail: int = Field(ge=0)


class FacilityInfo(BaseModel):
    code: str
    open_hours: str = ""
    staff_help: str = ""
    equipment: str = ""
    notes: str = ""


class DetailsIn(BaseModel):
    phone: str = ""
    website: str = ""
    amenities: list[str] = []
    rooms: list[RoomEdit] = []
    facilities: list[FacilityInfo] = []
    parking_watchman: bool | None = None
    parking_cars: int | None = None
    parking_bikes: int | None = None
    wifi_info: str = ""
    photo: str | None = None


@router.put("/hotels/{hotel_id}")
def update_details(hotel_id: int, body: DetailsIn, user=Depends(staff), db=Depends(get_db)):
    h = check_hotel(db, user, hotel_id)
    changes = []
    for r in body.rooms:
        old = db.one("SELECT * FROM rooms WHERE id=%s AND hotel_id=%s", (r.id, hotel_id))
        if not old:
            continue
        if old["price_per_night"] != r.price:
            changes.append(f"{old['room_type']} {old['ac']} price ₹{old['price_per_night']:,} → ₹{r.price:,}")
        if old["rooms_available"] != r.avail:
            changes.append(f"{old['room_type']} rooms available {old['rooms_available']} → {r.avail}")
        db.run("UPDATE rooms SET price_per_night=%s, rooms_available=%s WHERE id=%s", (r.price, r.avail, r.id))
    if body.phone.strip() != (h["phone"] or ""):
        changes.append("Contact number updated")
    if body.website.strip() != (h["website"] or ""):
        changes.append("Website updated")
    db.run("UPDATE hotels SET phone=%s, website=%s WHERE id=%s", (body.phone.strip(), body.website.strip(), hotel_id))
    am = [a for a in body.amenities if a in AMENITIES]
    old_am = sorted(r["amenity"] for r in db.all("SELECT amenity FROM hotel_amenities WHERE hotel_id=%s", (hotel_id,)))
    if sorted(am) != old_am:
        changes.append("Amenities: " + (", ".join(am) or "none"))
        db.run("DELETE FROM hotel_amenities WHERE hotel_id=%s", (hotel_id,))
        db.many("INSERT INTO hotel_amenities (hotel_id, amenity) VALUES (%s,%s)", [(hotel_id, a) for a in am])
        sync_facilities(db, hotel_id, am)
    new_park = (body.parking_watchman, body.parking_cars, body.parking_bikes, body.wifi_info.strip()[:200])
    if new_park != (None if h["parking_watchman"] is None else bool(h["parking_watchman"]), h["parking_cars"], h["parking_bikes"], h["wifi_info"] or ""):
        db.run("UPDATE hotels SET parking_watchman=%s, parking_cars=%s, parking_bikes=%s, wifi_info=%s WHERE id=%s", (*new_park, hotel_id))
        changes.append("Parking / Wi-Fi details updated")
    for f in body.facilities:
        old = db.one("SELECT f.*, t.name FROM facilities f JOIN facility_types t ON t.code=f.code "
                     "WHERE f.hotel_id=%s AND f.code=%s", (hotel_id, f.code))
        if not old:
            continue
        new = (f.open_hours.strip()[:60], f.staff_help.strip()[:200], f.equipment.strip()[:400], f.notes.strip()[:300])
        if new != tuple(old[k] or "" for k in ("open_hours", "staff_help", "equipment", "notes")):
            db.run("UPDATE facilities SET open_hours=%s, staff_help=%s, equipment=%s, notes=%s WHERE id=%s", (*new, old["id"]))
            changes.append(f"{old['name']} details updated")
    if body.photo:
        if not body.photo.startswith("data:image/") or len(body.photo) > 420_000:
            raise HTTPException(400, "Photo must be an image under 300 KB.")
        db.run("UPDATE hotels SET photo=%s WHERE id=%s", (body.photo, hotel_id))
        changes.append("New hotel photo")
    if changes:
        db.run("INSERT INTO hotel_updates (hotel_id, change_text) VALUES (%s,%s)", (hotel_id, "; ".join(changes)[:500]))
    return {"changes": changes}


class NewHotelIn(BaseModel):
    name: str
    district: str
    area: str
    phone: str
    price: int = Field(ge=300)
    rooms: int = Field(ge=1)
    amenities: list[str] = []


@router.post("/hotels")
def register_hotel(body: NewHotelIn, user=Depends(staff), db=Depends(get_db)):
    c = db.one("SELECT AVG(latitude) a, AVG(longitude) b FROM hotels WHERE district=%s", (body.district,))
    if not c or c["a"] is None:
        raise HTTPException(400, "Pick a district from the list.")
    hid = db.run("INSERT INTO hotels (name, district, area, latitude, longitude, phone, source, status) "
                 "VALUES (%s,%s,%s,%s,%s,%s,'owner','pending')",
                 (body.name.strip(), body.district, body.area.strip(), c["a"], c["b"], body.phone.strip()))
    db.run("INSERT INTO rooms (hotel_id, room_type, ac, price_per_night, rooms_available) VALUES (%s,'Standard','AC',%s,%s)",
           (hid, body.price, body.rooms))
    am = [a for a in body.amenities if a in AMENITIES]
    if am:
        db.many("INSERT INTO hotel_amenities (hotel_id, amenity) VALUES (%s,%s)", [(hid, a) for a in am])
    sync_facilities(db, hid, am)
    return {"id": hid}