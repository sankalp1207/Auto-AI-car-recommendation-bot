import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { GitCompare, Trophy, Sparkles } from "lucide-react";
import api, { formatINR } from "@/services/api";
import { toast } from "sonner";

export const Route = createFileRoute("/compare")({ component: ComparePage });

interface CarOption { id: number; brand: string; model: string; variant: string; }
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
  { label: "Pros", key: "pros" },
  { label: "Cons", key: "cons" },
];

function ComparePage() {
  const [options, setOptions] = useState<CarOption[]>([]);
  const [id1, setId1] = useState<number | "">("");
  const [id2, setId2] = useState<number | "">("");
  const [result, setResult] = useState<{ car1: CarSpec; car2: CarSpec; explanation?: string } | null>(null);
  const [rows, setRows] = useState(coreRows);

  useEffect(() => {
    api.get<CarOption[]>("/compare/cars").then((r) => setOptions(r.data)).catch(() => {});
    const saved: number[] = JSON.parse(localStorage.getItem("compare") || "[]");
    if (saved[0]) setId1(saved[0]);
    if (saved[1]) setId2(saved[1]);
  }, []);

  useEffect(() => {
    if (result && result.car1 && result.car2) {
      const excludedKeys = new Set([
        "id", "brand", "model", "variant", "price", "fuel", "transmission",
        "engine_cc", "engine", "power", "torque", "mileage", "seating",
        "seating_capacity", "boot_space", "ground_clearance", "safety_rating",
        "image", "image_url", "pros", "cons", "pros_list", "cons_list",
        "summary", "summary_embedding_text", "year", "sunroof", "adas",
        "touchscreen_inches", "touchscreen", "carplay_androidauto",
        "wireless_android_auto", "wireless_apple_carplay", "ideal_for",
        "maintenance_cost", "resale_rating", "city_use", "highway_use",
        "family_friendly", "Unnamed: 0"
      ]);

      const additionalRows: any[] = [];
      const keys = Object.keys(result.car1);
      for (const key of keys) {
        if (!excludedKeys.has(key)) {
          const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
          const v1 = result.car1[key];
          const v2 = result.car2[key];
          const isNum = typeof v1 === "number" && typeof v2 === "number";
          
          additionalRows.push({
            label,
            key,
            higher: isNum ? true : undefined
          });
        }
      }
      setRows([...coreRows, ...additionalRows]);
    } else {
      setRows(coreRows);
    }
  }, [result]);

  const [loading, setLoading] = useState(false);

  const compare = async () => {
    if (!id1 || !id2) return;
    setLoading(true);
    try {
      const r = await api.post("/compare", { car1_id: id1, car2_id: id2 });
      setResult(r.data);
    } catch {
      toast?.error?.("Failed to compare vehicles");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold"><GitCompare className="h-6 w-6 text-primary" /> Compare Cars</h1>
      <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md sm:grid-cols-[1fr_1fr_auto]">
        <select value={id1} onChange={(e) => setId1(+e.target.value || "")} className="input">
          <option value="">Select first car</option>
          {options.map((o) => <option key={o.id} value={o.id}>{o.brand} {o.model} {o.variant}</option>)}
        </select>
        <select value={id2} onChange={(e) => setId2(+e.target.value || "")} className="input">
          <option value="">Select second car</option>
          {options.map((o) => <option key={o.id} value={o.id}>{o.brand} {o.model} {o.variant}</option>)}
        </select>
        <button
          onClick={compare}
          disabled={!id1 || !id2 || loading}
          className="rounded-lg px-5 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40"
          style={{ background: "var(--gradient-primary)" }}
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {result && (
        <div className="space-y-6">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md">
            <div className="grid grid-cols-3 border-b border-white/10 bg-white/5 items-center">
              <div className="p-4 text-sm font-medium text-muted-foreground">Vehicle</div>
              <div className="p-4 space-y-2">
                {(result.car1.image_url || result.car1.image) && (
                  <div className="h-24 w-full overflow-hidden rounded-lg bg-muted">
                    <img src={result.car1.image_url || result.car1.image} alt={result.car1.model} className="h-full w-full object-cover" />
                  </div>
                )}
                <div className="font-semibold">{result.car1.brand} {result.car1.model}</div>
                <div className="text-xs text-muted-foreground">{result.car1.variant}</div>
              </div>
              <div className="p-4 space-y-2">
                {(result.car2.image_url || result.car2.image) && (
                  <div className="h-24 w-full overflow-hidden rounded-lg bg-muted">
                    <img src={result.car2.image_url || result.car2.image} alt={result.car2.model} className="h-full w-full object-cover" />
                  </div>
                )}
                <div className="font-semibold">{result.car2.brand} {result.car2.model}</div>
                <div className="text-xs text-muted-foreground">{result.car2.variant}</div>
              </div>
            </div>
            {rows.map((row) => {
              const v1 = result.car1[row.key];
              const v2 = result.car2[row.key];
              let winner: 1 | 2 | 0 = 0;
              if (typeof v1 === "number" && typeof v2 === "number" && row.higher !== undefined) {
                if (v1 === v2) winner = 0;
                else if (row.higher) winner = v1 > v2 ? 1 : 2;
                else winner = v1 < v2 ? 1 : 2;
              }
              const fmt = (v: string | number) => row.key === "price" && typeof v === "number" ? formatINR(v) : String(v || "Specification not available in current database");
              return (
                <div key={row.label} className="grid grid-cols-3 border-b border-white/5 last:border-0">
                  <div className="p-4 text-sm text-muted-foreground">{row.label}</div>
                  <div className={`flex items-center gap-2 p-4 text-sm ${winner === 1 ? "font-semibold text-primary" : ""}`}>
                    {fmt(v1)} {winner === 1 && <Trophy className="h-3.5 w-3.5" />}
                  </div>
                  <div className={`flex items-center gap-2 p-4 text-sm ${winner === 2 ? "font-semibold text-primary" : ""}`}>
                    {fmt(v2)} {winner === 2 && <Trophy className="h-3.5 w-3.5" />}
                  </div>
                </div>
              );
            })}
          </div>

          {result.explanation && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md space-y-3">
              <h3 className="text-lg font-semibold flex items-center gap-2 text-primary">
                <Sparkles className="h-5 w-5 text-primary" /> AI Verdict & Summary
              </h3>
              <div className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground border-t border-white/5 pt-4">
                {result.explanation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}