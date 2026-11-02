"""StayZen assistant. Answers only from the database, in English or Tamil.
If the data is not there, it says it needs confirmation. It never invents prices or offers."""
from services.crowd import load_facilities

ALIAS = {
    "gym": ["gym", "workout", "exercise", "fitness", "ஜிம்", "உடற்பயிற்சி"],
    "spa": ["spa", "massage", "ஸ்பா"],
    "pool": ["pool", "swim", "நீச்சல்"],
    "garden": ["garden", "walk", "தோட்ட"],
    "reception": ["reception", "front desk", "lobby", "வரவேற்பு"],
    "coffee": ["coffee", "tea", "cafe", "lounge", "காபி", "டீ"],
    "restaurant": ["restaurant", "food", "dinner", "lunch", "breakfast", "eat", "உணவ", "சாப்பா"],
}
LEVEL = {"low": "Low", "med": "Medium", "high": "High"}
LEVEL_TA = {"low": "குறைவு", "med": "மிதமான", "high": "அதிகம்"}


def has(text, words):
    return any(w in text for w in words)


def money(n):
    return "₹" + f"{n:,}"


def context_hotel(db, user):
    row = db.one(
        "SELECT h.id, h.name FROM bookings b JOIN hotels h ON h.id=b.hotel_id WHERE b.guest_id=%s "
        "ORDER BY (b.status='checked_in') DESC, b.id DESC LIMIT 1",
        (user["id"],),
    )
    if row:
        return row, ""
    demo = db.one("SELECT id, name FROM hotels WHERE source='demo' AND status='approved' ORDER BY id LIMIT 1")
    return demo, f"(Using {demo['name']} demo data.)\n" if demo else ""


