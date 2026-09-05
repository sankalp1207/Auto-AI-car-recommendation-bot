import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Heart, Trash2, LogIn, ShoppingBag } from "lucide-react";
import api, { type WishlistItem, formatINR } from "@/services/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

export const Route = createFileRoute("/wishlist")({ component: WishlistPage });

function WishlistPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get<WishlistItem[]>("/wishlist");
      setItems(Array.isArray(r.data) ? r.data : []);
      setErr("");
    } catch {
      setErr("Please log in to view and synchronize your saved wishlist.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [user]);

  const remove = async (id: number) => {
    try {
      await api.delete(`/wishlist/${id}`);
      toast?.success?.("Removed from wishlist");
      load();
    } catch {
      toast?.error?.("Failed to remove item");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Heart className="h-6 w-6 text-primary" /> My Wishlist
        </h1>
        <span className="text-sm text-muted-foreground">{items.length} saved</span>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-12 text-center text-muted-foreground animate-pulse">
          Loading your saved wishlist…
        </div>
      ) : err ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/5 p-12 text-center space-y-3">
          <LogIn className="h-8 w-8 text-primary" />
          <p className="text-base font-semibold">{err}</p>
          <Link
            to="/login"
            className="rounded-xl px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:scale-105"
            style={{ background: "var(--gradient-primary)" }}
          >
            Go to Login
          </Link>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/5 p-12 text-center space-y-3">
          <ShoppingBag className="h-8 w-8 text-muted-foreground" />
          <p className="text-base font-semibold">No saved cars yet</p>
          <p className="text-sm text-muted-foreground">
            Explore the catalog and click the wishlist heart on any vehicle to save it here.
          </p>
          <Link
            to="/search"
            className="rounded-xl px-4 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
            style={{ background: "var(--gradient-primary)" }}
          >
            Browse Vehicle Catalog
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((w) => (
            <div
              key={w.id}
              className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md flex flex-col justify-between"
            >
              <div>
                <div className="aspect-[16/10] overflow-hidden bg-muted">
                  {w.image || (w as any).image_url ? (
                    <img
                      src={w.image || (w as any).image_url}
                      alt={w.model}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="grid h-full place-items-center text-xs text-muted-foreground">No Image</div>
                  )}
                </div>
                <div className="space-y-2 p-4">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">{w.brand}</div>
                  <div className="font-semibold text-lg">{w.model} <span className="text-xs font-normal text-muted-foreground">{w.variant}</span></div>
                  <div className="text-xl font-bold text-primary">{formatINR(w.price)}</div>
                </div>
              </div>
              <div className="p-4 pt-0">
                <button
                  onClick={() => remove(w.id)}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 py-2 text-sm text-destructive hover:bg-destructive/20 transition-colors"
                >
                  <Trash2 className="h-4 w-4" /> Remove from Wishlist
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}