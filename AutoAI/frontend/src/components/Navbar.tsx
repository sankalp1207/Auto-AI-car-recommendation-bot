import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Car, Search, Bot, Sparkles, GitCompare, Heart, Shield, LogOut, User, Target, Rocket, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const links = [
  { to: "/", label: "Dashboard", icon: Car },
  { to: "/search", label: "Catalog", icon: Search },
  { to: "/launches", label: "New Launches", icon: Rocket },
  { to: "/data-quality", label: "Data Quality", icon: ShieldCheck },
  { to: "/chat", label: "AI Assistant", icon: Bot },
  { to: "/finder", label: "Car Finder", icon: Target },
  { to: "/quiz", label: "Quiz", icon: Sparkles },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/wishlist", label: "Wishlist", icon: Heart },
  { to: "/admin", label: "Admin", icon: Shield },
] as const;

export function Navbar() {
  const { user, logout } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="sticky top-0 z-50 border-b border-white/10 bg-background/60 backdrop-blur-xl"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl" style={{ background: "var(--gradient-primary)" }}>
            <Car className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-lg font-bold tracking-tight">
            Auto<span className="text-primary">AI</span>
          </span>
        </Link>

        <div className="hidden items-center gap-1 lg:flex">
          {links.map((l) => {
            const active = pathname === l.to;
            const Icon = l.icon;
            return (
              <Link
                key={l.to}
                to={l.to}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                }`}
              >
                <Icon className="h-4 w-4" />
                {l.label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <div className="hidden items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm sm:flex">
                <User className="h-4 w-4 text-primary" />
                <span className="max-w-[120px] truncate">{user.username}</span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="rounded-lg px-3 py-1.5 text-sm hover:bg-white/5">
                Login
              </Link>
              <Link
                to="/register"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-primary-foreground"
                style={{ background: "var(--gradient-primary)" }}
              >
                Register
              </Link>
            </>
          )}
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto border-t border-white/5 px-4 py-2 lg:hidden">
        {links.map((l) => {
          const active = pathname === l.to;
          return (
            <Link
              key={l.to}
              to={l.to}
              className={`shrink-0 rounded-md px-2.5 py-1 text-xs ${
                active ? "bg-primary/15 text-primary" : "text-muted-foreground"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </div>
    </motion.nav>
  );
}