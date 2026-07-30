# AutoAI API Integration Guide & Contract

This document outlines the API endpoints, request schemas, response shapes, and Axios integration examples for connecting the AutoAI Frontend (Vite/React) with the FastAPI Backend.

---

## 🚀 General Configuration

- **Backend Base URL**: `http://localhost:8000` or `http://127.0.0.1:8000`
- **CORS Configuration**: The backend accepts requests from:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`

---

## 🔐 1. Authentication Endpoints (`/auth`)

These endpoints manage user registration and session initiation.

### **POST /auth/register**
Creates a new user account.

* **Request Body (`UserRegister`):**
  ```json
  {
    "username": "johndoe",
    "email": "johndoe@example.com",
    "password": "securepassword123"
  }
  ```
* **Success Response (200 OK):**
  ```json
  {
    "message": "User Registered Successfully",
    "user": {
      "id": 1,
      "username": "johndoe",
      "email": "johndoe@example.com"
    }
  }
  ```
* **Error Response (200 OK - Validation message):**
  ```json
  {
    "message": "Email already exists"
  }
  ```

---

### **POST /auth/login**
Authenticates a user and returns a JSON Web Token (JWT).

* **Request Body (`UserLogin`):**
  ```json
  {
    "email": "johndoe@example.com",
    "password": "securepassword123"
  }
  ```
* **Success Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "username": "johndoe",
    "email": "johndoe@example.com"
  }
  ```
* **Error Response (200 OK):**
  ```json
  {
    "message": "Invalid Email or Password"
  }
  ```

---

## 🚗 2. Car Catalog Endpoints (`/cars`)

Endpoints for retrieving general car details.

### **GET /cars**
Retrieves the list of all available cars in the database.

* **Response (200 OK):**
  ```json
  [
    {
      "id": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "variant": "SX(O)",
      "ex_showroom_price": 1899000.0,
      "body_type": "SUV",
      "fuel_type": "Petrol",
      "transmission": "Automatic",
      "engine_cc": 1497,
      "power": 115,
      "torque": 144,
      "mileage": 17.4,
      "seating": 5,
      "boot_space": 433,
      "ground_clearance": 190,
      "safety_rating": 5.0,
      "maintenance_cost": 35000,
      "resale_rating": 4.8,
      "city_use": true,
      "highway_use": true,
      "family_friendly": true,
      "pros": "Comfortable, Feature Rich",
      "cons": "Expensive",
      "image_url": "https://..."
    }
  ]
  ```

### **GET /cars/{car_id}**
Retrieves details of a specific car by its database ID.

* **Response (200 OK):**
  Returns the single car object matched by ID.
* **Error Response (200 OK):**
  ```json
  {
    "message": "Car not found"
  }
  ```

---

## 🔍 3. Search Endpoint (`/search`)

Allows users to filter cars based on custom criteria.

### **GET /search**
* **Query Parameters:**
  - `brand` (string, optional) - Case-insensitive partial match
  - `fuel` (string, optional) - Exact match (e.g., `Petrol`, `Diesel`)
  - `transmission` (string, optional) - Exact match (e.g., `Automatic`, `Manual`, `CVT`)
  - `body_type` (string, optional) - Exact match (e.g., `SUV`, `Sedan`, `Hatchback`)
  - `budget` (number, optional) - Ex-showroom price less than or equal to this limit

* **Sample Request URL:**
  `GET http://localhost:8000/search?brand=Hyundai&budget=2000000`
* **Response:**
  A filtered array of car objects.

---

## 💡 4. Recommendation Engine (`/recommend`)

Computes scoring to recommend the top 5 matching cars based on priorities and budget constraints.

### **POST /recommend**
* **Request Body (`RecommendationRequest`):**
  ```json
  {
    "budget": 2000000,
    "fuel_type": "Petrol",
    "transmission": "Automatic",
    "family_members": 5,
    "priority": "safety",
    "body_type": "SUV",
    "city_drive": true,
    "highway_drive": true,
    "maintenance_sensitive": false
  }
  ```
  *(Valid priorities: `"safety"`, `"mileage"`, `"maintenance"`, `"resale"`)*

* **Response (200 OK):**
  ```json
  [
    {
      "id": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "variant": "SX(O)",
      "price": 1899000.0,
      "image": "https://...",
      "fuel_type": "Petrol",
      "transmission": "Automatic",
      "seating_capacity": 5,
      "score": 95.0,
      "reasons": [
        "Within Budget",
        "Preferred Fuel",
        "Preferred Transmission",
        "Preferred Body Type",
        "Enough Seats",
        "Good for City",
        "Good for Highway",
        "Excellent Safety"
      ]
    }
  ]
  ```

