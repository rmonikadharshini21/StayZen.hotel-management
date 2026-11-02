
"""Crowd heat-map logic: occupancy %, level, wait-time range, freshness and suggestions."""
 
STALE_AFTER_MIN = 15
 
 
def pct(count, capacity):
    return round(count / capacity * 100) if capacity else 0
 
 
def level(p):
    if p >= 80:
        return "high"
    if p >= 50:
        return "med"
    return "low"
 
 
def wait_range(p):
    """Always a range, never an exact time, because crowds change minute to minute."""
    if p >= 95:
        return [20, 30]
    if p >= 85:
        return [15, 20]
    if p >= 80:
        return [10, 15]
    return None
 
 
def load_facilities(db, hotel_id, guest_id=None):
    rows = db.all(
        "SELECT f.id, f.code, f.capacity, f.current_count, "
        "TIMESTAMPDIFF(MINUTE, f.last_updated, NOW()) AS mins_ago, "
        "f.open_hours, f.staff_help, f.equipment, f.notes, "
        "t.name, t.name_ta, t.grid_col, t.grid_row, t.duration_min, t.directions, t.directions_ta "
        "FROM facilities f JOIN facility_types t ON t.code = f.code "
        "WHERE f.hotel_id=%s ORDER BY t.grid_row, t.grid_col",
        (hotel_id,),
    )
    queues = {}
    if rows:
        ids = [r["id"] for r in rows]
        marks = ",".join(["%s"] * len(ids))
        for q in db.all(
            f"SELECT id, token_code, facility_id, guest_id FROM queue_tokens "
            f"WHERE status='waiting' AND facility_id IN ({marks}) ORDER BY id",
            ids,
        ):
            queues.setdefault(q["facility_id"], []).append(q)
 
    out = []
    for r in rows:
        p = pct(r["current_count"], r["capacity"])
        q = queues.get(r["id"], [])
        mine = next((i for i, t in enumerate(q) if guest_id and t["guest_id"] == guest_id), None)
        out.append({
            "id": r["id"], "code": r["code"], "name": r["name"], "name_ta": r["name_ta"],
            "col": r["grid_col"], "row": r["grid_row"], "duration": r["duration_min"],
            "directions": r["directions"], "directions_ta": r["directions_ta"],
            "capacity": r["capacity"], "count": r["current_count"], "pct": p, "level": level(p),
            "wait": wait_range(p), "mins_ago": int(r["mins_ago"] or 0),
            "stale": int(r["mins_ago"] or 0) > STALE_AFTER_MIN,
            "queue": [{"token": t["token_code"], "stayzen_guest": t["guest_id"] is not None} for t in q],
            "my_token": q[mine]["token_code"] if mine is not None else None,
            "my_pos": mine + 1 if mine is not None else None,
            "open_hours": r["open_hours"] or "", "staff_help": r["staff_help"] or "",
            "equipment": r["equipment"] or "", "notes": r["notes"] or "",
        })
    for f in out:
        f["suggestions"] = suggestions(out, f["code"]) if f["level"] == "high" else []
    return out
 
 
def suggestions(facilities, target_code):
    """Quiet facilities the guest can visit and still be back before the wait ends."""
    target = next((f for f in facilities if f["code"] == target_code), None)
    if not target:
        return []
    wr = target["wait"] or [5, 10]
    picks = []
    for f in facilities:
        if f["code"] in (target_code, "reception") or f["stale"] or f["level"] != "low" or f["duration"] > wr[1]:
            continue
        steps = abs(f["col"] - target["col"]) + abs(f["row"] - target["row"])
        picks.append((steps, f))
    picks.sort(key=lambda x: x[0])
    return [{"code": f["code"], "name": f["name"], "name_ta": f["name_ta"], "pct": f["pct"], "duration": f["duration"]}
            for _, f in picks[:2]]
 
