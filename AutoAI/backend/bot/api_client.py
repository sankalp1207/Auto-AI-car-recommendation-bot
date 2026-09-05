import logging
from typing import Any, Dict, List, Optional
import httpx

from bot.config import BACKEND_URL

logger = logging.getLogger("AutoAIBot.APIClient")


class AutoAIAPIClient:
    """Async client to communicate with the AutoAI FastAPI backend."""

    def __init__(self, base_url: str = BACKEND_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                logger.error(f"Cannot connect to AutoAI backend at {self.base_url}")
                raise RuntimeError("AutoAI backend server is currently unreachable.")
            except httpx.TimeoutException:
                logger.error(f"Timeout while requesting {url}")
                raise RuntimeError("AutoAI backend request timed out. Please try again.")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
                raise RuntimeError(f"Backend returned status {e.response.status_code}.")

    async def _post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=json_data, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                logger.error(f"Cannot connect to AutoAI backend at {self.base_url}")
                raise RuntimeError("AutoAI backend server is currently unreachable.")
            except httpx.TimeoutException:
                logger.error(f"Timeout while requesting {url}")
                raise RuntimeError("AutoAI backend request timed out. Please try again.")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
                raise RuntimeError(f"Backend returned status {e.response.status_code}.")

    async def _delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.delete(url, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                logger.error(f"Cannot connect to AutoAI backend at {self.base_url}")
                raise RuntimeError("AutoAI backend server is currently unreachable.")
            except httpx.TimeoutException:
                logger.error(f"Timeout while requesting {url}")
                raise RuntimeError("AutoAI backend request timed out. Please try again.")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
                raise RuntimeError(f"Backend returned status {e.response.status_code}.")

    async def check_health(self) -> Dict[str, Any]:
        """Check if FastAPI backend is online."""
        return await self._get("/")

    async def get_all_cars(self) -> List[Dict[str, Any]]:
        """Retrieve all cars from the catalog."""
        result = await self._get("/cars/")
        return result or []

    async def get_car(self, model_or_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific car by ID or model name."""
        return await self._get(f"/cars/{model_or_id}")

    async def search_cars(self, **kwargs) -> List[Dict[str, Any]]:
        """Search cars with filter query parameters."""
        clean_params = {k: v for k, v in kwargs.items() if v is not None}
        result = await self._get("/search/", params=clean_params)
        return result or []

    async def recommend_cars(self, preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get car recommendations based on criteria."""
        result = await self._post("/recommend/", json_data=preferences)
        return result or []

    async def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send message to AI chat assistant."""
        payload = {"message": message, "session_id": session_id}
        result = await self._post("/chat/", json_data=payload)
        return result or {"recommendations": [], "ai_response": "Sorry, I could not process your message."}

    async def compare_cars(self, car1: str, car2: str) -> Optional[Dict[str, Any]]:
        """Compare two cars by name."""
        return await self._get("/compare/", params={"car1": car1, "car2": car2})

    async def get_wishlist(self) -> List[Dict[str, Any]]:
        """Get all wishlist items."""
        result = await self._get("/wishlist/")
        return result or []

    async def add_to_wishlist(self, car_id: int) -> Dict[str, Any]:
        """Add a car to wishlist."""
        return await self._post("/wishlist/", json_data={"car_id": car_id})

    async def remove_from_wishlist(self, wishlist_id: int) -> Dict[str, Any]:
        """Remove an item from wishlist by wishlist item ID."""
        return await self._delete(f"/wishlist/{wishlist_id}")

    async def get_favorites(self, user_id: int) -> List[Dict[str, Any]]:
        """Get favorites for a specific user ID."""
        result = await self._get(f"/favorites/{user_id}")
        return result or []

    async def add_favorite(self, user_id: int, car_id: int) -> Dict[str, Any]:
        """Add a car to user's favorites."""
        return await self._post("/favorites/", params={"user_id": user_id, "car_id": car_id})

    async def delete_favorite(self, user_id: int, car_id: int) -> Dict[str, Any]:
        """Remove a car from user's favorites."""
        return await self._delete("/favorites/", params={"user_id": user_id, "car_id": car_id})


api_client = AutoAIAPIClient()
