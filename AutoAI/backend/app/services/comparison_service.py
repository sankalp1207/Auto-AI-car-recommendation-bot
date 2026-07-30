from app.services.car_data_service import car_data_service
from app.services.llm_services import compare_cars_llm

def compare_cars(request, db=None):
    car1_obj = None
    car2_obj = None

    # Resolve Car 1
    if getattr(request, "car1_id", None) is not None:
        car1_obj = car_data_service.get_car_by_id(request.car1_id)
    elif getattr(request, "model1", None) is not None:
        car1_obj = car_data_service.get_car_by_model(request.model1)
    elif getattr(request, "car1", None) is not None:
        car1_obj = car_data_service.get_car_by_model(request.car1)

    # Resolve Car 2
    if getattr(request, "car2_id", None) is not None:
        car2_obj = car_data_service.get_car_by_id(request.car2_id)
    elif getattr(request, "model2", None) is not None:
        car2_obj = car_data_service.get_car_by_model(request.model2)
    elif getattr(request, "car2", None) is not None:
        car2_obj = car_data_service.get_car_by_model(request.car2)

    if not car1_obj or not car2_obj:
        return None

    try:
        explanation = compare_cars_llm(car1_obj, car2_obj)
    except Exception as e:
        print(f"AI comparison failed: {e}")
        explanation = "AI Comparison currently unavailable."

    return {
        "car1": car1_obj,
        "car2": car2_obj,
        "explanation": explanation
    }