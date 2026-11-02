"""Sign in, register, sign out, and static lists the frontend needs."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import create_session, current_user, end_session, hash_password, verify_password
from db import get_db
from services.catalog import AMENITIES
from services.hotels import sync_facilities

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    email: str
    password: str
    role: str


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


def _user_out(u, token):
    return {"token": token, "user": {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
                                     "hotel_id": u["hotel_id"]}}


@router.post("/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    u = db.one("SELECT * FROM users WHERE email=%s AND role=%s", (body.email.strip().lower(), body.role))
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return _user_out(u, create_session(db, u["id"]))


@router.post("/auth/register")
def register(body: RegisterIn, db=Depends(get_db)):
    email = body.email.strip().lower()
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if not body.name.strip() or "@" not in email:
        raise HTTPException(400, "Enter your name and a valid email.")
    if db.one("SELECT id FROM users WHERE email=%s", (email,)):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    uid = db.run("INSERT INTO users (name, email, password_hash, role) VALUES (%s,%s,%s,'guest')",
                 (body.name.strip(), email, hash_password(body.password)))
    u = db.one("SELECT * FROM users WHERE id=%s", (uid,))
    return _user_out(u, create_session(db, uid))


class HotelSignupIn(BaseModel):
    name: str
    email: str
    password: str
    hotel_name: str
    district: str
    area: str
    phone: str
    price: int
    rooms: int
    amenities: list[str] = []


@router.post("/auth/register-hotel")
def register_hotel(body: HotelSignupIn, db=Depends(get_db)):
    """New hotel manager account plus their hotel, which waits for Stays Admin verification."""
    email = body.email.strip().lower()
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if not body.name.strip() or "@" not in email or not body.hotel_name.strip():
        raise HTTPException(400, "Fill in your name, email and hotel name.")
    if body.price < 300 or body.rooms < 1:
        raise HTTPException(400, "Enter a room price of at least ₹300 and at least 1 room.")
    if db.one("SELECT id FROM users WHERE email=%s", (email,)):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    c = db.one("SELECT AVG(latitude) a, AVG(longitude) b FROM hotels WHERE district=%s", (body.district,))
    if not c or c["a"] is None:
        raise HTTPException(400, "Pick a district from the list.")
    hid = db.run("INSERT INTO hotels (name, district, area, latitude, longitude, phone, source, status) "
                 "VALUES (%s,%s,%s,%s,%s,%s,'owner','pending')",
                 (body.hotel_name.strip(), body.district, body.area.strip(), c["a"], c["b"], body.phone.strip()))
    db.run("INSERT INTO rooms (hotel_id, room_type, ac, price_per_night, rooms_available) VALUES (%s,'Standard','AC',%s,%s)",
           (hid, body.price, body.rooms))
    am = [a for a in body.amenities if a in AMENITIES]
    if am:
        db.many("INSERT INTO hotel_amenities (hotel_id, amenity) VALUES (%s,%s)", [(hid, a) for a in am])
    sync_facilities(db, hid, am)
    uid = db.run("INSERT INTO users (name, email, password_hash, role, hotel_id) VALUES (%s,%s,%s,'staff',%s)",
                 (body.name.strip(), email, hash_password(body.password), hid))
    u = db.one("SELECT * FROM users WHERE id=%s", (uid,))
    return _user_out(u, create_session(db, uid))


@router.post("/auth/logout")
def logout(user=Depends(current_user), db=Depends(get_db)):
    end_session(db, user["token"])
    return {"ok": True}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return {k: user[k] for k in ("id", "name", "email", "role", "hotel_id")}


@router.get("/meta")
def meta(db=Depends(get_db)):
    districts = db.all(
        "SELECT district AS name, AVG(latitude) AS lat, AVG(longitude) AS lng, COUNT(*) AS hotels "
        "FROM hotels WHERE status IN ('approved','listed') GROUP BY district ORDER BY district")
    return {
        "districts": [{"name": d["name"], "lat": float(d["lat"]), "lng": float(d["lng"]), "hotels": d["hotels"]}
                      for d in districts],
        "amenities": AMENITIES,
    }