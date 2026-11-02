"""Creates the stayzen database and loads sample data.

    py seed.py

Loads every hotel and restaurant from database/data/tn_places_all_districts.csv
(collected from OpenStreetMap with the Overpass API). Names, locations, phones and
websites are real. Prices, rooms, crowd counts and reviews are DEMO values.
Running it again wipes the database and starts fresh.
"""
import csv
import os
import random
import zlib

from auth import hash_password
from db import connect
from services.catalog import CAPACITY, FACILITY_TYPES, facility_codes_for

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCHEMA = os.path.join(ROOT, "database", "schema.sql")
CSV_PATH = os.path.join(ROOT, "database", "data", "tn_places_all_districts.csv")
PASSWORD = "demo123"


def h32(text):
    return zlib.crc32(text.encode())


def run_schema(cur):
    sql = open(SCHEMA, encoding="utf-8").read()
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            cur.execute(stmt)


def main():
    conn = connect(with_db=False)
    cur = conn.cursor()
    print("Creating database and tables...")
    run_schema(cur)

    cur.executemany(
        "INSERT INTO facility_types (code, name, name_ta, amenity, grid_col, grid_row, duration_min, directions, directions_ta) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", FACILITY_TYPES)

    def add_hotel(name, district, area, lat, lng, phone, website, stars, source, status, score, rating=None, reviews=0):
        cur.execute("INSERT INTO hotels (name, district, area, latitude, longitude, rating, stars, review_count, phone, "
                    "website, source, status, data_score) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (name, district, area, lat, lng, rating, stars, reviews, phone, website, source, status, score))
        return cur.lastrowid

    def add_facilities(hotel_id, amenities, counts=None, stale=None):
        counts = counts or {}
        rows = []
        for i, code in enumerate(facility_codes_for(amenities)):
            cap = CAPACITY[code]
            n = counts.get(code, round(cap * [0.35, 0.6, 0.4, 0.15, 0.2, 0.3, 0.55][(hotel_id + i) % 7]))
            mins = 26 if code == stale else 1 + i % 4
            rows.append((hotel_id, code, cap, n, mins))
        cur.executemany("INSERT INTO facilities (hotel_id, code, capacity, current_count, last_updated) "
                        "VALUES (%s,%s,%s,%s,NOW() - INTERVAL %s MINUTE)", rows)

    # ---- demo hotel used for the in-hotel walkthrough (clearly labelled as demo) ----
    print("Adding demo hotels...")
    demo_am = ["Gym", "Swimming Pool", "Spa", "Restaurant", "Coffee Lounge", "Garden", "Parking", "Wi-Fi"]
    demo_id = add_hotel("Jasmine Court Hotel", "Madurai", "Town Hall Road", 9.9208, 78.1148, "0452 200 2202", "",
                        0, "demo", "approved", 99, rating=4.4, reviews=365)
    cur.executemany("INSERT INTO hotel_amenities VALUES (%s,%s)", [(demo_id, a) for a in demo_am])
    cur.executemany("INSERT INTO rooms (hotel_id, room_type, ac, price_per_night, rooms_available) VALUES (%s,%s,%s,%s,%s)",
                    [(demo_id, "Standard", "AC", 1900, 5), (demo_id, "Deluxe", "AC", 2600, 3), (demo_id, "Suite", "AC", 4200, 1)])
    cur.execute("UPDATE hotels SET parking_watchman=TRUE, parking_cars=30, parking_bikes=60, "
                "wifi_info='Free high-speed Wi-Fi across the hotel, about 100 Mbps' WHERE id=%s", (demo_id,))
    add_facilities(demo_id, demo_am, {"gym": 18, "spa": 8, "pool": 9, "garden": 4, "reception": 3, "coffee": 2,
                                      "restaurant": 35}, stale="pool")

    demo_details = {
        "gym": ("5:30 AM – 10:00 PM", "Trainer available 6–9 AM and 5–8 PM, free for guests",
                "3 treadmills, 2 exercise cycles, cross-trainer, dumbbells 2–25 kg, bench press, cable machine, yoga mats",
                "Towels and drinking water provided. Gym shoes required."),
        "pool": ("6:00 AM – 9:00 PM", "Lifeguard on duty all day",
                 "25 m outdoor pool, 1.2–1.8 m deep, separate kids pool (0.6 m), changing rooms",
                 "Swimwear required. Please shower before entering."),
        "spa": ("9:00 AM – 9:00 PM", "3 trained therapists",
                "Ayurvedic oil massage, head and shoulder massage, foot reflexology, steam room",
                "Book 30 minutes ahead at Reception."),
        "restaurant": ("7:00 AM – 10:30 PM", "Table service and buffet",
                       "South Indian breakfast buffet, Chettinad specials, North Indian and Chinese à la carte",
                       "Room service available until 11 PM."),
        "coffee": ("6:30 AM – 11:00 PM", "Self-service counter",
                   "Filter coffee, tea, fresh juice, snacks and biscuits",
                   "Free filter coffee for guests from 6:30 to 8:00 AM."),
        "garden": ("Open all day", "Evening walk guide on weekends",
                   "400 m walking path, seating area, kids play corner", "Path lights on after 6:30 PM."),
        "reception": ("24 hours", "Front desk staff speak Tamil, English and Hindi",
                      "Luggage storage, travel desk, doctor on call, currency exchange", ""),
    }
    cur.executemany("UPDATE facilities SET open_hours=%s, staff_help=%s, equipment=%s, notes=%s WHERE hotel_id=%s AND code=%s",
                    [(*v, demo_id, k) for k, v in demo_details.items()])

    pend_id = add_hotel("Anna Nagar Comforts", "Madurai", "Anna Nagar", 9.9281, 78.1482, "0452 200 6606", "",
                        0, "demo", "pending", 0)
    cur.executemany("INSERT INTO hotel_amenities VALUES (%s,%s)", [(pend_id, "Restaurant"), (pend_id, "Wi-Fi")])
    cur.execute("INSERT INTO rooms (hotel_id, room_type, ac, price_per_night, rooms_available) VALUES (%s,'Standard','AC',1500,6)",
                (pend_id,))
    add_facilities(pend_id, ["Restaurant", "Wi-Fi"])

    # ---- sample amenities and facility details for hotels that OpenStreetMap leaves blank ----
    def sample_amenities(am, stars, subtype, k):
        am = list(am)
        def add(a):
            if a not in am:
                am.append(a)
        add("Wi-Fi"); add("Parking")
        if subtype != "guest_house" or k % 2 == 0:
            add("Restaurant")
        if stars >= 3 or k % 3 == 0:
            add("Gym")
        if stars >= 4 or k % 5 == 0:
            add("Swimming Pool")
        if stars >= 4 and k % 2 == 0:
            add("Spa")
        if k % 2 == 0:
            add("Coffee Lounge")
        if k % 4 == 1:
            add("Garden")
        return am

    VARIANTS = {
        "gym": [("6:00 AM – 10:00 PM", "Trainer available 6–9 AM", "Treadmills, exercise cycle, dumbbells 2–20 kg, bench, yoga mats", "Gym shoes required."),
                ("5:30 AM – 9:30 PM", "Trainer on request at Reception", "2 treadmills, cross-trainer, multi-gym machine, free weights", "Towels provided."),
                ("24 hours", "Self-service, staff help on call", "Treadmill, exercise cycle, dumbbells, kettlebells, stretching area", "Guests only. Bring your room key.")],
        "pool": [("6:00 AM – 8:00 PM", "Lifeguard on duty", "Outdoor pool, 1.2–1.5 m deep, kids area, changing rooms", "Swimwear required."),
                 ("7:00 AM – 7:00 PM", "Lifeguard on duty", "Rooftop pool, 1.0–1.6 m deep, sun loungers, showers", "Closed for cleaning 1–2 PM.")],
        "spa": [("10:00 AM – 8:00 PM", "2 trained therapists", "Ayurvedic oil massage, foot reflexology, steam bath", "Book at Reception 30 minutes ahead."),
                ("9:00 AM – 9:00 PM", "3 therapists", "Full body massage, head and shoulder massage, facial", "Prior booking recommended.")],
        "restaurant": [("7:00 AM – 10:30 PM", "Table service", "South Indian breakfast, meals, North Indian and Chinese dishes", "Room service until 10 PM."),
                       ("6:30 AM – 11:00 PM", "Buffet and à la carte", "Breakfast buffet, Chettinad and tandoori specials, fresh juices", "Pure veg section available."),
                       ("7:00 AM – 10:00 PM", "Table service", "Idli, dosa, meals, biryani, parotta, evening snacks", "Parcel available.")],
        "coffee": [("6:30 AM – 10:00 PM", "Counter service", "Filter coffee, tea, juices, snacks", "Free morning coffee for guests."),
                   ("7:00 AM – 11:00 PM", "Self-service", "Coffee, tea, sandwiches, cakes", "")],
        "garden": [("Open all day", "", "Walking path, seating area, kids play corner", "Lights on after 6:30 PM."),
                   ("6:00 AM – 9:00 PM", "", "Lawn, sit-out area, small play area", "")],
        "reception": [("24 hours", "Front desk staff speak Tamil and English", "Luggage storage, travel desk, doctor on call", ""),
                      ("24 hours", "Front desk staff speak Tamil, English and Hindi", "Luggage storage, taxi booking, laundry", "")],
    }

    WIFI = ["Free Wi-Fi in rooms and lobby, about 50 Mbps", "Free Wi-Fi in all rooms, about 30 Mbps",
            "Free Wi-Fi in lobby and restaurant; rooms on request", "Free high-speed Wi-Fi across the hotel, about 100 Mbps"]

    def fill_details(hotel_id, amenities, k):
        rows = []
        for i, code in enumerate(facility_codes_for(amenities)):
            v = VARIANTS[code][(k + i) % len(VARIANTS[code])]
            rows.append((*v, hotel_id, code))
        cur.executemany("UPDATE facilities SET open_hours=%s, staff_help=%s, equipment=%s, notes=%s "
                        "WHERE hotel_id=%s AND code=%s", rows)

    # ---- real places from OpenStreetMap ----
    print("Loading OpenStreetMap places from the CSV...")
    hotels, rest, seen = [], [], set()
    with open(CSV_PATH, encoding="utf-8-sig") as fh:
        for x in csv.DictReader(fh):
            name = x["name"].strip()
            try:
                lat, lng = round(float(x["lat"]), 6), round(float(x["lon"]), 6)
            except ValueError:
                continue
            if not name or (name, lat, lng) in seen:
                continue
            seen.add((name, lat, lng))
            if x["type"] == "hotel":
                hotels.append(x | {"_lat": lat, "_lng": lng, "_name": name})
            else:
                rest.append((name[:160], x["district"], lat, lng, x["cuisine"].replace("_", " ").replace(";", ", ")[:255]))

    by_district = {}
    for x in hotels:
        by_district.setdefault(x["district"], []).append(x)
    verified = set()
    for lst in by_district.values():  # demo: best-documented 2 hotels per district start verified
        for x in sorted(lst, key=lambda r: -int(r["data_score"] or 0))[:2]:
            verified.add(id(x))

    for x in hotels:
        stars = int(x["stars"]) if x["stars"].strip().isdigit() else 0
        am = [a for a, key in (("Swimming Pool", "has_pool"), ("Gym", "has_gym"), ("Spa", "has_spa")) if x[key] == "True"]
        k = h32(x["_name"] + str(x["_lat"]))
        am = sample_amenities(am, stars, x["subtype"], k)
        hid = add_hotel(x["_name"], x["district"], x["street"].strip() or x["district"], x["_lat"], x["_lng"],
                        x["phone"].strip(), x["website"].strip(), stars, "osm",
                        "approved" if id(x) in verified else "listed", int(x["data_score"] or 0))
        if am:
            cur.executemany("INSERT INTO hotel_amenities VALUES (%s,%s)", [(hid, a) for a in am])
        base = {"guest_house": 900, "motel": 1200, "hotel": 1500}.get(x["subtype"], 1400)
        price = round((base + stars * 700 + (k % 7) * 100) / 50) * 50
        cur.executemany("INSERT INTO rooms (hotel_id, room_type, ac, price_per_night, rooms_available) VALUES (%s,%s,%s,%s,%s)",
                        [(hid, "Standard", "AC" if stars >= 3 else "Non-AC", price, 1 + k % 7),
                         (hid, "Deluxe", "AC", round(price * 1.5 / 50) * 50, k % 4)])
        add_facilities(hid, am)
        fill_details(hid, am, k)
        cur.execute("UPDATE hotels SET parking_watchman=%s, parking_cars=%s, parking_bikes=%s, wifi_info=%s WHERE id=%s",
                    (k % 3 != 0, 4 + k % 26, 10 + k % 40, WIFI[k % len(WIFI)], hid))

    cur.executemany("INSERT INTO restaurants (name, district, latitude, longitude, cuisine) VALUES (%s,%s,%s,%s,%s)", rest)

    # ---- users ----
    print("Creating demo accounts...")
    pw = hash_password(PASSWORD)
    cur.executemany("INSERT INTO users (name, email, password_hash, role, hotel_id) VALUES (%s,%s,%s,%s,%s)", [
        ("Demo Guest", "guest@stayzen.demo", pw, "guest", None),
        ("Jasmine Court Manager", "staff@jasminecourt.demo", pw, "staff", demo_id),
        ("Stays Admin", "admin@stayzen.demo", pw, "admin", None),
        ("Earlier Guest", "earlier.guest@stayzen.demo", pw, "guest", None),
    ])
    cur.execute("SELECT id FROM users WHERE email='earlier.guest@stayzen.demo'")
    earlier = cur.fetchone()["id"]

    # ---- other guests already in the gym and spa queues ----
    cur.execute("SELECT id, code FROM facilities WHERE hotel_id=%s AND code IN ('gym','spa')", (demo_id,))
    fac = {r["code"]: r["id"] for r in cur.fetchall()}
    for code, n in (("gym", 3), ("spa", 2)):
        for _ in range(n):
            cur.execute("INSERT INTO queue_tokens (token_code, facility_id) VALUES ('', %s)", (fac[code],))
            cur.execute("UPDATE queue_tokens SET token_code=%s WHERE id=%s", (f"Q-{cur.lastrowid:03d}", cur.lastrowid))

    # ---- past stays with feedback, and pending updates for the admin ----
    for code, r, comment in (("SZ-1043", (5, 4, 5, 5, 4, 4, 4, 5), "The queue token for the gym saved me 20 minutes. I had coffee and came back."),
                             ("SZ-0988", (4, 4, 4, 5, 5, 3, 4, 4), "Directions to the pool could mention the glass door earlier.")):
        cur.execute("INSERT INTO bookings (booking_code, guest_id, hotel_id, room_type, rooms_count, check_in, check_out, nights, "
                    "guests, total_cost, status) VALUES (%s,%s,%s,'Standard AC',1,CURDATE()-INTERVAL 5 DAY,CURDATE()-INTERVAL 3 DAY,2,2,3800,'completed')",
                    (code, earlier, demo_id))
        cur.execute("INSERT INTO feedback (booking_id, hotel_id, overall, clean, facilities, staff, accuracy, nav, crowd, queue, comments) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (cur.lastrowid, demo_id, *r, comment))
    cur.executemany("INSERT INTO hotel_updates (hotel_id, change_text, reviewed, created_at) VALUES (%s,%s,%s,NOW() - INTERVAL %s HOUR)", [
        (demo_id, "Deluxe AC price changed from ₹2,500 to ₹2,600 per night", False, 3),
        (demo_id, "Added Spa opening hours: 9 AM to 9 PM", True, 20),
    ])

    conn.commit()
    cur.execute("SELECT COUNT(*) n FROM hotels")
    nh = cur.fetchone()["n"]
    conn.close()
    print(f"Done. {nh} hotels and {len(rest)} restaurants loaded across {len(by_district)} districts.")
    print(f"Demo password for every account: {PASSWORD}")


if __name__ == "__main__":
    main()