import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { GitCompare, Trophy, Sparkles, Plus, X, IndianRupee, ShieldCheck, Fuel, Gauge } from "lucide-react";
import api, { formatINR, TCOResponse } from "@/services/api";
import { toast } from "sonner";

export const Route = createFileRoute("/compare")({ component: ComparePage });

interface CarOption {
  id: number;
  brand: string;
  model: string;
  variant: string;
}

interface CarSpec {
  [key: string]: any;
}

const coreRows = [
  { label: "Price", key: "price", higher: false },
  { label: "Fuel", key: "fuel" },
  { label: "Transmission", key: "transmission" },
  { label: "Engine (cc)", key: "engine_cc", higher: true },
  { label: "Power (bhp)", key: "power", higher: true },
  { label: "Torque (Nm)", key: "torque", higher: true },
  { label: "Mileage (km/l)", key: "mileage", higher: true },
  { label: "Seating", key: "seating", higher: true },
  { label: "Boot (L)", key: "boot_space", higher: true },
  { label: "Ground Clearance (mm)", key: "ground_clearance", higher: true },
  { label: "Safety Rating", key: "safety_rating", higher: true },
  { label: "Airbags", key: "airbags" },
  { label: "ADAS", key: "adas" },
  { label: "Sunroof", key: "sunroof" },
  { label: "Touchscreen", key: "touchscreen" },
  { label: "Wireless Android Auto", key: "wireless_android_auto" },
  { label: "Wireless Apple CarPlay", key: "wireless_apple_carplay" },
];

