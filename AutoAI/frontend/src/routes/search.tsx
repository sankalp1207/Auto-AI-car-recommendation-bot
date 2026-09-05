import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { Search as SearchIcon, RotateCcw, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import api, { type Car } from "@/services/api";
import { CarCard } from "@/components/CarCard";
import { toast } from "sonner";

export const Route = createFileRoute("/search")({ component: SearchPage });

const PAGE_SIZE = 24;

function SearchPage() {
  const [q, setQ] = useState("");
  const [brand, setBrand] = useState("");
  const [fuel, setFuel] = useState("");
  const [transmission, setTransmission] = useState("");
  const [bodyType, setBodyType] = useState("");
  const [seating, setSeating] = useState<number | "">("");
  const [status, setStatus] = useState("CURRENT");
  const [budget, setBudget] = useState<number>(5000000);
  const [sortBy, setSortBy] = useState("price");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  const [cars, setCars] = useState<Car[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCars = useCallback(async (targetPage = 1) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        page: targetPage,
        limit: PAGE_SIZE,
        sort_by: sortBy,
        order: sortOrder,
      };
      if (q.trim()) params.q = q.trim();
      if (brand.trim()) params.brand = brand.trim();
      if (fuel) params.fuel = fuel;
      if (transmission) params.transmission = transmission;
      if (bodyType) params.body_type = bodyType;
      if (seating) params.seating = seating;
      if (status) params.status = status;
      if (budget) params.budget = budget;

      const r = await api.get<Car[]>("/search", { params });
      setCars(r.data || []);
      setPage(targetPage);
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setCars([]);
      } else {
        setError("Unable to reach backend server. Please check connection.");
      }
    } finally {
      setLoading(false);
    }
  }, [q, brand, fuel, transmission, bodyType, seating, status, budget, sortBy, sortOrder]);

  useEffect(() => {
    fetchCars(1);
  }, [fetchCars]);

  const resetFilters = () => {
    setQ("");
    setBrand("");
    setFuel("");
    setTransmission("");
    setBodyType("");
    setSeating("");
    setStatus("CURRENT");
    setBudget(5000000);
    setSortBy("price");
    setSortOrder("asc");
  };

  const addToWishlist = async (car: Car) => {
    try {
      await api.post("/wishlist", { car_id: car.id });
      toast?.success?.("Added to wishlist");
    } catch {
      toast?.error?.("Login required to save");
    }
  };

  const addToCompare = (car: Car) => {
    const existing: number[] = JSON.parse(localStorage.getItem("compare") || "[]");
    const next = [...new Set([...existing, car.id])].slice(-2);
    localStorage.setItem("compare", JSON.stringify(next));
    toast?.success?.("Added to compare");
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <aside className="h-fit space-y-4 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-md lg:sticky lg:top-24">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Catalog Filters</h2>
          <button
            onClick={resetFilters}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
          >
            <RotateCcw className="h-3 w-3" /> Reset
          </button>
        </div>

        <Field label="Model / Search Keyword">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchCars(1)}
            placeholder="Creta, Nexon, Thar, EV..."
            className="input"
          />
        </Field>

        <Field label="Brand">
          <input
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchCars(1)}
            placeholder="Tata, Hyundai, Mahindra..."
            className="input"
          />
        </Field>

        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="input">
            <option value="CURRENT">Current In-Market (2,076)</option>
            <option value="UPCOMING">Upcoming Launches (169)</option>
            <option value="ALL">All Statuses (2,245)</option>
          </select>
        </Field>

        <Field label="Fuel Type">
          <select value={fuel} onChange={(e) => setFuel(e.target.value)} className="input">
            <option value="">Any Fuel</option>
            <option value="Petrol">Petrol</option>
            <option value="Diesel">Diesel</option>
            <option value="Electric">Electric / EV</option>
            <option value="CNG">CNG</option>
            <option value="Hybrid">Hybrid</option>
          </select>
        </Field>

        <Field label="Transmission">
          <select value={transmission} onChange={(e) => setTransmission(e.target.value)} className="input">
            <option value="">Any Transmission</option>
            <option value="Automatic">Automatic</option>
            <option value="Manual">Manual</option>
            <option value="CVT">CVT</option>
          </select>
        </Field>

        <Field label="Body Type">
          <select value={bodyType} onChange={(e) => setBodyType(e.target.value)} className="input">
            <option value="">Any Body Style</option>
            <option value="SUV">SUV</option>
            <option value="Sedan">Sedan</option>
            <option value="Hatchback">Hatchback</option>
            <option value="MUV">MUV / MPV</option>
          </select>
        </Field>

        <Field label="Min Seating Capacity">
          <select value={seating} onChange={(e) => setSeating(e.target.value ? +e.target.value : "")} className="input">
            <option value="">Any Seating</option>
            <option value="5">5+ Seats</option>
            <option value="6">6+ Seats</option>
            <option value="7">7+ Seats</option>
            <option value="8">8+ Seats</option>
          </select>
        </Field>

        <Field label={`Max Budget: ₹${(budget / 100000).toFixed(1)} L`}>
          <input
            type="range"
            min={300000}
            max={10000000}
            step={100000}
            value={budget}
            onChange={(e) => setBudget(+e.target.value)}
            className="w-full accent-[var(--color-primary)]"
          />
        </Field>

        <button
          onClick={() => fetchCars(1)}
          className="flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-95"
          style={{ background: "var(--gradient-primary)" }}
        >
          <SearchIcon className="h-4 w-4" /> Apply Filters
        </button>
      </aside>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Vehicle Catalog</h1>
            <span className="text-sm text-muted-foreground">
              Showing {cars.length} vehicles on Page {page}
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">Sort:</span>
            <select
              value={`${sortBy}_${sortOrder}`}
              onChange={(e) => {
                const [sb, so] = e.target.value.split("_");
                setSortBy(sb);
                setSortOrder(so as "asc" | "desc");
              }}
              className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-foreground text-xs"
            >
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="mileage_desc">Mileage: High to Low</option>
              <option value="safety_rating_desc">Safety: High to Low</option>
              <option value="power_desc">Power: High to Low</option>
            </select>
          </div>
        </div>

        {error ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-destructive/20 bg-destructive/5 p-10 text-center text-sm space-y-3">
            <AlertCircle className="h-6 w-6 text-destructive" />
            <p className="text-destructive font-medium">{error}</p>
            <button
              onClick={() => fetchCars(page)}
              className="rounded-lg border border-white/10 bg-white/5 px-4 py-1.5 text-xs hover:bg-white/10"
            >
              Retry
            </button>
          </div>
        ) : loading ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-16 text-center text-muted-foreground animate-pulse">
            Querying real database vehicles…
          </div>
        ) : cars.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-12 text-center text-muted-foreground space-y-2">
            <p className="text-base font-semibold text-foreground">No vehicles match your filters.</p>
            <p className="text-sm text-muted-foreground">
              Try adjusting your budget slider, selecting "All Statuses", or changing fuel/transmission filters.
            </p>
            <button
              onClick={resetFilters}
              className="mt-3 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs hover:bg-white/10 text-primary"
            >
              Clear All Filters
            </button>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {cars.map((c) => (
                <CarCard key={c.id} car={c} onWishlist={addToWishlist} onCompare={addToCompare} />
              ))}
            </div>

            <div className="flex items-center justify-between border-t border-white/10 pt-4 text-sm">
              <button
                onClick={() => fetchCars(Math.max(1, page - 1))}
                disabled={page <= 1 || loading}
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium disabled:opacity-30 hover:bg-white/10"
              >
                <ChevronLeft className="h-4 w-4" /> Previous
              </button>
              <span className="text-xs text-muted-foreground">Page {page}</span>
              <button
                onClick={() => fetchCars(page + 1)}
                disabled={cars.length < PAGE_SIZE || loading}
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium disabled:opacity-30 hover:bg-white/10"
              >
                Next <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}