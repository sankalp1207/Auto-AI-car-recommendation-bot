from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

def explain_car(car, user_preferences):

    prompt = f"""
You are an expert automobile advisor.

User Preferences:
{user_preferences}

Recommended Car:

Brand: {car.brand}
Model: {car.model}
Variant: {car.variant}
Price: {car.ex_showroom_price}
Fuel: {car.fuel_type}
Transmission: {car.transmission}
Mileage: {car.mileage}
Power: {car.power}
Safety: {car.safety_rating}
Maintenance Cost: {car.maintenance_cost}
Resale Rating: {car.resale_rating}

Explain in simple English:

1. Why this car matches.
2. Pros.
3. Cons.
4. Who should buy it.

Maximum 150 words.
"""

    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content