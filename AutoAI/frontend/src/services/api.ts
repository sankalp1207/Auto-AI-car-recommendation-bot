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
  if (!n || isNaN(n)) return "Price on Request";
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
};

export interface LaunchVehicle {
  id: string;
  brand: string;
  model: string;
  variant?: string;
  price?: number;
  fuel_type?: string;
  transmission?: string;
  body_type?: string;
  engine_cc?: number;
  power?: number;
  torque?: number;
  mileage?: number;
  seating?: number;
  boot_space?: number;
  ground_clearance?: number;
  safety_rating?: number;
  battery_capacity?: number;
  range_km?: number;
  status: string;
  source: string;
  model_url?: string;
  variant_url?: string;
  launch_date?: string;
  launch_date_type?: string;
  launch_evidence_url?: string;
  record_type?: string;
  data_quality_status?: string;
  discovered_at?: string;
}

export interface LaunchesResponse {
  tab: "launched" | "upcoming";
  total: number;
  page: number;
  page_size: number;
  items: LaunchVehicle[];
  stats: {
    total_launched: number;
    total_upcoming: number;
    new_variants: number;
    facelifts: number;
    special_editions: number;
    new_models: number;
  };
  freshness: {
    source_website: string;
    last_scraped_at?: string;
    actual_date_cutoff?: string;
    scraper_version?: string;
    listing_pages_examined?: number;
    news_articles_examined?: number;
    detail_pages_examined?: number;
    new_models_discovered?: number;
    new_variants_discovered?: number;
    facelifts_discovered?: number;
    special_editions_discovered?: number;
  };
  available_filters: {
    brands: string[];
    body_types: string[];
    fuel_types: string[];
    transmissions: string[];
    price_range: { min: number; max: number };
  };
}

export interface DataQualityReport {
  validation_timestamp: string;
  dataset_name: string;
  total_rows: number;
  total_columns: number;
  total_issues_count: number;
  severity_counts: {
    ERROR: number;
    WARNING: number;
    INFO: number;
  };
  records_requiring_manual_review: number;
  missing_data_analysis: {
    total_rows: number;
    fields: Record<string, {
      missing_count: number;
      missing_percentage: number;
      not_applicable_count: number;
      adjusted_missing_count: number;
      adjusted_missing_percentage: number;
    }>;
    ev_records_count?: number;
    ice_records_count?: number;
  };
  duplicate_analysis: {
    exact_duplicate_rows_count: number;
    duplicate_urls_count: number;
    normalized_duplicate_count: number;
  };
  summary_statistics?: {
    price?: { min: number; max: number; mean: number; median: number };
    unique_brands_count?: number;
    unique_models_count?: number;
    fuel_type_distribution?: Record<string, number>;
    body_type_distribution?: Record<string, number>;
  };
  review_actions_summary?: Record<string, number>;
}

export interface DataQualityIssue {
  record_id: string;
  brand: string;
  model: string;
  variant?: string;
  field: string;
  issue_type: string;
  severity: "ERROR" | "WARNING" | "INFO";
  observed_value: string;
  recommended_action: string;
}

export interface DataQualityIssuesResponse {
  dataset: string;
  total: number;
  page: number;
  page_size: number;
  severity_counts: {
    ERROR: number;
    WARNING: number;
    INFO: number;
  };
  items: DataQualityIssue[];
}

export interface TCOYearlyBreakdown {
  year: number;
  fuel_cost: number;
  maintenance_cost: number;
  insurance_cost: number;
  financing_interest: number;
  depreciation_loss: number;
  cumulative_net_cost: number;
}

export interface TCOResponse {
  vehicle_name: string;
  ex_showroom_price: number;
  on_road_estimated_price: number;
  ownership_years: number;
  total_distance_km: number;
  fuel_total_cost: number;
  maintenance_total_cost: number;
  insurance_total_cost: number;
  financing_interest_total: number;
  estimated_resale_value: number;
  total_depreciation: number;
  net_total_ownership_cost: number;
  cost_per_km: number;
  monthly_equivalent_cost: number;
  yearly_breakdown: TCOYearlyBreakdown[];
  assumptions: Record<string, any>;
}

export interface PriceIntelligenceResponse {
  vehicle_identifier: string;
  predicted_ex_showroom: number;
  ex_showroom_range_min: number;
  ex_showroom_range_max: number;
  estimated_on_road: number;
  actual_ex_showroom?: number;
  price_difference_vs_model?: number;
  vfm_score: number;
  vfm_verdict: string;
  variant_ladder: Array<{
    id: number;
    variant: string;
    fuel_type?: string;
    transmission?: string;
    ex_showroom_price: number;
  }>;
  segment_benchmarks: Array<{
    id: number;
    name: string;
    price: number;
    mileage?: number;
    safety_rating?: number;
    power?: number;
  }>;
  model_provenance: {
    model_name: string;
    evaluation_dataset_rows: number;
    mean_absolute_error_inr: number;
    r2_score: number;
  };
}

export interface LaunchAlert {
  alert_id: string;
  name: string;
  criteria: {
    budget_max?: number;
    brand?: string;
    fuel_type?: string;
    transmission?: string;
    body_type?: string;
    launch_classification?: string;
  };
  is_active: boolean;
  created_at: string;
  telegram_chat_id?: string;
  matches_count: number;
}