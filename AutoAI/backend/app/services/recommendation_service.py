from app.services.car_data_service import car_data_service

def recommend_cars(request, db=None):
    return car_data_service.recommend_cars(request)