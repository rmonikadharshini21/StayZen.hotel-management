"""Shared hotel and booking queries."""
import random

from services.catalog import CAPACITY, facility_codes_for


def marks(n):
    return ",".join(["%s"] * n)


def rooms_and_amenities(db, ids):
    rooms, amen = {}, {}
    if not ids:
        return rooms, amen
    for r in db.all(f"SELECT * FROM rooms WHERE hotel_id IN ({marks(len(ids))}) ORDER BY price_per_night", ids):
        rooms.setdefault(r["hotel_id"], []).append(r)
    for a in db.all(f"SELECT hotel_id, amenity FROM hotel_amenities WHERE hotel_id IN ({marks(len(ids))})", ids):
        amen.setdefault(a["hotel_id"], []).append(a["amenity"])
    return rooms, amen


def hotel_public(h, amenities=None):
    return {
        "id": h["id"], "name": h["name"], "district": h["district"], "area": h["area"],
        "lat": float(h["latitude"]), "lng": float(h["longitude"]),
        "rating": float(h["rating"]) if h["rating"] is not None else None, "stars": h["stars"],
        "reviews": h["review_count"], "phone": h["phone"] or "", "website": h["website"] or "",
        "photo": h.get("photo") or "", "source": h["source"], "status": h["status"],
        "verified": h["status"] == "approved", "amenities": amenities or [],
        "parking": {"watchman": h.get("parking_watchman"), "cars": h.get("parking_cars"), "bikes": h.get("parking_bikes")},
        "wifi_info": h.get("wifi_info") or "",
    }


def booking_public(b):
    return {
        "code": b["booking_code"], "hotel_id": b["hotel_id"], "hotel_name": b.get("hotel_name"),
        "hotel_phone": b.get("hotel_phone") or "", "hotel_website": b.get("hotel_website") or "",
        "lat": float(b["latitude"]) if b.get("latitude") is not None else None,
        "lng": float(b["longitude"]) if b.get("longitude") is not None else None,
        "room_type": b["room_type"], "rooms": b["rooms_count"], "check_in": b["check_in"].isoformat(),
        "check_out": b["check_out"].isoformat(), "nights": b["nights"], "guests": b["guests"],
        "total": b["total_cost"], "status": b["status"], "guest_name": b.get("guest_name"),
        "has_feedback": bool(b.get("has_feedback")),
    }


BOOKING_SELECT = (
    "SELECT b.*, h.name AS hotel_name, h.phone AS hotel_phone, h.website AS hotel_website, "
    "h.latitude, h.longitude, u.name AS guest_name, (f.id IS NOT NULL) AS has_feedback "
    "FROM bookings b JOIN hotels h ON h.id=b.hotel_id JOIN users u ON u.id=b.guest_id "
    "LEFT JOIN feedback f ON f.booking_id=b.id "
)


def new_booking_code(db):
    while True:
        code = f"SZ-{random.randint(1000, 9999)}"
        if not db.one("SELECT id FROM bookings WHERE booking_code=%s", (code,)):
            return code


def sync_facilities(db, hotel_id, amenities):
    """Add facilities for newly listed amenities; keep existing counts."""
    have = {r["code"] for r in db.all("SELECT code FROM facilities WHERE hotel_id=%s", (hotel_id,))}
    want = facility_codes_for(amenities)
    for code in want:
        if code not in have:
            db.run("INSERT INTO facilities (hotel_id, code, capacity, current_count) VALUES (%s,%s,%s,0)",
                   (hotel_id, code, CAPACITY[code]))
    for code in have - set(want):
        db.run("DELETE FROM facilities WHERE hotel_id=%s AND code=%s", (hotel_id, code))


def notify(db, user_id, message, kind="info"):
    if user_id:
        db.run("INSERT INTO notifications (user_id, message, kind) VALUES (%s,%s,%s)", (user_id, message, kind))