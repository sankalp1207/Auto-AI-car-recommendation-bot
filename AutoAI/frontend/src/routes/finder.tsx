import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Bot,
  User as UserIcon,
  X,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Info,
  GitCompare,
  Shield,
  Fuel,
  Settings2,
  Gauge,
  Star,
  RotateCcw,
  AlertCircle,
  Zap,
  Users,
  RefreshCw,
} from "lucide-react";
import api, { type Recommendation, formatINR } from "@/services/api";
import { useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/finder")({ component: FinderPage });

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CarRecommendation {
  id: number;
  brand: string;
  model: string;
  variant: string;
  price: number;
  price_basis?: string;
  status: string;
  fuel_type?: string;
  transmission?: string;
  seating_capacity?: number;
  mileage?: number;
  power?: number;
  safety_rating?: number;
  engine_cc?: number;
  boot_space?: number;
  ground_clearance?: number;
  sunroof?: boolean;
  adas?: boolean;
  touchscreen_inches?: number;
  carplay_androidauto?: boolean;
  image?: string;
  ideal_for?: string;
  pros?: string;
  cons?: string;
  suitability_score: number;
  matched_requirements: string[];
  strengths: string[];
  trade_offs: string[];
  missing_data: string[];
  score_breakdown?: Record<string, number>;
}

interface FinderResponse {
  session_id: string;
  preferences: Record<string, unknown>;
  needs_clarification: boolean;
  clarification_question?: string;
  recommendations: CarRecommendation[];
  total_matched: number;
  ai_response: string;
  no_results_reason?: string;
  alternative_suggestions: string[];
}

interface Message {
  role: "user" | "ai";
  text: string;
  recommendations?: CarRecommendation[];
  hasResults?: boolean;
  sessionId?: string;
  preferences?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const EXAMPLE_PROMPTS = [
  "Safe family SUV under ₹15 lakh with automatic transmission",
  "Fuel-efficient petrol hatchback for city commuting under ₹8 lakh",
  "Electric car with good range under ₹25 lakh",
  "7-seater MPV for large family under ₹20 lakh",
  "Sporty performance car under ₹30 lakh",
  "Affordable CNG car for daily office commute",
];

function ScoreBar({ label, value, max = 20 }: { label: string; value?: number; max?: number }) {
  if (!value || value === 0) return null;
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span>{value.toFixed(1)}/{max}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: "var(--gradient-primary)" }}
        />
      </div>
    </div>
  );
}

