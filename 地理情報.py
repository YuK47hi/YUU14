from geopy.geocoders import Nominatim
geolocatior = Nominatim(user_agent="user-id")
location = geolocatior.geocode("東京タワー")
print(location.latitude, location.longitude)
print(location.address)
