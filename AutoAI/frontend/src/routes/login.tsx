import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { LogIn } from "lucide-react";
import api from "@/services/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export const Route = createFileRoute("/login")({ component: LoginPage });

function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post("/auth/login", { email, password });
      if (r.data.access_token) {
        login(r.data.access_token, { username: r.data.username, email: r.data.email });
        toast?.success?.("Welcome back!");
        navigate({ to: "/" });
      } else {
        toast?.error?.(r.data.message || "Login failed");
      }
    } catch { toast?.error?.("Login failed"); }
    finally { setLoading(false); }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-md">
      <div className="rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl" style={{ background: "var(--gradient-primary)" }}>
            <LogIn className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold">Welcome back</h1>
          <p className="text-sm text-muted-foreground">Log in to continue your car search</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <input type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="input" />
          <input type="password" required placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="input" />
          <button disabled={loading} className="w-full rounded-lg py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50" style={{ background: "var(--gradient-primary)" }}>
            {loading ? "Logging in…" : "Login"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          No account? <Link to="/register" className="text-primary hover:underline">Create one</Link>
        </p>
      </div>
    </motion.div>
  );
}