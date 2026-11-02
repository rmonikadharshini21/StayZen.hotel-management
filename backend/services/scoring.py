"""Best Match Score and hotel search.

Score out of 100 = budget fit 40 + rating 25 + distance 20 + facilities 15.
If a hotel has no rating, it gets a neutral 12.5 for rating instead of 0.
"""
import math
from datetime import date


def distance_km(a, b):
    r = 6371
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def nights_between(check_in: date, check_out: date):
    return (check_out - check_in).days


def rooms_needed(guests):
    return max(1, math.ceil(guests / 2))  # max 2 guests per room


def pick_room(rooms, budget, need):
    ok = [r for r in rooms if r["rooms_available"] >= need]
    if not ok:
        return None
    under = sorted([r for r in ok if r["price_per_night"] <= budget], key=lambda r: -r["price_per_night"])
    return under[0] if under else min(ok, key=lambda r: r["price_per_night"])


def evaluate(hotel, rooms, amenities, origin, budget, guests, nights, wants):
    need = rooms_needed(guests)
    room = pick_room(rooms, budget, need)
    d = distance_km(origin, (float(hotel["latitude"]), float(hotel["longitude"])))

    if room:
        price = room["price_per_night"]
        budget_pts = 40 if price <= budget else max(0, 40 * (1 - (price - budget) / budget))
    else:
        budget_pts = 0
    if hotel["rating"]:
        rating_pts = float(hotel["rating"]) / 5 * 25
    elif hotel["stars"]:
        rating_pts = hotel["stars"] / 5 * 25
    else:
        rating_pts = 12.5
    distance_pts = max(0, 1 - d / 20) * 20
    hits = [w for w in wants if w in amenities]
    fac_pts = (len(hits) / len(wants) * 15) if wants else min(1, len(amenities) / 6) * 15
    score = round(budget_pts + rating_pts + distance_pts + fac_pts)

    return {
        "room": {"id": room["id"], "type": room["room_type"], "ac": room["ac"], "price": room["price_per_night"],
                 "avail": room["rooms_available"]} if room else None,
        "distance_km": round(d, 1),
        "rooms_needed": need,
        "nights": nights,
        "total": room["price_per_night"] * nights * need if room else None,
        "over_budget": bool(room and room["price_per_night"] > budget),
        "hits": hits,
        "score": score,
        "parts": {"budget": round(budget_pts), "rating": round(rating_pts), "distance": round(distance_pts),
                  "facilities": round(fac_pts)},
    }