function ComparePage() {
  const [options, setOptions] = useState<CarOption[]>([]);
  const [selectedIds, setSelectedIds] = useState<(number | "")[]>(["", ""]);
  const [result, setResult] = useState<{
    cars?: CarSpec[];
    tco_estimates?: TCOResponse[];
    explanation?: string;
    car1?: CarSpec;
    car2?: CarSpec;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<CarOption[]>("/compare/cars").then((r) => setOptions(r.data)).catch(() => {});
    const saved: number[] = JSON.parse(localStorage.getItem("compare") || "[]");
    if (saved.length >= 2) {
      setSelectedIds([saved[0], saved[1]]);
    }
  }, []);

  const addSlot = () => {
    if (selectedIds.length < 4) {
      setSelectedIds([...selectedIds, ""]);
    }
  };

  const removeSlot = (index: number) => {
    if (selectedIds.length > 2) {
      const next = selectedIds.filter((_, i) => i !== index);
      setSelectedIds(next);
    }
  };

  const updateSelection = (index: number, val: number | "") => {
    const next = [...selectedIds];
    next[index] = val;
    setSelectedIds(next);
  };

  const validIds = selectedIds.filter((id): id is number => typeof id === "number" && id > 0);

  const compare = async () => {
    if (validIds.length < 2) return;
    setLoading(true);
    try {
      const r = await api.post("/compare", {
        car_ids: validIds,
        ownership_years: 5,
        annual_kms: 12000,
      });
      setResult(r.data);
    } catch {
      toast?.error?.("Failed to compare vehicles. Try different selections.");
    } finally {
      setLoading(false);
    }
  };

  const comparedCars: CarSpec[] = result?.cars || (result?.car1 && result?.car2 ? [result.car1, result.car2] : []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <GitCompare className="h-6 w-6 text-primary" /> Multi-Vehicle Comparison
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Compare 2 to 4 vehicles side-by-side with 5-year TCO calculations and AI trade-off analysis.
          </p>
        </div>
        {selectedIds.length < 4 && (
          <button
            onClick={addSlot}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium hover:bg-white/10"
          >
            <Plus className="h-3.5 w-3.5" /> Add Car ({selectedIds.length}/4)
          </button>
        )}
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md space-y-3">
        <div className={`grid gap-3 ${selectedIds.length === 2 ? "sm:grid-cols-2" : selectedIds.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-4"}`}>
          {selectedIds.map((val, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <select
                value={val}
                onChange={(e) => updateSelection(idx, +e.target.value || "")}
                className="input w-full text-xs"
              >
                <option value="">Select vehicle #{idx + 1}</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.brand} {o.model} {o.variant}
                  </option>
                ))}
              </select>
              {selectedIds.length > 2 && (
                <button
                  onClick={() => removeSlot(idx)}
                  className="rounded-lg p-2 text-muted-foreground hover:bg-white/10 hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={compare}
            disabled={validIds.length < 2 || loading}
            className="rounded-lg px-6 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
            style={{ background: "var(--gradient-primary)" }}
          >
            {loading ? "Comparing…" : `Compare ${validIds.length} Vehicles`}
          </button>
        </div>
      </div>

      {comparedCars.length > 0 && (
        <div className="space-y-6">
          {/* Main Specifications Table */}
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md">
            <div
              className="grid border-b border-white/10 bg-white/5 items-center"
              style={{ gridTemplateColumns: `180px repeat(${comparedCars.length}, minmax(200px, 1fr))` }}
            >
              <div className="p-4 text-sm font-semibold text-muted-foreground">Vehicle</div>
              {comparedCars.map((car, i) => (
                <div key={i} className="p-4 space-y-2 border-l border-white/5">
                  {(car.image_url || car.image) && (
                    <div className="h-28 w-full overflow-hidden rounded-lg bg-muted">
                      <img src={car.image_url || car.image} alt={car.model} className="h-full w-full object-cover" />
                    </div>
                  )}
                  <div className="font-bold text-base leading-tight">
                    {car.brand} {car.model}
                  </div>
                  <div className="text-xs text-muted-foreground">{car.variant || "Standard"}</div>
                  <div className="text-sm font-semibold text-primary">
                    {formatINR(car.price || car.ex_showroom_price || 0)}
                  </div>
                </div>
              ))}
            </div>

            {coreRows.map((row) => {
              const vals = comparedCars.map((c) => c[row.key]);
              const numVals = vals.filter((v): v is number => typeof v === "number");
              let bestVal: number | null = null;
              if (numVals.length === comparedCars.length && row.higher !== undefined) {
                bestVal = row.higher ? Math.max(...numVals) : Math.min(...numVals);
              }

              return (
                <div
                  key={row.label}
                  className="grid border-b border-white/5 last:border-0 items-center hover:bg-white/[0.02]"
                  style={{ gridTemplateColumns: `180px repeat(${comparedCars.length}, minmax(200px, 1fr))` }}
                >
                  <div className="p-3 text-xs font-medium text-muted-foreground">{row.label}</div>
                  {comparedCars.map((c, i) => {
                    const val = c[row.key];
                    const isBest = bestVal !== null && typeof val === "number" && val === bestVal;
                    const fmt = (v: any) => {
                      if (v === null || v === undefined || v === "") return "Specification not available in current database";
                      if (row.key === "price" && typeof v === "number") return formatINR(v);
                      return String(v);
                    };

                    return (
                      <div
                        key={i}
                        className={`p-3 text-xs border-l border-white/5 flex items-center gap-1.5 ${
                          isBest ? "font-semibold text-primary" : ""
                        }`}
                      >
                        <span>{fmt(val)}</span>
                        {isBest && <Trophy className="h-3 w-3 text-primary shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Feature D: Total Cost of Ownership Section */}
          {result?.tco_estimates && result.tco_estimates.length > 0 && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md space-y-4">
              <div className="flex items-center gap-2 text-lg font-semibold text-foreground">
                <IndianRupee className="h-5 w-5 text-emerald-400" />
                <span>5-Year Total Cost of Ownership (TCO) Comparison</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Deterministic calculation assuming 5 years ownership @ 12,000 km/year, including fuel/energy, insurance (IDV depreciation scale), and maintenance.
              </p>

              <div
                className="grid gap-4 pt-2"
                style={{ gridTemplateColumns: `repeat(auto-fit, minmax(220px, 1fr))` }}
              >
                {result.tco_estimates.map((tco, idx) => (
                  <div key={idx} className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                    <div className="font-semibold text-sm truncate">{tco.vehicle_name}</div>
                    <div className="space-y-1.5 text-xs text-muted-foreground border-t border-white/5 pt-2">
                      <div className="flex justify-between">
                        <span>Net 5-Yr Cost:</span>
                        <span className="font-bold text-foreground">{formatINR(tco.net_total_ownership_cost || 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Cost / km:</span>
                        <span className="font-medium text-emerald-400">₹{tco.cost_per_km || 0}/km</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Monthly Equiv:</span>
                        <span>{formatINR(tco.monthly_equivalent_cost || 0)}/mo</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Fuel/Energy:</span>
                        <span>{formatINR(tco.fuel_total_cost || 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Est. Resale:</span>
                        <span className="text-foreground">{formatINR(tco.estimated_resale_value || 0)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Verdict and Structured Trade-Offs */}
          {result?.explanation && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md space-y-3">
              <h3 className="text-base font-semibold flex items-center gap-2 text-primary">
                <Sparkles className="h-5 w-5 text-primary" /> AI Verdict & Trade-Off Analysis
              </h3>
              <div className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground border-t border-white/5 pt-3">
                {result.explanation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}