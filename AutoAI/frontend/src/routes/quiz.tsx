import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles, Trophy } from "lucide-react";
import api, { type Recommendation, formatINR } from "@/services/api";

export const Route = createFileRoute("/quiz")({ component: QuizPage });

function QuizPage() {
  const [step, setStep] = useState(0);
  const [budget, setBudget] = useState(1500000);
  const [fuelType, setFuelType] = useState("Petrol");
  const [transmission, setTransmission] = useState("Automatic");
  const [family, setFamily] = useState(4);
  const [bodyType, setBodyType] = useState("SUV");
  const [city, setCity] = useState(true);
  const [highway, setHighway] = useState(false);
  const [priority, setPriority] = useState<"safety" | "mileage" | "maintenance" | "resale">("safety");
  const [results, setResults] = useState<Recommendation[] | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      const r = await api.post<Recommendation[]>("/recommend", {
        budget,
        fuel_type: fuelType,
        transmission,
        family_members: family,
        priority,
        body_type: bodyType,
        city_drive: city,
        highway_drive: highway,
        maintenance_sensitive: priority === "maintenance",
        status: "CURRENT",
      });
      setResults(r.data || []);
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setResults([]);
      } else {
        toast?.error?.(err?.response?.data?.detail || "Failed to fetch recommendations");
      }
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { title: "What's your budget?", body: (
      <div className="space-y-4">
        <div className="text-4xl font-bold text-primary">{formatINR(budget)}</div>
        <input type="range" min={300000} max={10000000} step={100000} value={budget} onChange={(e) => setBudget(+e.target.value)} className="w-full accent-[var(--color-primary)]" />
      </div>
    )},
    { title: "Fuel & Transmission", body: (
      <div className="space-y-6">
        <ChoiceGrid label="Fuel" value={fuelType} onChange={setFuelType} options={["Petrol", "Diesel", "Electric", "Hybrid"]} />
        <ChoiceGrid label="Transmission" value={transmission} onChange={setTransmission} options={["Automatic", "Manual", "CVT"]} />
        <ChoiceGrid label="Body Type" value={bodyType} onChange={setBodyType} options={["SUV", "Sedan", "Hatchback", "MUV"]} />
      </div>
    )},
    { title: "Family & Driving", body: (
      <div className="space-y-6">
        <div>
          <div className="mb-2 text-sm text-muted-foreground">Family members: <span className="text-foreground font-semibold">{family}</span></div>
          <input type="range" min={1} max={8} value={family} onChange={(e) => setFamily(+e.target.value)} className="w-full accent-[var(--color-primary)]" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Toggle label="City Drive" value={city} onChange={setCity} />
          <Toggle label="Highway Drive" value={highway} onChange={setHighway} />
        </div>
      </div>
    )},
    { title: "Your top priority?", body: (
      <ChoiceGrid label="" value={priority} onChange={(v) => setPriority(v as typeof priority)} options={["safety", "mileage", "maintenance", "resale"]} />
    )},
  ];

  if (results) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-2xl font-bold">
            <Trophy className="h-6 w-6 text-primary" /> Top Verified Matches
          </div>
          <button
            onClick={() => { setResults(null); setStep(0); }}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs hover:bg-white/10 transition-colors"
          >
            Retake Questionnaire
          </button>
        </div>

        {results.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-12 text-center text-muted-foreground space-y-3">
            <p className="text-lg font-semibold text-foreground">No matching vehicles found</p>
            <p className="text-sm">
              We couldn't find vehicles matching all strict constraints (budget: {formatINR(budget)}, {fuelType}, {transmission}, {bodyType}).
            </p>
            <button
              onClick={() => { setResults(null); setStep(0); }}
              className="mt-4 rounded-xl px-5 py-2.5 text-sm font-semibold text-primary-foreground"
              style={{ background: "var(--gradient-primary)" }}
            >
              Adjust Answers
            </button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {results.map((r, i) => (
              <motion.div
                key={r.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md flex flex-col justify-between"
              >
                <div>
                  <div className="relative aspect-[16/10] bg-muted">
                    {r.image || (r as any).image_url ? (
                      <img
                        src={r.image || (r as any).image_url}
                        alt={r.model}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="grid h-full place-items-center text-xs text-muted-foreground">No Image</div>
                    )}
                    <div className="absolute right-2 top-2 rounded-lg bg-primary px-3 py-1 text-sm font-bold text-primary-foreground shadow">
                      {r.score}% Match
                    </div>
                  </div>
                  <div className="space-y-3 p-4">
                    <div>
                      <div className="text-xs text-muted-foreground">{r.brand}</div>
                      <div className="text-lg font-semibold">{r.model} <span className="text-xs text-muted-foreground font-normal">{r.variant}</span></div>
                    </div>
                    <div className="text-xl font-bold text-primary">
                      {r.starting_price && r.ending_price ? (
                        `${formatINR(r.starting_price)} - ${formatINR(r.ending_price)}`
                      ) : (
                        formatINR(r.price || (r as any).ex_showroom_price || 0)
                      )}
                    </div>
                    {r.reasons && r.reasons.length > 0 && (
                      <ul className="space-y-1 text-xs text-muted-foreground border-t border-white/5 pt-2">
                        {r.reasons.map((reason) => (
                          <li key={reason} className="flex items-center gap-1.5">
                            <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" /> {reason}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center gap-2 text-xs text-muted-foreground">
        <Sparkles className="h-4 w-4 text-primary" /> Step {step + 1} of {steps.length}
      </div>
      <div className="mb-6 h-1 rounded-full bg-white/10">
        <motion.div animate={{ width: `${((step + 1) / steps.length) * 100}%` }} className="h-full rounded-full" style={{ background: "var(--gradient-primary)" }} />
      </div>
      <div className="rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-md">
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            <h2 className="mb-6 text-2xl font-bold">{steps[step].title}</h2>
            {steps[step].body}
          </motion.div>
        </AnimatePresence>
        <div className="mt-8 flex justify-between">
          <button onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0} className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm disabled:opacity-40">
            <ChevronLeft className="h-4 w-4" /> Back
          </button>
          {step === steps.length - 1 ? (
            <button onClick={submit} disabled={loading} className="flex items-center gap-1 rounded-lg px-5 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" style={{ background: "var(--gradient-primary)" }}>
              {loading ? "Finding matches…" : "Get Recommendations"} <Sparkles className="h-4 w-4" />
            </button>
          ) : (
            <button onClick={() => setStep((s) => s + 1)} className="flex items-center gap-1 rounded-lg px-4 py-2 text-sm font-semibold text-primary-foreground" style={{ background: "var(--gradient-primary)" }}>
              Next <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ChoiceGrid({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div>
      {label && <div className="mb-2 text-sm text-muted-foreground">{label}</div>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {options.map((o) => (
          <button key={o} onClick={() => onChange(o)} className={`rounded-xl border p-3 text-sm capitalize transition-all ${value === o ? "border-primary bg-primary/15 text-primary" : "border-white/10 bg-white/5 hover:bg-white/10"}`}>
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)} className={`rounded-xl border p-3 text-sm ${value ? "border-primary bg-primary/15 text-primary" : "border-white/10 bg-white/5"}`}>
      {label}: {value ? "Yes" : "No"}
    </button>
  );
}