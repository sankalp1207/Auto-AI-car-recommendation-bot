import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Bot, User as UserIcon, X, GitCompare, Info, Gauge, Fuel, Settings2, Shield } from "lucide-react";
import api, { type Recommendation, formatINR } from "@/services/api";
import { useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/chat")({ component: ChatPage });

type Msg = { role: "user" | "ai"; text: string; recs?: Recommendation[] };

function ChatPage() {
  const [sessionId] = useState(() => "session_" + Math.random().toString(36).substring(2, 10));
  const [messages, setMessages] = useState<Msg[]>([
    { role: "ai", text: "Hi! Tell me what kind of car you're looking for — budget, family size, fuel preference, driving style. I'll suggest the best matches." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedCar, setSelectedCar] = useState<Recommendation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setMessages((m) => [...m, { role: "user", text: userMsg }]);
    setInput("");
    setLoading(true);
    try {
      const r = await api.post("/chat", { message: userMsg, session_id: sessionId });
      setMessages((m) => [
        ...m,
        {
          role: "ai",
          text: r.data.ai_response || "Here are the top matches based on your criteria:",
          recs: r.data.recommendations || [],
        },
      ]);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Sorry, I couldn't reach the server. Please ensure the AutoAI backend is reachable.";
      setMessages((m) => [...m, { role: "ai", text: detail }]);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = (carId: number) => {
    const saved: number[] = JSON.parse(localStorage.getItem("compare") || "[]");
    if (saved[0] === carId || saved[1] === carId) {
      // Already added
    } else if (saved.length >= 2) {
      saved[1] = carId;
    } else {
      saved.push(carId);
    }
    localStorage.setItem("compare", JSON.stringify(saved));
    navigate({ to: "/compare" });
  };

  return (
    <div className="flex h-[calc(100vh-180px)] flex-col rounded-3xl border border-white/10 bg-white/5 backdrop-blur-md">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${m.role === "user" ? "bg-primary/20 text-primary" : "bg-accent/20 text-accent"}`}>
              {m.role === "user" ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            <div className={`max-w-[80%] space-y-3 rounded-2xl px-4 py-3 text-sm ${m.role === "user" ? "bg-primary/15 text-foreground" : "bg-white/5 border border-white/10"}`}>
              <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
              {m.recs && m.recs.length > 0 && (
                <div className="flex gap-3 overflow-x-auto pt-2">
                  {m.recs.map((r) => (
                    <div key={r.id} className="w-64 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-background/80 hover:border-primary/40 transition-all flex flex-col justify-between">
                      <div>
                        <div className="relative aspect-[16/10] bg-muted">
                          {r.image || (r as any).image_url ? (
                            <img src={r.image || (r as any).image_url} alt={r.model} className="h-full w-full object-cover" />
                          ) : (
                            <div className="grid h-full place-items-center text-xs text-muted-foreground">No Image</div>
                          )}
                          <div className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium backdrop-blur">
                            Match: {r.score}%
                          </div>
                        </div>
                        <div className="space-y-2 p-3">
                          <div>
                            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{r.brand}</div>
                            <div className="truncate text-sm font-bold">{r.model}</div>
                            <div className="truncate text-[10px] text-muted-foreground">{r.variant}</div>
                          </div>
                          <div className="text-base font-extrabold text-primary">
                            {r.starting_price && r.ending_price ? (
                              `${formatINR(r.starting_price)} - ${formatINR(r.ending_price)}`
                            ) : (
                              formatINR(r.price)
                            )}
                          </div>
                          <div className="grid grid-cols-2 gap-1.5 text-[11px] text-muted-foreground border-t border-white/5 pt-2">
                            <div className="flex items-center gap-1"><Fuel className="h-3.5 w-3.5 text-accent" />{r.fuel_type}</div>
                            <div className="flex items-center gap-1"><Settings2 className="h-3.5 w-3.5 text-accent" />{r.transmission}</div>
                            <div className="flex items-center gap-1"><Gauge className="h-3.5 w-3.5 text-accent" />{r.mileage} kmpl</div>
                            <div className="flex items-center gap-1"><Shield className="h-3.5 w-3.5 text-accent" />{r.safety_rating !== undefined ? `${r.safety_rating} Star` : "N/A"}</div>
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-1.5 p-3 border-t border-white/5 bg-white/5">
                        <button
                          onClick={() => handleCompare(r.id)}
                          className="flex items-center justify-center gap-1 rounded bg-white/5 hover:bg-white/10 border border-white/10 py-1.5 text-[11px] font-semibold text-foreground transition-colors"
                        >
                          <GitCompare className="h-3 w-3" /> Compare
                        </button>
                        <button
                          onClick={() => setSelectedCar(r)}
                          className="flex items-center justify-center gap-1 rounded bg-primary/20 hover:bg-primary/30 border border-primary/20 py-1.5 text-[11px] font-semibold text-primary transition-colors"
                        >
                          <Info className="h-3 w-3" /> Details
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        ))}
        {loading && <div className="text-sm text-muted-foreground">AI is thinking…</div>}
      </div>
      <div className="border-t border-white/10 p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="e.g. Safe family SUV under 15 lakhs, petrol automatic..."
            className="input flex-1"
          />
          <button onClick={send} disabled={loading} className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" style={{ background: "var(--gradient-primary)" }}>
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>

      {selectedCar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-background p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto"
          >
            <button
              onClick={() => setSelectedCar(null)}
              className="absolute right-4 top-4 rounded-full border border-white/10 bg-white/5 p-1.5 hover:bg-white/10"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="flex gap-4 items-center">
              <div className="h-16 w-24 shrink-0 overflow-hidden rounded-lg bg-muted border border-white/5">
                <img src={selectedCar.image || (selectedCar as any).image_url} alt={selectedCar.model} className="h-full w-full object-cover" />
              </div>
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">{selectedCar.brand}</div>
                <h2 className="text-xl font-bold">{selectedCar.model}</h2>
                <div className="text-sm text-muted-foreground">{selectedCar.variant}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 border-t border-white/10 pt-4 text-sm sm:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">Price Range / Ex-Showroom Price</div>
                <div className="font-semibold text-primary">
                  {selectedCar.starting_price && selectedCar.ending_price ? (
                    `${formatINR(selectedCar.starting_price)} - ${formatINR(selectedCar.ending_price)}`
                  ) : (
                    formatINR(selectedCar.price)
                  )}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Fuel Type</div>
                <div className="font-semibold">{selectedCar.fuel_type}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Transmission</div>
                <div className="font-semibold">{selectedCar.transmission}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Engine Capacity</div>
                <div className="font-semibold">{selectedCar.engine_cc ? `${selectedCar.engine_cc} cc` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Power</div>
                <div className="font-semibold">{selectedCar.power ? `${selectedCar.power} BHP` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Torque</div>
                <div className="font-semibold">{selectedCar.torque ? `${selectedCar.torque} Nm` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Mileage</div>
                <div className="font-semibold">{selectedCar.mileage ? `${selectedCar.mileage} kmpl` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Seating Capacity</div>
                <div className="font-semibold">{selectedCar.seating_capacity} Seater</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Boot Space</div>
                <div className="font-semibold">{selectedCar.boot_space ? `${selectedCar.boot_space} Liters` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Ground Clearance</div>
                <div className="font-semibold">{selectedCar.ground_clearance ? `${selectedCar.ground_clearance} mm` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Safety Rating</div>
                <div className="font-semibold">{selectedCar.safety_rating ? `${selectedCar.safety_rating} Star (GNCAP)` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Airbags</div>
                <div className="font-semibold">{selectedCar.airbags || "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Sunroof</div>
                <div className="font-semibold">{selectedCar.sunroof ? "Yes" : selectedCar.sunroof === false ? "No" : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">ADAS</div>
                <div className="font-semibold">{selectedCar.adas ? "Yes" : selectedCar.adas === false ? "No" : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Touchscreen</div>
                <div className="font-semibold">{selectedCar.touchscreen_inches ? `${selectedCar.touchscreen_inches} inches` : "Specification not available in current database"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Wireless CarPlay / Android Auto</div>
                <div className="font-semibold">{selectedCar.carplay_androidauto ? "Yes" : selectedCar.carplay_androidauto === false ? "No" : "Specification not available in current database"}</div>
              </div>
            </div>

            {selectedCar.ideal_for && (
              <div className="border-t border-white/10 pt-3">
                <div className="text-xs text-muted-foreground">Ideal For</div>
                <p className="text-sm font-medium text-foreground/90">{selectedCar.ideal_for}</p>
              </div>
            )}

            {(selectedCar.pros || selectedCar.cons) && (
              <div className="grid gap-3 border-t border-white/10 pt-3 sm:grid-cols-2">
                {selectedCar.pros && (
                  <div className="rounded-xl bg-primary/5 border border-primary/10 p-3">
                    <div className="text-xs font-semibold text-primary mb-1">Pros</div>
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
          </motion.div>
        </div>
      )}
    </div>
  );
}