---

## 🤖 5. AI Chat Assistant (`/chat`)

Uses natural language processing to extract user preferences and generate tailored advice.

### **POST /chat**
* **Request Body (`ChatRequest`):**
  ```json
  {
    "message": "I want a safe petrol automatic SUV under 15 Lakhs for my family of 4."
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "recommendations": [
      {
        "id": 2,
        "brand": "Tata",
        "model": "Nexon",
        "variant": "Fearless+",
        "price": 1490000.0,
        "image": "https://...",
        "fuel_type": "Petrol",
        "transmission": "Automatic",
        "seating_capacity": 5,
        "score": 90.0,
        "reasons": ["Within Budget", "Preferred Fuel", "Preferred Transmission", "Enough Seats", "Excellent Safety"]
      }
    ],
    "ai_response": "Based on your criteria, I highly recommend the Tata Nexon. It fits perfectly within your budget of 15 Lakhs, comes with an automatic transmission and a highly efficient petrol engine, and has a 5-star safety rating making it extremely secure for your family of 4..."
  }
  ```

---

## ⚖️ 6. Car Comparison Endpoints (`/compare`)

Enables side-by-side spec comparison.

### **GET /compare/cars**
Retrieves high-level details of all cars to populate selection dropdowns in the frontend.

* **Response (200 OK):**
  ```json
  [
    {
      "id": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "variant": "SX(O)"
    }
  ]
  ```

### **POST /compare**
Compares two cars side-by-side.

* **Request Body (`ComparisonRequest`):**
  ```json
  {
    "car1_id": 1,
    "car2_id": 2
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "car1": {
      "id": 1,
      "brand": "Hyundai",
      "model": "Creta",
      "variant": "SX(O)",
      "price": 1899000.0,
      "fuel": "Petrol",
      "transmission": "Automatic",
      "engine_cc": 1497,
      "power": 115,
      "torque": 144,
      "mileage": 17.4,
      "seating": 5,
      "boot_space": 433,
      "ground_clearance": 190,
      "safety_rating": 5.0
    },
    "car2": {
      "id": 2,
      "brand": "Tata",
      "model": "Nexon",
      "variant": "Fearless+",
      "price": 1490000.0,
      "fuel": "Petrol",
      "transmission": "Automatic",
      "engine_cc": 1199,
      "power": 120,
      "torque": 170,
      "mileage": 17.1,
      "seating": 5,
      "boot_space": 382,
      "ground_clearance": 208,
      "safety_rating": 5.0
    }
  }
  ```

---

## ❤️ 7. Wishlist Endpoints (`/wishlist`)

Enables saving cars to a persistent user wishlist.

### **GET /wishlist**
* **Response (200 OK):**
  ```json
  [
    {
      "id": 1,
      "car_id": 2,
      "brand": "Tata",
      "model": "Nexon",
      "variant": "Fearless+",
      "price": 1490000.0,
      "image": "https://..."
    }
  ]
  ```

### **POST /wishlist**
Adds a car to the wishlist.

* **Request Body (`WishlistRequest`):**
  ```json
  {
    "car_id": 2
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "message": "Added Successfully"
  }
  ```
  *(If already added: `{"message": "Already in wishlist"}`)*

### **DELETE /wishlist/{wishlist_item_id}**
Removes a car from the wishlist. Note that this takes the **wishlist item's unique row ID** (returned from `GET /wishlist`), not the `car_id`.

* **Sample Request:**
  `DELETE http://localhost:8000/wishlist/1`
* **Response (200 OK):**
  ```json
  {
    "message": "Removed Successfully"
  }
  ```

---

## 🛠️ 8. Admin Control Endpoints (`/admin`)

Endpoints for administrative tasks like adding/updating the vehicle list.

### **GET /admin/cars**
* **Response (200 OK):** List of all cars.

### **POST /admin/cars**
* **Request Body (`CarCreate`):** Same schema as `Car` properties.
* **Response (200 OK):** The newly created car object.

### **PUT /admin/cars/{car_id}**
* **Request Body (`CarUpdate`):** Updated car details.
* **Response (200 OK):** The updated car object.

### **DELETE /admin/cars/{car_id}**
* **Response (200 OK):** `{"message": "Car deleted successfully"}`

---

## 💻 Frontend Axios Client Template

You can place this setup inside `frontend/src/services/api.js`:

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  }
});

// Request interceptor to automatically attach authorization tokens
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default api;
```
