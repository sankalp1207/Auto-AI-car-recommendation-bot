import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { UserPlus } from "lucide-react";
import api from "@/services/api";
import { toast } from "sonner";

export const Route = createFileRoute("/register")({ component: RegisterPage });

function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post("/auth/register", { username, email, password });
      if (r.data.user) {
        toast?.success?.("Account created! Please log in.");
        navigate({ to: "/login" });
      } else {
        toast?.error?.(r.data.message || "Registration failed");
      }
    } catch { toast?.error?.("Registration failed"); }
    finally { setLoading(false); }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-md">
      <div className="rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl" style={{ background: "var(--gradient-primary)" }}>
            <UserPlus className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold">Create your account</h1>
          <p className="text-sm text-muted-foreground">Save wishlists, get AI-powered picks</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <input required placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} className="input" />
          <input type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="input" />
          <input type="password" required placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="input" />
          <button disabled={loading} className="w-full rounded-lg py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50" style={{ background: "var(--gradient-primary)" }}>
            {loading ? "Creating…" : "Register"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Already have an account? <Link to="/login" className="text-primary hover:underline">Log in</Link>
        </p>
      </div>
    </motion.div>
  );
}