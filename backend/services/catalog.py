"""Fixed lists shared by the seed script and the API."""

AMENITIES = ["Gym", "Swimming Pool", "Spa", "Restaurant", "Coffee Lounge", "Garden", "Parking", "Wi-Fi"]

# code, name, Tamil name, amenity needed, grid col, grid row, typical minutes, directions, Tamil directions
FACILITY_TYPES = [
    ("gym", "Gym", "ஜிம்", "Gym", 0, 0, 45,
     "From Reception, step into the main corridor and turn left. The Gym is the first door on your left.",
     "வரவேற்பிலிருந்து நடைபாதைக்குச் சென்று இடதுபுறம் திரும்புங்கள். இடதுபுறம் முதல் கதவு ஜிம்."),
    ("spa", "Spa", "ஸ்பா", "Spa", 1, 0, 60,
     "Walk into the corridor and keep straight. The Spa is the second door on your left, next to the Gym.",
     "நடைபாதையில் நேராகச் செல்லுங்கள். ஜிம் அருகே இடதுபுறம் இரண்டாவது கதவு ஸ்பா."),
    ("pool", "Swimming Pool", "நீச்சல் குளம்", "Swimming Pool", 2, 0, 30,
     "Walk along the corridor past the Coffee Lounge. Take the glass door on your left to the Pool deck.",
     "காபி லவுஞ்சைக் கடந்து நடைபாதையில் செல்லுங்கள். இடதுபுறம் உள்ள கண்ணாடிக் கதவு வழியாக நீச்சல் குளம்."),
    ("garden", "Garden Walk", "தோட்ட நடை", "Garden", 3, 0, 15,
     "Follow the corridor to the far end. The Garden exit is on your left, after the Pool.",
     "நடைபாதையின் கடைசி வரை செல்லுங்கள். நீச்சல் குளத்திற்குப் பிறகு இடதுபுறம் தோட்டம்."),
    ("reception", "Reception", "வரவேற்பு", None, 0, 1, 5,
     "You are at Reception. All directions start here.",
     "நீங்கள் வரவேற்பில் இருக்கிறீர்கள். எல்லா வழிகளும் இங்கிருந்து தொடங்கும்."),
    ("coffee", "Coffee Lounge", "காபி லவுஞ்ச்", "Coffee Lounge", 1, 1, 10,
     "Right next to Reception. Walk about 20 steps along the corridor; it is on your right.",
     "வரவேற்புக்கு அருகில். நடைபாதையில் சுமார் 20 அடி நடந்தால் வலதுபுறம்."),
    ("restaurant", "Restaurant", "உணவகம்", "Restaurant", 2, 1, 25,
     "Walk along the corridor past the Coffee Lounge. The Restaurant is the next door on your right.",
     "காபி லவுஞ்சைக் கடந்து செல்லுங்கள். வலதுபுறம் அடுத்த கதவு உணவகம்."),
]

CAPACITY = {"gym": 20, "spa": 8, "pool": 25, "garden": 30, "reception": 15, "coffee": 12, "restaurant": 60}


def facility_codes_for(amenities):
    """Reception always exists; other facilities only if the hotel lists that amenity."""
    return [f[0] for f in FACILITY_TYPES if f[3] is None or f[3] in amenities]
