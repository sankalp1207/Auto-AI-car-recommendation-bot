import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Car as CarIcon, Users, Heart, MessageSquare, ArrowRight, Sparkles } from "lucide-react";
import api, { type Car } from "@/services/api";
import { CarCard } from "@/components/CarCard";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

interface Stats {
  total_cars?: number;
  current_cars?: number;
  upcoming_cars?: number;
  active_users?: number;
  wishlisted_cars?: number;
  ai_chats?: number;
}

function Dashboard() {
  const [stats, setStats] = useState<Stats>({});
  const [featured, setFeatured] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/dashboard/stats")
      .then((r) => setStats(r.data))
      .catch(() => {});
    api.get<Car[]>("/cars")
      .then((r) => setFeatured(r.data.slice(0, 6)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const statCards = [
    { label: "Total Cars", value: stats.total_cars ?? (featured.length || "—"), icon: CarIcon },
    { label: "Current Models", value: stats.current_cars ?? "—", icon: Sparkles },
    { label: "Upcoming Launches", value: stats.upcoming_cars ?? "—", icon: ArrowRight },
    { label: "Wishlisted", value: stats.wishlisted_cars ?? "—", icon: Heart },
  ];

  return (
    <div className="space-y-12">
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-md sm:p-14"
      >
        <div className="absolute inset-0 -z-10 opacity-40" style={{ background: "var(--gradient-glow)" }} />
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
          <Sparkles className="h-3 w-3" /> AI-Powered Discovery
        </div>
        <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
          Find Your Perfect Car <br />
          <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-primary)" }}>
            with AI
          </span>
        </h1>
        <p className="mt-4 max-w-2xl text-muted-foreground">
          Discover, compare, and shortlist your next car with an intelligent assistant tuned to your budget, lifestyle, and priorities.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            to="/quiz"
            className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-primary-foreground"
            style={{ background: "var(--gradient-primary)" }}
          >
            Take the Quiz <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold hover:bg-white/10"
          >
            Ask AI Assistant
          </Link>
        </div>
      </motion.section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {statCards.map((s, i) => {
          const Icon = s.icon;
          return (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Icon className="h-4 w-4 text-primary" /> {s.label}
              </div>
              <div className="mt-2 text-2xl font-bold">{s.value}</div>
            </motion.div>
          );
        })}
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-2xl font-bold">Featured Cars</h2>
          <Link to="/search" className="text-sm text-primary hover:underline">Browse all →</Link>
        </div>
        {loading ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-10 text-center text-muted-foreground animate-pulse">
            Loading featured cars from catalog…
          </div>
        ) : featured.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-10 text-center text-muted-foreground">
            No cars found or unable to connect to the AutoAI backend. Please ensure the server is active.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((c) => <CarCard key={c.id} car={c} />)}
          </div>
        )}
      </section>
    </div>
  );
}