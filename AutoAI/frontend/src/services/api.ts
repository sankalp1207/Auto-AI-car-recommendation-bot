import axios from "axios";

const BACKEND_URL = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: BACKEND_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    }
    return Promise.reject(error);
  }
);

export default api;

export interface Car {
  id: number;
  brand: string;
  model: string;
  variant: string;
  ex_showroom_price: number;
  price?: number;
  starting_price?: number;
  ending_price?: number;
  body_type: string;
  fuel_type: string;
  transmission: string;
  engine_cc: number;
  power: number;
  torque: number;
  mileage: number;
  seating: number;
  boot_space: number;
  ground_clearance: number;
  safety_rating: number;
  maintenance_cost: number;
  resale_rating: number;
  city_use: boolean;
  highway_use: boolean;
  family_friendly: boolean;
  pros: string;
  cons: string;
  image_url: string;
  image?: string;
  status?: string;
}

export interface Recommendation {
  id: number;
  brand: string;
  model: string;
  variant: string;
  price: number;
  starting_price?: number;
  ending_price?: number;
  image: string;
  fuel_type: string;
  transmission: string;
  seating_capacity: number;
  score: number;
  reasons: string[];
  mileage?: number;
  safety_rating?: number;
  engine_cc?: number;
  power?: number;
  torque?: number;
  boot_space?: number;
  ground_clearance?: number;
  airbags?: string;
  sunroof?: boolean;
  adas?: boolean;
  touchscreen_inches?: number;
  carplay_androidauto?: boolean;
  ideal_for?: string;
  summary?: string;
  pros?: string;
  cons?: string;
}

export interface WishlistItem {
  id: number;
  car_id: number;
  brand: string;
  model: string;
  variant: string;
  price: number;
  image: string;
}

export const formatINR = (n: number) => {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
};