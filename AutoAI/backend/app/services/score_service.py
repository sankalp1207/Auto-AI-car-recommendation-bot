def calculate_match_score(car, prefs):

    score = 0

    breakdown = {}

    # Budget
    if car.ex_showroom_price <= prefs["budget"]:
        score += 25
        breakdown["Budget"] = 25
    else:
        breakdown["Budget"] = 0

    # Fuel
    if prefs["fuel_type"]:

        if car.fuel_type.lower() == prefs["fuel_type"].lower():

            score += 15
            breakdown["Fuel"] = 15
        else:
            breakdown["Fuel"] = 0

    # Transmission
    if prefs["transmission"]:

        if car.transmission.lower() == prefs["transmission"].lower():

            score += 15
            breakdown["Transmission"] = 15
        else:
            breakdown["Transmission"] = 0

    # Safety

    safety = min(car.safety_rating * 4, 20)

    score += safety

    breakdown["Safety"] = safety

    # Seating

    if car.seating >= prefs["family_members"]:

        score += 10
        breakdown["Family"] = 10
    else:
        breakdown["Family"] = 0

    # Mileage

    mileage = min(car.mileage, 15)

    score += mileage

    breakdown["Mileage"] = mileage

    return score, breakdown