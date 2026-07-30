'''
PROG 1: City Latitude and Longitude Lookup
=> For any of your 5 favorite cities of the world, find out the latitude and longitude of each city from google.
=> Create a dictionary where the city is the key and value is a tuple consisting of the latitude and longitude of that city.

=> Develop a program where a city name is entered by an user.
=> If that city exists in the dictionary, it prints the city name and its latitude and longitude, else it shares a suitable message. \
=> While checking the city name, the function ignores the case. This program runs till the user selection is not “exit.
=> City name checking should be a function and return value will be the string to be printed.
'''

# PROG 1: City Latitude and Longitude Lookup

cities = {
    "mumbai": (19.076, 72.8777),
    "bangalore": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "pune": (18.5204, 73.8567),
    "hyderabad": (17.385, 78.4867)
}


def check_city(city_name):
    """Return the coordinates of a city"""
    city_name = city_name.strip().lower()

    if city_name in cities:
        latitude, longitude = cities[city_name]

        return (
            f"{city_name.title()}: Latitude = {latitude}, "
            f"Longitude = {longitude}"
        )

    return "City not found in the dictionary."


print("Cities Dictionary:")
print(cities)

while True:
    city = input("Enter a city name (or type 'exit' to quit): ").strip()

    if city.lower() == "exit":
        print("Exiting the program.")
        break

    print(check_city(city))