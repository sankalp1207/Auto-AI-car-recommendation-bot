import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Shield, Plus, Pencil, Trash2, X } from "lucide-react";
import api, { type Car, formatINR } from "@/services/api";
import { toast } from "sonner";

export const Route = createFileRoute("/admin")({ component: AdminPage });

const emptyCar: Partial<Car> = {
  brand: "", model: "", variant: "", ex_showroom_price: 0, body_type: "SUV",
  fuel_type: "Petrol", transmission: "Automatic", engine_cc: 0, power: 0, torque: 0,
  mileage: 0, seating: 5, boot_space: 0, ground_clearance: 0, safety_rating: 0,
  maintenance_cost: 0, resale_rating: 0, city_use: true, highway_use: true,
  family_friendly: true, pros: "", cons: "", image_url: "",
};

function AdminPage() {
  const [cars, setCars] = useState<Car[]>([]);
  const [editing, setEditing] = useState<Partial<Car> | null>(null);
  const [page, setPage] = useState(0);
  const perPage = 10;

  const load = async () => {
    try { const r = await api.get<Car[]>("/admin/cars"); setCars(r.data); }
    catch { const r = await api.get<Car[]>("/cars"); setCars(r.data); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!editing) return;
    try {
      if (editing.id) await api.put(`/admin/cars/${editing.id}`, editing);
      else await api.post("/admin/cars", editing);
      toast?.success?.("Saved");
      setEditing(null);
      load();
    } catch { toast?.error?.("Save failed"); }
  };

  const del = async (id: number) => {
    if (!confirm("Delete this car?")) return;
    await api.delete(`/admin/cars/${id}`);
    toast?.success?.("Deleted");
    load();
  };

  const paged = cars.slice(page * perPage, page * perPage + perPage);
  const totalPages = Math.ceil(cars.length / perPage);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-bold"><Shield className="h-6 w-6 text-primary" /> Admin Panel</h1>
        <button onClick={() => setEditing({ ...emptyCar })} className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold text-primary-foreground" style={{ background: "var(--gradient-primary)" }}>
          <Plus className="h-4 w-4" /> Add Car
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-white/10 bg-white/5 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Brand</th><th className="p-3">Model</th><th className="p-3">Variant</th>
                <th className="p-3">Fuel</th><th className="p-3">Price</th><th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {paged.map((c) => (
                <tr key={c.id} className="border-b border-white/5 last:border-0 hover:bg-white/5">
                  <td className="p-3">{c.brand}</td>
                  <td className="p-3">{c.model}</td>
                  <td className="p-3 text-muted-foreground">{c.variant}</td>
                  <td className="p-3">{c.fuel_type}</td>
                  <td className="p-3 font-semibold text-primary">{formatINR(c.ex_showroom_price)}</td>
                  <td className="p-3 text-right">
                    <div className="inline-flex gap-1">
                      <button onClick={() => setEditing(c)} className="rounded-md p-1.5 hover:bg-white/10"><Pencil className="h-4 w-4" /></button>
                      <button onClick={() => del(c.id)} className="rounded-md p-1.5 text-destructive hover:bg-destructive/10"><Trash2 className="h-4 w-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-white/10 p-3 text-sm">
            <span className="text-muted-foreground">Page {page + 1} of {totalPages}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="rounded-md border border-white/10 px-3 py-1 disabled:opacity-40">Prev</button>
              <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="rounded-md border border-white/10 px-3 py-1 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setEditing(null)}>
          <div onClick={(e) => e.stopPropagation()} className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">{editing.id ? "Edit Car" : "Add Car"}</h2>
              <button onClick={() => setEditing(null)} className="rounded-md p-1 hover:bg-white/10"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {(["brand","model","variant","body_type","fuel_type","transmission","image_url","pros","cons"] as const).map((k) => (
                <label key={k} className="col-span-2 space-y-1 sm:col-span-1">
                  <span className="text-xs text-muted-foreground">{k}</span>
                  <input value={(editing as any)[k] || ""} onChange={(e) => setEditing({ ...editing, [k]: e.target.value })} className="input" />
                </label>
              ))}
              {(["ex_showroom_price","engine_cc","power","torque","mileage","seating","boot_space","ground_clearance","safety_rating","maintenance_cost","resale_rating"] as const).map((k) => (
                <label key={k} className="space-y-1">
                  <span className="text-xs text-muted-foreground">{k}</span>
                  <input type="number" value={(editing as any)[k] ?? 0} onChange={(e) => setEditing({ ...editing, [k]: +e.target.value })} className="input" />
                </label>
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setEditing(null)} className="rounded-lg border border-white/10 px-4 py-2 text-sm">Cancel</button>
              <button onClick={save} className="rounded-lg px-4 py-2 text-sm font-semibold text-primary-foreground" style={{ background: "var(--gradient-primary)" }}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}