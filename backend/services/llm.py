"""AI chat for the StayZen assistant.

Uses Google Gemini (GEMINI_API_KEY) or Anthropic Claude (ANTHROPIC_API_KEY) from backend/.env.
The model gets the guest's live StayZen data as context, so it can chat normally and still
answer hotel questions from real records. If no key is set or the call fails, the caller
falls back to the built-in rule-based answers.
"""
import json
import os
import urllib.error
import urllib.request

from services.crowd import load_facilities

RULES = """You are the StayZen assistant inside the StayZen hotel website (Tamil Nadu, India).
You can chat normally and help with anything the guest asks, like a friendly general assistant.
For anything about hotels, bookings, prices, crowds, facilities or this website, use ONLY the
STAYZEN DATA below. If the data does not have the answer, say you need to confirm it and suggest
contacting the hotel. Never invent prices, offers, room availability, booking IDs or crowd numbers.
Prices are calculated by StayZen; quote them exactly as given.
Crowd levels: Low under 50%, Medium 50-79%, High 80% or more. Give wait times as ranges.
Emergency numbers in India: 112 (all), 100 (police), 108 (ambulance), 101 (fire).
Keep answers short and clear (2-5 sentences unless the guest asks for more). Use plain text, no markdown tables.

How the website works (use this to guide guests):
- Find hotels: choose district or use my location, budget, guests, dates, facilities, then Find hotels.
  Hotels are ranked by Best Match Score (budget 40, rating 25, distance 20, facilities 15).
  Click a hotel to see rooms, facilities, parking, Wi-Fi, food nearby, Route and Pre-book. Compare up to 3 hotels.
- Pre-book: no payment online. The guest gets a Booking ID like SZ-1234. The hotel accepts or rejects it.
- Crowd map tab: enter the Booking ID to see the live crowd heat map of that hotel.
  After check-in, the guest can get a free virtual queue token for a crowded facility and gets suggestions for the wait.
- My bookings: status, check-in, Finish trip, then feedback.
- Safety tab: emergency numbers and nearest police, hospital, pharmacy with navigation.
"""


def _context(db, user, message):
    lines = [f"Guest name: {user['name']}"]
    bookings = db.all(
        "SELECT b.booking_code, b.status, b.check_in, b.check_out, b.nights, b.guests, b.total_cost, b.room_type, "
        "h.id AS hotel_id, h.name FROM bookings b JOIN hotels h ON h.id=b.hotel_id WHERE b.guest_id=%s "
        "ORDER BY (b.status='checked_in') DESC, b.id DESC LIMIT 5", (user["id"],))
    if bookings:
        lines.append("Guest's bookings:")
        for b in bookings:
            lines.append(f"- {b['booking_code']} at {b['name']}: {b['status'].replace('_', ' ')}, {b['check_in']} to "
                         f"{b['check_out']} ({b['nights']} nights), {b['guests']} guests, {b['room_type']}, total ₹{b['total_cost']:,}")
        hid = bookings[0]["hotel_id"]
        h = db.one("SELECT * FROM hotels WHERE id=%s", (hid,))
        lines.append(f"\nCurrent hotel: {h['name']}, {h['area']}, {h['district']}. Phone: {h['phone'] or 'not available'}. "
                     f"Website: {h['website'] or 'not available'}.")
        am = [r["amenity"] for r in db.all("SELECT amenity FROM hotel_amenities WHERE hotel_id=%s", (hid,))]
        lines.append("Amenities: " + (", ".join(am) or "not listed"))
        if h.get("parking_cars") is not None or h.get("parking_watchman") is not None:
            lines.append(f"Parking: watchman {'available' if h.get('parking_watchman') else 'not available'}, "
                         f"{h.get('parking_cars')} car slots, {h.get('parking_bikes')} bike slots.")
        if h.get("wifi_info"):
            lines.append("Wi-Fi: " + h["wifi_info"])
        rooms = db.all("SELECT room_type, ac, price_per_night, rooms_available FROM rooms WHERE hotel_id=%s", (hid,))
        lines.append("Rooms: " + "; ".join(f"{r['room_type']} {r['ac']} ₹{r['price_per_night']:,}/night, {r['rooms_available']} left" for r in rooms))
        lines.append("Facilities right now:")
        for f in load_facilities(db, hid, user["id"]):
            wait = f" wait {f['wait'][0]}-{f['wait'][1]} min" if f["wait"] else ""
            token = f" guest's token {f['my_token']} position {f['my_pos']}" if f["my_token"] else ""
            old = " (data may be outdated)" if f["stale"] else ""
            extra = "; ".join(x for x in (f["open_hours"] and "open " + f["open_hours"], f["staff_help"], f["equipment"], f["notes"]) if x)
            lines.append(f"- {f['name']}: {f['pct']}% ({f['count']}/{f['capacity']}), {f['level']}{wait}{token}{old}, "
                         f"updated {f['mins_ago']} min ago. Directions from Reception: {f['directions']} {extra}")
    else:
        lines.append("The guest has no bookings yet.")

    # If the guest names a district, add its best verified hotels.
    text = message.lower()
    for d in db.all("SELECT DISTINCT district FROM hotels"):
        if d["district"].lower() in text:
            rows = db.all("SELECT h.name, h.area, MIN(r.price_per_night) p FROM hotels h JOIN rooms r ON r.hotel_id=h.id "
                          "WHERE h.district=%s AND h.status='approved' GROUP BY h.id ORDER BY p LIMIT 6", (d["district"],))
            if rows:
                lines.append(f"\nVerified hotels in {d['district']} (bookable): " +
                             "; ".join(f"{r['name']} ({r['area']}) from ₹{r['p']:,}/night" for r in rows))
            break
    return "\n".join(lines)


def _post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def ask_ai(db, user, message, lang, history):
    """Returns the AI reply, or None if no AI is configured or the call fails."""
    gem, ant = os.getenv("GEMINI_API_KEY", "").strip(), os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not gem and not ant:
        return None
    system = RULES + ("\nReply in Tamil (தமிழ்)." if lang == "ta" else "\nReply in the language the guest uses.") \
        + "\n\nSTAYZEN DATA:\n" + _context(db, user, message)
    turns = [h for h in (history or [])[-10:] if h.get("text")]
    try:
        if gem:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            contents = [{"role": "user" if t["who"] == "me" else "model", "parts": [{"text": t["text"]}]} for t in turns]
            contents.append({"role": "user", "parts": [{"text": message}]})
            data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                         {"x-goog-api-key": gem},
                         {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
                          "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600}})
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip() or None
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
        msgs = [{"role": "user" if t["who"] == "me" else "assistant", "content": t["text"]} for t in turns]
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        msgs.append({"role": "user", "content": message})
        data = _post("https://api.anthropic.com/v1/messages",
                     {"x-api-key": ant, "anthropic-version": "2023-06-01"},
                     {"model": model, "max_tokens": 600, "system": system, "messages": msgs})
        return "".join(b.get("text", "") for b in data["content"]).strip() or None
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as exc:
        print("AI chat unavailable, using built-in answers:", exc)
        return None