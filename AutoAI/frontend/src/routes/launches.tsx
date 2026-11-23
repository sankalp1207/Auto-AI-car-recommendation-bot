import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Rocket,
  Calendar,
  Sparkles,
  Search,
  RotateCcw,
  ExternalLink,
  ChevronRight,
  Shield,
  Zap,
  Gauge,
  Fuel,
  SlidersHorizontal,
  Clock,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Car as CarIcon,
  X,
  Layers,
  ArrowUpDown,
} from "lucide-react";
import api, { type LaunchVehicle, type LaunchesResponse, formatINR } from "@/services/api";

export const Route = createFileRoute("/launches")({
  component: LaunchesPage,
});

export function LaunchesPage() {
  const [activeTab, setActiveTab] = useState<"launched" | "upcoming">("launched");
  const [data, setData] = useState<LaunchesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [brand, setBrand] = useState("");
  const [bodyType, setBodyType] = useState("");
  const [fuelType, setFuelType] = useState("");
  const [transmission, setTransmission] = useState("");
  const [sortBy, setSortBy] = useState("launch_date_desc");
  const [page, setPage] = useState(1);

  // Modal Detail
  const [selectedCar, setSelectedCar] = useState<LaunchVehicle | null>(null);

  const fetchLaunches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {
        tab: activeTab,
        sort_by: sortBy,
        page,
        page_size: 40,
      };
      if (search.trim()) params.search = search.trim();
      if (brand) params.brand = brand;
      if (bodyType) params.body_type = bodyType;
      if (fuelType) params.fuel_type = fuelType;
      if (transmission) params.transmission = transmission;

      const res = await api.get<LaunchesResponse>("/launches", { params });
      setData(res.data);
    } catch (err: any) {
      console.error("Error fetching launches:", err);
      setError("Failed to load new car launches. Please ensure the backend is running.");
    } finally {
      setLoading(false);
    }
  }, [activeTab, search, brand, bodyType, fuelType, transmission, sortBy, page]);

  useEffect(() => {
    fetchLaunches();
  }, [fetchLaunches]);

  const handleResetFilters = () => {
    setSearch("");
    setBrand("");
    setBodyType("");
    setFuelType("");
    setTransmission("");
    setSortBy("launch_date_desc");
    setPage(1);
  };

  const getRecordTypeBadge = (recordType?: string) => {
    switch (recordType) {
      case "NEW_MODEL":
        return { label: "New Model", bg: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" };
      case "NEW_VARIANT":
        return { label: "New Variant", bg: "bg-blue-500/15 text-blue-400 border-blue-500/30" };
      case "FACELIFT":
        return { label: "Facelift", bg: "bg-purple-500/15 text-purple-400 border-purple-500/30" };
      case "SPECIAL_EDITION":
        return { label: "Special Edition", bg: "bg-amber-500/15 text-amber-400 border-amber-500/30" };
      case "UPCOMING":
        return { label: "Upcoming", bg: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" };
      default:
        return { label: recordType || "Discovered", bg: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30" };
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      {/* Hero Header */}
      <div className="relative overflow-hidden border-b border-white/10 bg-gradient-to-b from-primary/10 via-background to-background py-12 px-4 sm:px-6 lg:px-8">
        <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:32px_32px]" />
        <div className="mx-auto max-w-7xl relative z-10">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider mb-4">
                <Rocket className="h-3.5 w-3.5" />
                Live CarWale Tracker
              </div>
              <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight">
                New Car <span className="bg-gradient-to-r from-primary to-amber-400 bg-clip-text text-transparent">Launches</span>
              </h1>
              <p className="mt-3 text-base sm:text-lg text-muted-foreground max-w-2xl">
                Real-time tracking of newly launched models, variants, facelifts, and upcoming vehicles in India. Validated exclusively from CarWale.
              </p>
            </div>

            {/* Freshness Badge Card */}
            {data?.freshness && (
              <div className="flex flex-col sm:flex-row gap-3 rounded-2xl border border-white/10 bg-card/60 backdrop-blur-md p-4 text-xs shadow-xl">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-emerald-400" />
                  <div>
                    <span className="text-muted-foreground block">Verified Feed</span>
                    <span className="font-semibold text-foreground">
                      {data.freshness.last_scraped_at
                        ? new Date(data.freshness.last_scraped_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })
                        : "Active"}
                    </span>
                  </div>
                </div>
                <div className="hidden sm:block w-px bg-white/10" />
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                  <div>
                    <span className="text-muted-foreground block">Source Quality</span>
                    <span className="font-semibold text-foreground">CarWale Cleaned</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Stats Bar */}
          {data?.stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-8">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">New Launches</span>
                <div className="text-2xl font-bold text-foreground mt-0.5">{data.stats.total_launched}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">New Variants</span>
                <div className="text-2xl font-bold text-blue-400 mt-0.5">{data.stats.new_variants}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">Facelifts</span>
                <div className="text-2xl font-bold text-purple-400 mt-0.5">{data.stats.facelifts}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">Special Editions</span>
                <div className="text-2xl font-bold text-amber-400 mt-0.5">{data.stats.special_editions}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">New Models</span>
                <div className="text-2xl font-bold text-emerald-400 mt-0.5">{data.stats.new_models}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-sm">
                <span className="text-xs text-muted-foreground">Upcoming Cars</span>
                <div className="text-2xl font-bold text-cyan-400 mt-0.5">{data.stats.total_upcoming}</div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 mt-8 border-b border-white/10">
            <button
              onClick={() => {
                setActiveTab("launched");
                setPage(1);
              }}
              className={`pb-3 px-4 font-semibold text-sm transition-all border-b-2 flex items-center gap-2 ${
                activeTab === "launched"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Rocket className="h-4 w-4" />
              Recently Launched ({data?.stats?.total_launched ?? "..."})
            </button>
            <button
              onClick={() => {
                setActiveTab("upcoming");
                setPage(1);
              }}
              className={`pb-3 px-4 font-semibold text-sm transition-all border-b-2 flex items-center gap-2 ${
                activeTab === "upcoming"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Calendar className="h-4 w-4" />
              Upcoming Vehicles ({data?.stats?.total_upcoming ?? "..."})
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 mt-8">
        {/* Filter Toolbar */}
        <div className="rounded-2xl border border-white/10 bg-card/40 backdrop-blur-xl p-4 sm:p-5 shadow-lg mb-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Search brand, model, trim..."
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-white/10 bg-background/80 text-sm focus:outline-none focus:border-primary transition"
              />
            </div>

            {/* Brand Filter */}
            <select
              value={brand}
              onChange={(e) => {
                setBrand(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-xl border border-white/10 bg-background/80 text-sm focus:outline-none focus:border-primary transition"
            >
              <option value="">All Brands</option>
              {data?.available_filters?.brands?.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>

            {/* Fuel Filter */}
            <select
              value={fuelType}
              onChange={(e) => {
                setFuelType(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-xl border border-white/10 bg-background/80 text-sm focus:outline-none focus:border-primary transition"
            >
              <option value="">All Fuels</option>
              {data?.available_filters?.fuel_types?.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>

            {/* Body Type Filter */}
            <select
              value={bodyType}
              onChange={(e) => {
                setBodyType(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-xl border border-white/10 bg-background/80 text-sm focus:outline-none focus:border-primary transition"
            >
              <option value="">All Body Styles</option>
              {data?.available_filters?.body_types?.map((bt) => (
                <option key={bt} value={bt}>
                  {bt}
                </option>
              ))}
            </select>

            {/* Sort Filter */}
            <div className="flex gap-2">
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 rounded-xl border border-white/10 bg-background/80 text-sm focus:outline-none focus:border-primary transition"
              >
                <option value="launch_date_desc">Latest Launch First</option>
                <option value="launch_date_asc">Oldest Launch First</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
                <option value="brand_asc">Brand (A-Z)</option>
              </select>

              {(search || brand || bodyType || fuelType || transmission || sortBy !== "launch_date_desc") && (
                <button
                  onClick={handleResetFilters}
                  title="Reset Filters"
                  className="px-3 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-muted-foreground hover:text-foreground transition flex items-center justify-center shrink-0"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* State Indicators */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-64 rounded-2xl border border-white/10 bg-card/30 animate-pulse p-5" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-8 text-center max-w-xl mx-auto my-12">
            <AlertCircle className="h-10 w-10 text-destructive mx-auto mb-3" />
            <h3 className="text-lg font-bold text-foreground">Unable to Fetch Launches</h3>
            <p className="text-sm text-muted-foreground mt-1 mb-4">{error}</p>
            <button
              onClick={fetchLaunches}
              className="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 transition"
            >
              Retry Connection
            </button>
          </div>
        )}

        {!loading && !error && data?.items?.length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-card/30 p-12 text-center max-w-md mx-auto my-12">
            <CarIcon className="h-12 w-12 text-muted-foreground/50 mx-auto mb-3" />
            <h3 className="text-lg font-bold text-foreground">No Vehicles Match Criteria</h3>
            <p className="text-sm text-muted-foreground mt-1 mb-5">
              Try adjusting your active filters or search terms to see available launches.
            </p>
            <button
              onClick={handleResetFilters}
              className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-sm font-medium transition"
            >
              Clear All Filters
            </button>
          </div>
        )}

        {/* Vehicle Grid */}
        {!loading && !error && data && data.items.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((car, idx) => {
              const badge = getRecordTypeBadge(car.record_type);
              return (
                <motion.div
                  key={car.id || idx}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03, duration: 0.3 }}
                  className="group relative rounded-2xl border border-white/10 bg-card/50 hover:bg-card/80 backdrop-blur-md overflow-hidden transition-all duration-300 hover:border-primary/40 hover:shadow-2xl hover:shadow-primary/5 flex flex-col justify-between"
                >
                  <div className="p-5">
                    {/* Top Row: Brand & Classification Badge */}
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <span className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">
                        {car.brand}
                      </span>
                      <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${badge.bg}`}>
                        {badge.label}
                      </span>
                    </div>

                    {/* Model & Variant */}
                    <h3 className="text-xl font-bold tracking-tight text-foreground group-hover:text-primary transition-colors line-clamp-1">
                      {car.model}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5 mb-4 line-clamp-1 font-mono">
                      {car.variant || "Standard Edition"}
                    </p>

                    {/* Price Tag */}
                    <div className="mb-4">
                      <div className="text-2xl font-extrabold text-foreground tracking-tight">
                        {car.price ? formatINR(car.price) : "Price on Request"}
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {car.status === "UPCOMING" ? "Estimated Ex-Showroom" : "Ex-Showroom India"}
                      </span>
                    </div>

                    {/* Key Specs Pills */}
                    <div className="grid grid-cols-3 gap-2 py-3 border-y border-white/5 text-xs">
                      <div className="flex flex-col">
                        <span className="text-muted-foreground text-[10px]">Fuel</span>
                        <span className="font-medium text-foreground truncate">{car.fuel_type || "N/A"}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-muted-foreground text-[10px]">Gearbox</span>
                        <span className="font-medium text-foreground truncate">{car.transmission || "N/A"}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-muted-foreground text-[10px]">Type</span>
                        <span className="font-medium text-foreground truncate">{car.body_type || "Passenger"}</span>
                      </div>
                    </div>

                    {/* Secondary Specs (Power, Engine, Mileage/Range) */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground mt-3">
                      {car.power ? (
                        <span className="flex items-center gap-1">
                          <Zap className="h-3.5 w-3.5 text-amber-400" />
                          {car.power} bhp
                        </span>
                      ) : (
                        <span />
                      )}

                      {car.engine_cc ? (
                        <span className="flex items-center gap-1">
                          <Gauge className="h-3.5 w-3.5 text-blue-400" />
                          {car.engine_cc} cc
                        </span>
                      ) : car.battery_capacity ? (
                        <span className="flex items-center gap-1 text-emerald-400">
                          <Zap className="h-3.5 w-3.5" />
                          {car.battery_capacity} kWh
                        </span>
                      ) : null}

                      {car.launch_date && (
                        <span className="flex items-center gap-1 text-[11px]">
                          <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                          {car.launch_date}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Card Bottom CTA */}
                  <div className="px-5 py-3.5 bg-white/[0.02] border-t border-white/5 flex items-center justify-between">
                    <button
                      onClick={() => setSelectedCar(car)}
                      className="text-xs font-semibold text-primary hover:text-primary/80 transition flex items-center gap-1"
                    >
                      View Full Specs <ChevronRight className="h-3.5 w-3.5" />
                    </button>

                    {car.variant_url || car.model_url ? (
                      <a
                        href={car.variant_url || car.model_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-muted-foreground hover:text-foreground transition flex items-center gap-1"
                      >
                        CarWale <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : null}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal Detail Dialog */}
      <AnimatePresence>
        {selectedCar && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl border border-white/10 bg-card p-6 sm:p-8 shadow-2xl text-foreground"
            >
              <button
                onClick={() => setSelectedCar(null)}
                className="absolute top-5 right-5 p-2 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 transition"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="mb-6">
                <span className="text-xs font-bold text-primary uppercase tracking-wider">
                  {selectedCar.brand}
                </span>
                <h2 className="text-2xl sm:text-3xl font-extrabold mt-1">
                  {selectedCar.model}
                </h2>
                <p className="text-sm text-muted-foreground font-mono mt-0.5">
                  {selectedCar.variant || "Standard Variant"}
                </p>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <div className="text-3xl font-extrabold text-foreground">
                    {selectedCar.price ? formatINR(selectedCar.price) : "Price on Request"}
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getRecordTypeBadge(selectedCar.record_type).bg}`}>
                    {getRecordTypeBadge(selectedCar.record_type).label}
                  </span>
                </div>
              </div>

              {/* Technical Specifications Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5 py-4 border-y border-white/10 text-xs">
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Fuel Type</span>
                  <span className="font-semibold text-foreground text-sm">{selectedCar.fuel_type || "N/A"}</span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Transmission</span>
                  <span className="font-semibold text-foreground text-sm">{selectedCar.transmission || "N/A"}</span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Body Style</span>
                  <span className="font-semibold text-foreground text-sm">{selectedCar.body_type || "N/A"}</span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Power</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.power ? `${selectedCar.power} bhp` : "N/A"}
                  </span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Torque</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.torque ? `${selectedCar.torque} Nm` : "N/A"}
                  </span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Engine Displacement</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.engine_cc ? `${selectedCar.engine_cc} cc` : "N/A"}
                  </span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Claimed Efficiency</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.mileage ? `${selectedCar.mileage} kmpl` : "N/A"}
                  </span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Seating Capacity</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.seating ? `${selectedCar.seating} Seats` : "5 Seats"}
                  </span>
                </div>
                <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                  <span className="text-muted-foreground block text-[10px]">Boot Space</span>
                  <span className="font-semibold text-foreground text-sm">
                    {selectedCar.boot_space ? `${selectedCar.boot_space} L` : "N/A"}
                  </span>
                </div>
              </div>

              {/* Launch Evidence & Source Metadata */}
              <div className="mt-5 space-y-2 text-xs">
                <div className="flex items-center justify-between py-1">
                  <span className="text-muted-foreground">Launch Date</span>
                  <span className="font-semibold">{selectedCar.launch_date || "Announced"}</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-muted-foreground">Date Type</span>
                  <span className="font-mono text-xs">{selectedCar.launch_date_type || "EXACT_DATE"}</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-muted-foreground">External Verification</span>
                  <span className="font-semibold text-emerald-400">CarWale Sole Source</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap gap-3">
                {selectedCar.variant_url && (
                  <a
                    href={selectedCar.variant_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 py-2.5 px-4 rounded-xl bg-primary text-primary-foreground font-semibold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition"
                  >
                    View on CarWale <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                {selectedCar.launch_evidence_url && (
                  <a
                    href={selectedCar.launch_evidence_url}
                    target="_blank"
                    rel="noreferrer"
                    className="py-2.5 px-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-semibold flex items-center gap-2 transition"
                  >
                    Launch Article <ExternalLink className="h-4 w-4" />
                  </a>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
