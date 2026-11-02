# StayZen

AI-powered Smart Hotel and Resort Management Platform.
Team BYTEBUILDER · JJCET AI-PDLC Hackathon 2026.

Three portals: **Guest**, **Hotel Management** and **Stays Admin**.
Hotel and restaurant data for Tamil Nadu comes from OpenStreetMap (Overpass API), collected by the team.

## Project structure

```
StayZen/
├── backend/                  Python FastAPI server
│   ├── main.py               starts the server and serves the website
│   ├── db.py                 MySQL connection
│   ├── auth.py               password hashing and login sessions
│   ├── seed.py               creates the database and loads all data
│   ├── requirements.txt
│   ├── .env.example          copy to .env and add your MySQL password
│   ├── routes/               API endpoints for each portal
│   │   ├── auth_routes.py    sign in, register, sign out
│   │   ├── guest.py          search, pre-booking, in-hotel, queue tokens, chat, feedback
│   │   ├── staff.py          bookings, head counts, queues, hotel details, registration
│   │   └── admin.py          verification, updates, data freshness, feedback
│   └── services/             the feature logic
│       ├── scoring.py        Best Match Score
│       ├── crowd.py          heat map levels, wait-time ranges, suggestions
│       ├── chatbot.py        English + Tamil assistant (answers only from the database)
│       ├── hotels.py         shared hotel and booking queries
│       └── catalog.py        facility types, directions, amenities
├── database/
│   ├── schema.sql            all MySQL tables
│   └── data/tn_places_all_districts.csv   Overpass export (603 hotels, 714 restaurants)
└── frontend/                 the website
    ├── index.html
    ├── css/style.css
    └── js/
        ├── api.js            talks to the backend
        └── app.js            screens for all three portals
```

## How to run (Windows)

You need **Python** and **MySQL Server** running.

1. **Set your MySQL password**
   In the `backend` folder, copy `.env.example` and rename the copy to `.env`.
   Open `.env` and set `DB_PASSWORD` to your MySQL root password.

2. **Install the Python packages** (open a terminal in the `backend` folder)
   ```
   py -m pip install -r requirements.txt
   ```

3. **Create the database and load the data**
   ```
   py seed.py
   ```
   You should see: `Done. 605 hotels and 713 restaurants loaded...`
   Run it again any time to reset everything for a fresh demo.

4. **Start the server**
   ```
   py -m uvicorn main:app --reload
   ```

5. **Open the website** at **http://127.0.0.1:8000**

API documentation is at http://127.0.0.1:8000/docs (FastAPI makes it automatically).

## Demo logins

Password for every account: `demo123`

| Portal | Email |
|---|---|
| Guest | guest@stayzen.demo |
| Hotel Management | staff@jasminecourt.demo |
| Stays Admin | admin@stayzen.demo |

## Demo flow

1. **Guest**: pick a district (or use GPS), set budget and dates, compare hotels, pre-book. You get a Booking ID.
2. **Hotel Management**: accept the booking, check the ID on arrival, mark checked in, update head counts.
3. **Guest**: In-hotel tab shows the crowd heat map. Tap a busy facility, choose Wait, get a free queue token and a suggestion for the wait.
4. **Hotel Management**: Queues tab, tap Call next. The guest is told their turn is coming up.
5. **Guest**: Ask StayZen in English or Tamil (text, mic or voice replies). Finish trip and give feedback.
6. **Stays Admin**: verify a pending hotel, review updates, see outdated crowd data and feedback.

Short on time? On the guest side, **"Skip ahead: demo stay at Jasmine Court"** creates a checked-in stay.

## What is real and what is demo

- **Real (OpenStreetMap):** hotel and restaurant names, locations, phone numbers, websites, star ratings, pool/gym/spa tags.
- **Demo:** room prices, room counts, crowd counts, guest reviews, and the two "(Demo)" hotels.
- Hotels from OpenStreetMap show as **"Owner not verified"** and cannot be pre-booked until the Stays Admin verifies them. For the demo, the two best-documented hotels in each district start as verified.
- Crowd levels come from head counts typed by hotel staff. No cameras or sensors. With `SIMULATE_CROWD=true`, the demo hotel's counts change slightly every minute so the heat map moves; the pool is left alone so the "may be outdated" warning still shows.
- Missing data is shown as "Not available". The chatbot never guesses; prices are calculated by the server.

## Security notes

- Passwords are hashed with PBKDF2-SHA256 (200,000 rounds, random salt).
- Login tokens are random; only their SHA-256 hash is stored.
- Every API route checks the user's role, so a guest cannot open staff or admin data.
- All SQL uses parameters (no string building with user input).

## Not in this build yet

Real "Continue with Google" login (needs a Google Client ID), online payment, and turn-by-turn indoor maps.
