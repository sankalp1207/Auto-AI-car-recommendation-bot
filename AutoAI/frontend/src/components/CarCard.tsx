import { motion } from "framer-motion";
import { Fuel, Gauge, Settings2, Heart, GitCompare } from "lucide-react";
import type { Car } from "@/services/api";
import { formatINR } from "@/services/api";

interface Props {
  car: Car;
  onWishlist?: (car: Car) => void;
  onCompare?: (car: Car) => void;
}

export function CarCard({ car, onWishlist, onCompare }: Props) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md transition-shadow hover:shadow-[var(--shadow-glow)]"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-muted">
        {car.image_url || car.image ? (
          <img
            src={car.image_url || car.image}
            alt={`${car.brand} ${car.model}`}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="grid h-full place-items-center text-muted-foreground">No Image</div>
        )}
        <div className="absolute right-2 top-2 flex items-center gap-1.5">
          {car.status === "UPCOMING" && (
            <span className="rounded-md bg-amber-500/80 text-white px-2 py-0.5 text-[10px] font-bold backdrop-blur uppercase tracking-wider">
              Upcoming
            </span>
          )}
          <span className="rounded-md bg-black/60 px-2 py-1 text-xs font-medium backdrop-blur">
            {car.body_type}
          </span>
        </div>
      </div>
      <div className="space-y-3 p-4">
        <div>
          <div className="text-xs text-muted-foreground">{car.brand}</div>
          <h3 className="truncate text-lg font-semibold">
            {car.model} <span className="text-muted-foreground">{car.variant}</span>
          </h3>
        </div>
        <div className="text-2xl font-bold text-primary">
          {car.starting_price && car.ending_price ? (
            `${formatINR(car.starting_price)} - ${formatINR(car.ending_price)}`
          ) : (
            formatINR(car.ex_showroom_price || car.price || 0)
          )}
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1"><Fuel className="h-3 w-3" />{car.fuel_type}</div>
          <div className="flex items-center gap-1"><Settings2 className="h-3 w-3" />{car.transmission}</div>
          <div className="flex items-center gap-1"><Gauge className="h-3 w-3" />{car.mileage} km/l</div>
        </div>
        {(onWishlist || onCompare) && (
          <div className="flex gap-2 pt-2">
            {onWishlist && (
              <button
                onClick={() => onWishlist(car)}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs hover:bg-white/10"
              >
                <Heart className="h-3.5 w-3.5" /> Wishlist
              </button>
            )}
            {onCompare && (
              <button
                onClick={() => onCompare(car)}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs hover:bg-white/10"
              >
                <GitCompare className="h-3.5 w-3.5" /> Compare
              </button>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}