function CarCard({
  car,
  onCompare,
  onDetail,
  index,
}: {
  car: CarRecommendation;
  onCompare: (id: number) => void;
  onDetail: (car: CarRecommendation) => void;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const scoreColor =
    car.suitability_score >= 85
      ? "text-green-400"
      : car.suitability_score >= 70
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md flex flex-col"
    >
      {/* Image */}
      <div className="relative aspect-[16/9] bg-muted">
        {car.image ? (
          <img
            src={car.image}
            alt={`${car.brand} ${car.model}`}
            className="h-full w-full object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="grid h-full place-items-center text-xs text-muted-foreground">
            <Bot className="h-8 w-8 opacity-30" />
          </div>
        )}
        {/* Score badge */}
        <div
          className={`absolute right-2 top-2 flex items-center gap-1 rounded-lg bg-black/70 px-2 py-1 text-xs font-bold backdrop-blur ${scoreColor}`}
        >
          <Star className="h-3 w-3" />
          {car.suitability_score.toFixed(0)}% Match
        </div>
        {/* Status badge */}
        {car.status === "UPCOMING" && (
          <div className="absolute left-2 top-2 rounded-md bg-amber-500/90 px-2 py-0.5 text-[10px] font-semibold text-black">
            UPCOMING
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 space-y-3 p-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{car.brand}</div>
          <div className="text-base font-bold leading-tight">{car.model}</div>
          <div className="truncate text-xs text-muted-foreground">{car.variant}</div>
        </div>

        <div className="text-xl font-extrabold text-primary">
          {formatINR(car.price)}
          <span className="ml-1 text-[10px] font-normal text-muted-foreground">{car.price_basis}</span>
        </div>

        {/* Key specs grid */}
        <div className="grid grid-cols-2 gap-1.5 text-[11px] text-muted-foreground">
          {car.fuel_type && (
            <div className="flex items-center gap-1">
              <Fuel className="h-3 w-3 text-accent" />
              {car.fuel_type}
            </div>
          )}
          {car.transmission && (
            <div className="flex items-center gap-1">
              <Settings2 className="h-3 w-3 text-accent" />
              {car.transmission}
            </div>
          )}
          {car.mileage ? (
            <div className="flex items-center gap-1">
              <Gauge className="h-3 w-3 text-accent" />
              {car.mileage} km/l
            </div>
          ) : null}
          {car.safety_rating ? (
            <div className="flex items-center gap-1">
              <Shield className="h-3 w-3 text-accent" />
              {car.safety_rating}★ Safety
            </div>
          ) : null}
          {car.seating_capacity && (
            <div className="flex items-center gap-1">
              <Users className="h-3 w-3 text-accent" />
              {car.seating_capacity} Seater
            </div>
          )}
          {car.power ? (
            <div className="flex items-center gap-1">
              <Zap className="h-3 w-3 text-accent" />
              {car.power} BHP
            </div>
          ) : null}
        </div>

        {/* Matched requirements */}
        {car.matched_requirements.length > 0 && (
          <div className="space-y-1 border-t border-white/5 pt-2">
            {car.matched_requirements.slice(0, 2).map((r, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                {r}
              </div>
            ))}
          </div>
        )}

        {/* Expandable details */}
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center justify-between text-[11px] text-muted-foreground hover:text-foreground border-t border-white/5 pt-2"
        >
          <span>More details</span>
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden space-y-3"
            >
              {/* Score breakdown */}
              {car.score_breakdown && Object.keys(car.score_breakdown).length > 0 && (
                <div className="space-y-1.5 rounded-xl bg-white/5 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Score Breakdown
                  </div>
                  {Object.entries(car.score_breakdown).map(([k, v]) => (
                    <ScoreBar key={k} label={k} value={v} />
                  ))}
                </div>
              )}

              {/* Strengths */}
              {car.strengths.length > 0 && (
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-3">
                  <div className="text-[10px] font-semibold text-primary mb-1">Strengths</div>
                  {car.strengths.map((s, i) => (
                    <div key={i} className="text-[11px] text-muted-foreground flex items-start gap-1.5">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      {s}
                    </div>
                  ))}
                </div>
              )}

              {/* Trade-offs */}
              {car.trade_offs.length > 0 && (
                <div className="rounded-xl bg-amber-500/5 border border-amber-500/10 p-3">
                  <div className="text-[10px] font-semibold text-amber-400 mb-1">Trade-offs</div>
                  {car.trade_offs.map((t, i) => (
                    <div key={i} className="text-[11px] text-muted-foreground flex items-start gap-1.5">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                      {t}
                    </div>
                  ))}
                </div>
              )}

              {/* Missing data */}
              {car.missing_data.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {car.missing_data.map((m, i) => (
                    <span
                      key={i}
                      className="rounded-full bg-white/5 border border-white/10 px-2 py-0.5 text-[10px] text-muted-foreground"
                    >
                      {m}: N/A
                    </span>
                  ))}
                </div>
              )}

              {/* Features */}
              <div className="flex flex-wrap gap-1.5">
                {car.sunroof && (
                  <span className="rounded-full bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 text-[10px] text-blue-400">
                    Sunroof
                  </span>
                )}
                {car.adas && (
                  <span className="rounded-full bg-green-500/10 border border-green-500/20 px-2 py-0.5 text-[10px] text-green-400">
                    ADAS
                  </span>
                )}
                {car.carplay_androidauto && (
                  <span className="rounded-full bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 text-[10px] text-purple-400">
                    CarPlay / AA
                  </span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Action buttons */}
      <div className="grid grid-cols-2 gap-2 border-t border-white/5 bg-white/5 p-3">
        <button
          onClick={() => onCompare(car.id)}
          className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 py-2 text-[11px] font-semibold hover:bg-white/10 transition-colors"
        >
          <GitCompare className="h-3.5 w-3.5" />
          Compare
        </button>
        <button
          onClick={() => onDetail(car)}
          className="flex items-center justify-center gap-1.5 rounded-lg border border-primary/20 bg-primary/10 py-2 text-[11px] font-semibold text-primary hover:bg-primary/20 transition-colors"
        >
          <Info className="h-3.5 w-3.5" />
          Details
        </button>
      </div>
    </motion.div>
  );
}

function PreferenceChip({
  label,
  value,
  onRemove,
}: {
  label: string;
  value: string;
  onRemove?: () => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[11px] text-primary">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">{value}</span>
      {onRemove && (
        <button onClick={onRemove} className="ml-0.5 rounded-full hover:text-foreground">
          <X className="h-2.5 w-2.5" />
        </button>
      )}
    </div>
  );
}

function ActivePreferences({ prefs }: { prefs: Record<string, unknown> }) {
  const chips: { label: string; value: string }[] = [];

  if (prefs.budget_max) chips.push({ label: "Max Budget", value: formatINR(prefs.budget_max as number) });
  if (prefs.budget_min) chips.push({ label: "Min Budget", value: formatINR(prefs.budget_min as number) });
  if (prefs.fuel_type) chips.push({ label: "Fuel", value: prefs.fuel_type as string });
  if (prefs.transmission) chips.push({ label: "Transmission", value: prefs.transmission as string });
  if (prefs.body_type) chips.push({ label: "Body", value: prefs.body_type as string });
  if (prefs.minimum_seating) chips.push({ label: "Seats", value: `${prefs.minimum_seating}+` });
  if (prefs.vehicle_status && prefs.vehicle_status !== "CURRENT")
    chips.push({ label: "Status", value: prefs.vehicle_status as string });
  if (Array.isArray(prefs.preferred_brands) && (prefs.preferred_brands as string[]).length > 0)
    chips.push({ label: "Brand", value: (prefs.preferred_brands as string[]).join(", ") });
  if (prefs.is_luxury) chips.push({ label: "Segment", value: "Luxury" });
  if (prefs.priority) chips.push({ label: "Priority", value: (prefs.priority as string).charAt(0).toUpperCase() + (prefs.priority as string).slice(1) });

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 px-4 pb-2">
      {chips.map((c) => (
        <PreferenceChip key={c.label} label={c.label} value={c.value} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

function FinderPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      text: "Hi! I'm your AI Car Finder. Tell me what you're looking for — budget, family size, fuel preference, driving style — and I'll find the perfect car for you.\n\nYou can also refine your search conversationally. Try something like:",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedCar, setSelectedCar] = useState<CarRecommendation | null>(null);
  const [currentPrefs, setCurrentPrefs] = useState<Record<string, unknown>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;
      const userText = text.trim();
      setInput("");
      setMessages((m) => [...m, { role: "user", text: userText }]);
      setLoading(true);

      try {
        const resp = await api.post<FinderResponse>("/finder", {
          message: userText,
          session_id: sessionId || undefined,
          reset_session: false,
        });

        const data = resp.data;
        if (!sessionId && data.session_id) setSessionId(data.session_id);
        if (data.preferences) setCurrentPrefs(data.preferences);

        setMessages((m) => [
          ...m,
          {
            role: "ai",
            text: data.ai_response || "Here are my top recommendations:",
            recommendations: data.recommendations,
            hasResults: data.recommendations.length > 0,
            sessionId: data.session_id,
            preferences: data.preferences,
          },
        ]);
      } catch (err: any) {
        const detail =
          err?.response?.data?.detail ||
          "Sorry, I couldn't reach the server. Please ensure the AutoAI backend is running on http://localhost:8000.";
        setMessages((m) => [...m, { role: "ai", text: detail }]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, sessionId]
  );

  const handleCompare = (carId: number) => {
    const saved: number[] = JSON.parse(localStorage.getItem("compare") || "[]");
    if (!saved.includes(carId)) {
      if (saved.length >= 2) saved[1] = carId;
      else saved.push(carId);
      localStorage.setItem("compare", JSON.stringify(saved));
    }
    navigate({ to: "/compare" });
  };

  const handleReset = async () => {
    if (sessionId) {
      try {
        await api.delete(`/finder/session/${sessionId}`);
      } catch {
        // ignore
      }
    }
    setSessionId(null);
    setCurrentPrefs({});
    setMessages([
      {
        role: "ai",
        text: "Session reset! Tell me what kind of car you're looking for.",
      },
    ]);
  };

  const hasActiveFilters = Object.keys(currentPrefs).some(
    (k) =>
      currentPrefs[k] !== null &&
      currentPrefs[k] !== undefined &&
      currentPrefs[k] !== false &&
      currentPrefs[k] !== "CURRENT" &&
      !["city_drive", "highway_drive", "family_friendly", "budget_flexible"].includes(k)
  );

  return (
    <div className="flex h-[calc(100vh-160px)] flex-col gap-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pb-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-xl"
              style={{ background: "var(--gradient-primary)" }}
            >
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            AI Car Finder
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Describe your needs in plain language — refine conversationally
          </p>
        </div>
        {hasActiveFilters && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
        )}
      </div>

      {/* Active filters */}
      <AnimatePresence>
        {hasActiveFilters && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <ActivePreferences prefs={currentPrefs} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md"
      >
        <div className="space-y-5 p-4 sm:p-6">
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              {/* Avatar */}
              <div
                className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${
                  msg.role === "user"
                    ? "bg-primary/20 text-primary"
                    : "bg-accent/20 text-accent"
                }`}
              >
                {msg.role === "user" ? (
                  <UserIcon className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </div>

              {/* Bubble */}
              <div
                className={`max-w-[85%] space-y-4 rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-primary/15 text-foreground"
                    : "bg-white/5 border border-white/10"
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

                {/* Example prompts on first AI message */}
                {i === 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {EXAMPLE_PROMPTS.map((p, j) => (
                      <button
                        key={j}
                        onClick={() => sendMessage(p)}
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] hover:bg-white/10 hover:border-primary/30 transition-all text-left text-muted-foreground hover:text-foreground"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}

                {/* Recommendation cards */}
                {msg.recommendations && msg.recommendations.length > 0 && (
                  <div>
                    <div className="mb-3 text-xs text-muted-foreground">
                      Showing top {msg.recommendations.length} recommendation
                      {msg.recommendations.length !== 1 ? "s" : ""}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      {msg.recommendations.map((car, idx) => (
                        <CarCard
                          key={car.id}
                          car={car}
                          index={idx}
                          onCompare={handleCompare}
                          onDetail={setSelectedCar}
                        />
                      ))}
                    </div>

                    {/* Refinement suggestions */}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {[
                        "Show more options",
                        "Compare top 3",
                        "Prioritize safety",
                        "Show cheaper alternatives",
                        "Find automatics only",
                      ].map((s) => (
                        <button
                          key={s}
                          onClick={() => sendMessage(s)}
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] hover:bg-white/10 hover:border-primary/30 transition-all text-muted-foreground hover:text-foreground"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* No results with alternatives */}
                {msg.hasResults === false &&
                  msg.role === "ai" &&
                  (msg as any).alternative_suggestions?.length > 0 && (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
                        <AlertCircle className="h-3.5 w-3.5" />
                        Try adjusting:
                      </div>
                      {((msg as any).alternative_suggestions as string[]).slice(0, 3).map(
                        (s: string, i: number) => (
                          <div key={i} className="text-[11px] text-muted-foreground flex gap-1.5 items-start">
                            <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                            {s}
                          </div>
                        )
                      )}
                    </div>
                  )}
              </div>
            </motion.div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3"
            >
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent/20 text-accent">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-muted-foreground">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                Finding the best cars for you…
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="pt-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            id="finder-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
            placeholder="e.g. Safe 7-seater SUV under ₹20 lakh, automatic, petrol…"
            className="input flex-1 rounded-xl"
            disabled={loading}
          />
          <button
            id="finder-send-btn"
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-40 transition-opacity"
            style={{ background: "var(--gradient-primary)" }}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-muted-foreground">
          Prices shown are ex-showroom. Add approx. 10-15% for on-road costs.
        </p>
      </div>

      {/* Car detail modal */}
      <AnimatePresence>
        {selectedCar && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-2xl max-h-[88vh] overflow-y-auto rounded-3xl border border-white/10 bg-background p-6 shadow-2xl space-y-4"
            >
              <button
                onClick={() => setSelectedCar(null)}
                className="absolute right-4 top-4 z-10 rounded-full border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>

              {/* Header */}
              <div className="flex gap-4 items-start">
                {selectedCar.image && (
                  <div className="h-20 w-28 shrink-0 overflow-hidden rounded-xl bg-muted">
                    <img
                      src={selectedCar.image}
                      alt={selectedCar.model}
                      className="h-full w-full object-cover"
                    />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">{selectedCar.brand}</div>
                  <h2 className="text-xl font-bold leading-tight">{selectedCar.model}</h2>
                  <div className="text-sm text-muted-foreground truncate">{selectedCar.variant}</div>
                  <div className="mt-2 text-2xl font-extrabold text-primary">{formatINR(selectedCar.price)}</div>
                  <div className="text-[10px] text-muted-foreground">{selectedCar.price_basis} Price</div>
                </div>
              </div>

              {/* Suitability score */}
              <div className="rounded-xl bg-white/5 border border-white/10 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold">Suitability Score</span>
                  <span
                    className={`text-2xl font-extrabold ${
                      selectedCar.suitability_score >= 85
                        ? "text-green-400"
                        : selectedCar.suitability_score >= 70
                          ? "text-yellow-400"
                          : "text-red-400"
                    }`}
                  >
                    {selectedCar.suitability_score.toFixed(0)}/100
                  </span>
                </div>
                <div className="h-2 rounded-full bg-white/10">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${selectedCar.suitability_score}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full"
                    style={{ background: "var(--gradient-primary)" }}
                  />
                </div>
              </div>

              {/* Specs grid */}
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 border-t border-white/10 pt-4">
                {[
                  { label: "Fuel Type", value: selectedCar.fuel_type },
                  { label: "Transmission", value: selectedCar.transmission },
                  { label: "Seating", value: selectedCar.seating_capacity ? `${selectedCar.seating_capacity} Seater` : undefined },
                  { label: "Mileage", value: selectedCar.mileage ? `${selectedCar.mileage} km/l` : undefined },
                  { label: "Power", value: selectedCar.power ? `${selectedCar.power} BHP` : undefined },
                  { label: "Safety", value: selectedCar.safety_rating ? `${selectedCar.safety_rating}★` : undefined },
                  { label: "Engine", value: selectedCar.engine_cc ? `${selectedCar.engine_cc} cc` : undefined },
                  { label: "Boot Space", value: selectedCar.boot_space ? `${selectedCar.boot_space} L` : undefined },
                  { label: "Ground Clearance", value: selectedCar.ground_clearance ? `${selectedCar.ground_clearance} mm` : undefined },
                  { label: "Sunroof", value: selectedCar.sunroof !== undefined ? (selectedCar.sunroof ? "Yes" : "No") : undefined },
                  { label: "ADAS", value: selectedCar.adas !== undefined ? (selectedCar.adas ? "Yes" : "No") : undefined },
                  { label: "Touchscreen", value: selectedCar.touchscreen_inches ? `${selectedCar.touchscreen_inches}"` : undefined },
                ].map(({ label, value }) =>
                  value ? (
                    <div key={label}>
                      <div className="text-xs text-muted-foreground">{label}</div>
                      <div className="font-semibold">{value}</div>
                    </div>
                  ) : null
                )}
              </div>

              {/* Matched requirements */}
              {selectedCar.matched_requirements.length > 0 && (
                <div className="rounded-xl bg-primary/5 border border-primary/10 p-3">
                  <div className="text-xs font-semibold text-primary mb-2">Why this matches your requirements</div>
                  {selectedCar.matched_requirements.map((r, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      {r}
                    </div>
                  ))}
                </div>
              )}

              {/* Pros/Cons */}
              {(selectedCar.pros || selectedCar.cons) && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {selectedCar.pros && (
                    <div className="rounded-xl bg-green-500/5 border border-green-500/10 p-3">
                      <div className="text-xs font-semibold text-green-400 mb-1">Pros</div>
                      <p className="text-xs leading-relaxed text-muted-foreground">{selectedCar.pros}</p>
                    </div>
                  )}
                  {selectedCar.cons && (
                    <div className="rounded-xl bg-red-500/5 border border-red-500/10 p-3">
                      <div className="text-xs font-semibold text-red-400 mb-1">Cons</div>
                      <p className="text-xs leading-relaxed text-muted-foreground">{selectedCar.cons}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Ideal for */}
              {selectedCar.ideal_for && (
                <div className="border-t border-white/10 pt-3">
                  <div className="text-xs text-muted-foreground">Ideal For</div>
                  <p className="text-sm font-medium">{selectedCar.ideal_for}</p>
                </div>
              )}

              {/* Missing data disclaimer */}
              {selectedCar.missing_data.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-amber-400">
                    <AlertCircle className="h-3.5 w-3.5" />
                    Specification not available in database: {selectedCar.missing_data.join(", ")}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-4">
                <button
                  onClick={() => handleCompare(selectedCar.id)}
                  className="flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 py-2.5 text-sm font-semibold hover:bg-white/10 transition-colors"
                >
                  <GitCompare className="h-4 w-4" />
                  Add to Compare
                </button>
                <button
                  onClick={() => setSelectedCar(null)}
                  className="flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-primary-foreground"
                  style={{ background: "var(--gradient-primary)" }}
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