def reply(db, user, message, lang="en"):
    s = message.lower().strip()
    ta = lang == "ta"
    if not s:
        return "கேள்வியை எழுதுங்கள்." if ta else "Type a question to get started."

    if has(s, ["hi", "hello", "vanakkam", "வணக்கம்"]) and len(s) < 14:
        return "வணக்கம்! உங்களுக்கு என்ன உதவி வேண்டும்?" if ta else "Hello! What would you like to know?"

    if has(s, ["emergency", "police", "hospital", "ambulance", "pharmacy", "medical", "fire", "safety",
               "அவசர", "காவல்", "மருத்துவ", "மருந்து"]):
        if ta:
            return ("அவசர எண்கள்: 112 (அனைத்தும்), 100 (காவல்), 108 (ஆம்புலன்ஸ்), 101 (தீயணைப்பு).\n"
                    "அருகிலுள்ள மருத்துவமனை மற்றும் காவல் நிலையத்திற்கு Safety பகுதியில் வழி பார்க்கலாம்.")
        return ("Emergency numbers: 112 (all emergencies), 100 (police), 108 (ambulance), 101 (fire).\n"
                "Open the Safety tab for the nearest police station, hospital and pharmacy with navigation.")

    hotel, note = context_hotel(db, user)
    if not hotel:
        return "இதை உறுதிப்படுத்த வேண்டும்." if ta else "I need to confirm this. Please contact the hotel reception."
    facs = load_facilities(db, hotel["id"], user["id"])
    by_code = {f["code"]: f for f in facs}
    code = next((c for c, words in ALIAS.items() if has(s, words)), None)
    f = by_code.get(code) if code else None

    def nm(f_):
        return f_["name_ta"] if ta else f_["name"]

    if has(s, ["token", "queue", "turn", "டோக்கன்", "வரிசை"]):
        mine = [x for x in facs if x["my_token"]]
        if not mine:
            return ("உங்களிடம் டோக்கன் இல்லை. கூட்டமான வசதியைத் தேர்ந்தெடுத்து டோக்கன் பெறுங்கள்." if ta else
                    "You have no queue token right now. Pick a crowded facility in the In-hotel tab and tap "
                    "\"Get free virtual token\".")
        return "\n".join(
            (f"{nm(x)}: டோக்கன் {x['my_token']}, வரிசையில் {x['my_pos']}வது இடம்." if ta else
             f"{nm(x)}: token {x['my_token']}, position {x['my_pos']} in the queue.") for x in mine)

    if has(s, ["booking", "status of my", "முன்பதிவு"]):
        b = db.one("SELECT b.booking_code, b.status, h.name FROM bookings b JOIN hotels h ON h.id=b.hotel_id "
                   "WHERE b.guest_id=%s ORDER BY b.id DESC LIMIT 1", (user["id"],))
        if not b:
            return "உங்களுக்கு முன்பதிவு எதுவும் இல்லை." if ta else "You have no bookings yet. Search hotels and tap Pre-book."
        status = b["status"].replace("_", " ")
        return (f"உங்கள் முன்பதிவு {b['booking_code']}: நிலை {status}." if ta else
                f"Your booking {b['booking_code']} at {b['name']} is {status}.")

    if has(s, ["price", "cost", "rent", "tariff", "how much", "விலை", "கட்டணம்"]):
        rooms = db.all("SELECT room_type, ac, price_per_night FROM rooms WHERE hotel_id=%s ORDER BY price_per_night",
                       (hotel["id"],))
        if not rooms:
            return note + ("விலை தகவல் இல்லை. ஹோட்டலை தொடர்பு கொள்ளவும்." if ta else
                           "Room prices are not available. Please contact the hotel.")
        head = f"{hotel['name']} அறை விலை (ஒரு இரவுக்கு):\n" if ta else f"Room prices at {hotel['name']} (per night, demo data):\n"
        lines = "\n".join(f"{r['room_type']} {r['ac']}: {money(r['price_per_night'])}" for r in rooms)
        tail = "\nமொத்த விலையை கணினி கணக்கிடும்." if ta else "\nThe total for your dates is calculated when you pre-book."
        return note + head + lines + tail

    if f and has(s, ["where", "how do i", "how to", "direction", "way", "route", "reach", "get to", "go to",
                     "எங்கே", "எப்படி", "வழி"]):
        return note + (f"{nm(f)} செல்லும் வழி: {f['directions_ta']}" if ta else f"To the {nm(f)}: {f['directions']}")

    if has(s, ["suggest", "while i wait", "what can i do", "bored", "free time", "idea",
               "பரிந்துரை", "என்ன செய்ய", "காத்திருக்கும்"]):
        target = f or next((x for x in facs if x["my_token"]), None) or next((x for x in facs if x["level"] == "high"), None)
        picks = target["suggestions"] if target and target["suggestions"] else \
            [{"name": x["name"], "name_ta": x["name_ta"], "pct": x["pct"], "duration": x["duration"]}
             for x in facs if x["level"] == "low" and x["code"] != "reception" and not x["stale"]][:2]
        if not picks:
            return "இப்போது அமைதியான வசதி எதுவும் இல்லை." if ta else "Nothing is quiet enough to suggest right now. Check again in a few minutes."
        out = []
        for p in picks:
            if ta:
                out.append(f"{p['name_ta']} இப்போது அமைதியாக உள்ளது ({p['pct']}%). சுமார் {p['duration']} நிமிடம் செலவிடலாம்.")
            else:
                back = f", so you'll be back for the {target['name']} in time" if target else ""
                out.append(f"{p['name']} is quiet now ({p['pct']}%). It takes about {p['duration']} min{back}.")
        return note + "\n".join(out)

    if has(s, ["amenit", "facilit", "what does", "what is there", "வசதி"]):
        am = [r["amenity"] for r in db.all("SELECT amenity FROM hotel_amenities WHERE hotel_id=%s", (hotel["id"],))]
        if not am:
            return note + ("வசதி தகவல் இல்லை." if ta else f"{hotel['name']} has not listed its amenities yet.")
        return note + (f"{hotel['name']} வசதிகள்: " if ta else f"{hotel['name']} has: ") + ", ".join(am) + "."

    if f:
        old = (" இந்த தகவல் பழையதாக இருக்கலாம்." if ta else " This data may be outdated.") if f["stale"] else ""
        if ta:
            w = f"காத்திருப்பு சுமார் {f['wait'][0]}–{f['wait'][1]} நிமிடம்." if f["wait"] else "இப்போது செல்லலாம்."
            return note + f"{nm(f)}: கூட்டம் {LEVEL_TA[f['level']]} ({f['pct']}%). {w} கடைசி புதுப்பிப்பு {f['mins_ago']} நிமிடங்களுக்கு முன்.{old}"
        w = (f"Expect a wait of about {f['wait'][0]}–{f['wait'][1]} min. You can get a free queue token."
             if f["wait"] else "You can go now.")
        return note + (f"{nm(f)}: {LEVEL[f['level']]} crowd ({f['pct']}%, {f['count']} of {f['capacity']} people). "
                       f"{w} Updated {f['mins_ago']} min ago.{old}")

    if code and not f:
        return (f"இந்த ஹோட்டலில் அந்த வசதி இல்லை." if ta else f"{hotel['name']} does not list that facility.")

    return ("இதை உறுதிப்படுத்த வேண்டும். ஹோட்டல் வரவேற்பை தொடர்பு கொள்ளவும்." if ta else
            "I need to confirm this. Please contact the hotel reception.")
