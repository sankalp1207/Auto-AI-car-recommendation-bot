import time
import httpx
from typing import Dict, List, Any, Optional
from .config import BACKEND_URL
from .logger import log_activity

async def make_request(
    method: str,
    path: str,
    user_id: int | str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any] | List[Any]:
    """
    Generic asynchronous request runner that measures backend response time and logs activities.
    """
    url = f"{BACKEND_URL.rstrip('/')}/{path.lstrip('/')}"
    start_time = time.perf_counter()
    
    # Clean params to remove None values
    if params:
        params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, json=json_data, params=params, headers=headers)
            elif method.upper() == "DELETE":
                response = await client.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            
            # Log response and response time
            log_activity(user_id, f"{method} {path} - Status {response.status_code}", response_time_ms=elapsed_ms)
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log_activity(user_id, f"{method} {path} - HTTP Error {e.response.status_code}", response_time_ms=elapsed_ms, error=e)
            raise e
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log_activity(user_id, f"{method} {path} - Request Failed", response_time_ms=elapsed_ms, error=e)
            raise e

async def sync_user(telegram_id: int) -> Dict[str, Any]:
    """
    Registers the telegram user. If already exists, logs the user in.
    Returns registration/login info containing username, email, and access_token.
    """
    username = f"telegram_{telegram_id}"
    email = f"telegram_{telegram_id}@telegram.com"
    password = f"telegram_{telegram_id}_secret"
    
    # Try registration first
    try:
        register_payload = {
            "username": username,
            "email": email,
            "password": password
        }
        res = await make_request("POST", "/auth/register", telegram_id, json_data=register_payload)
        # Registration success, now login to get token
        login_payload = {
            "email": email,
            "password": password
        }
        login_res = await make_request("POST", "/auth/login", telegram_id, json_data=login_payload)
        # Insert database ID if decoded or present
        return login_res
    except Exception as e:
        # If registration failed (e.g. user already exists), log in
        login_payload = {
            "email": email,
            "password": password
        }
        return await make_request("POST", "/auth/login", telegram_id, json_data=login_payload)

async def recommend(
    user_id: int | str,
    budget: int,
    fuel_type: str,
    transmission: str,
    family_members: int,
    body_type: Optional[str] = None,
    city_drive: bool = True,
    highway_drive: bool = False,
    priority: str = "mileage",
    maintenance_sensitive: bool = False
) -> List[Dict[str, Any]]:
    """
    Call the recommendation API `/recommend/`.
    """
    payload = {
        "budget": budget,
        "fuel_type": fuel_type,
        "transmission": transmission,
        "family_members": family_members,
        "priority": priority,
        "body_type": body_type,
        "city_drive": city_drive,
        "highway_drive": highway_drive,
        "maintenance_sensitive": maintenance_sensitive
    }
    return await make_request("POST", "/recommend/", user_id, json_data=payload)

async def search(user_id: int | str, query_str: str) -> List[Dict[str, Any]]:
    """
    Call the general car search endpoint `/admin/cars/search` which matches brand, model, and variant.
    """
    params = {"query": query_str}
    return await make_request("GET", "/admin/cars/search", user_id, params=params)

async def chat(user_id: int | str, message: str, session_id: str) -> Dict[str, Any]:
    """
    Call the AI chat endpoint `/chat/`.
    """
    payload = {
        "message": message,
        "session_id": session_id
    }
    return await make_request("POST", "/chat/", user_id, json_data=payload)

async def get_wishlist(user_id: int | str) -> List[Dict[str, Any]]:
    """
    Call the wishlist fetch API `/wishlist/`.
    """
    return await make_request("GET", "/wishlist/", user_id)

async def add_to_wishlist(user_id: int | str, car_id: int) -> Dict[str, Any]:
    """
    Call the add-to-wishlist API `/wishlist/`.
    """
    payload = {"car_id": car_id}
    return await make_request("POST", "/wishlist/", user_id, json_data=payload)

async def remove_from_wishlist(user_id: int | str, wishlist_id: int) -> Dict[str, Any]:
    """
    Call the delete-from-wishlist API `/wishlist/{id}`.
    """
    return await make_request("DELETE", f"/wishlist/{wishlist_id}", user_id)

async def compare_cars(user_id: int | str, car1: str, car2: str) -> Dict[str, Any]:
    """
    Call the compare cars API `/compare/` using car model/brand names.
    """
    params = {"car1": car1, "car2": car2}
    return await make_request("GET", "/compare/", user_id, params=params)

async def get_favorites(user_id: int | str, db_user_id: int) -> List[Dict[str, Any]]:
    """
    Call the favorites fetch API `/favorites/{user_id}`.
    """
    return await make_request("GET", f"/favorites/{db_user_id}", user_id)

async def add_favorite(user_id: int | str, db_user_id: int, car_id: int) -> Dict[str, Any]:
    """
    Call the add favorite API `/favorites/`.
    """
    params = {"user_id": db_user_id, "car_id": car_id}
    return await make_request("POST", "/favorites/", user_id, params=params)

async def delete_favorite(user_id: int | str, db_user_id: int, car_id: int) -> Dict[str, Any]:
    """
    Call the delete favorite API `/favorites/`.
    """
    params = {"user_id": db_user_id, "car_id": car_id}
    return await make_request("DELETE", "/favorites/", user_id, params=params)
