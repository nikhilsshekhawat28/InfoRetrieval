import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Database, FileText, Image, BookmarkIcon, HardDrive, Loader2 } from "lucide-react";

function AnimatedCounter({ value, duration = 1200 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<number>(0);

  useEffect(() => {
    const start = ref.current;
    const diff = value - start;
    if (diff === 0) return;
    const startTime = performance.now();
    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + diff * eased);
      setDisplay(current);
      if (progress < 1) requestAnimationFrame(tick);
      else ref.current = value;
    };
    requestAnimationFrame(tick);
  }, [value, duration]);

  return <span className="tabular-nums font-semibold">{display.toLocaleString()}</span>;
}

interface SyncStatus {
  running: boolean;
  processed: number;
  errors: number;
  total: number;
}

export function StatsBar() {
  const [totalIndexed, setTotalIndexed] = useState(0);
  const [imagesOnDisk, setImagesOnDisk] = useState(0);
  const [docsOnDisk, setDocsOnDisk] = useState(0);
  const [bookmarks, setBookmarks] = useState(0);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [healthy, setHealthy] = useState<boolean | null>(null);

  const fetchData = async () => {
    try {
      const [stats, health] = await Promise.all([
        api.stats().catch(() => null),
        api.health().catch(() => null),
      ]);
      if (stats) {
        setTotalIndexed(stats.total_documents);
        if (stats.file_counts) {
          setImagesOnDisk(stats.file_counts.images_on_disk ?? 0);
          setDocsOnDisk(stats.file_counts.documents_on_disk ?? 0);
          setBookmarks(stats.file_counts.bookmarks ?? 0);
        }
        if ((stats as any).bookmark_sync) {
          setSyncStatus((stats as any).bookmark_sync);
        }
      }
      setHealthy(health?.status === "ok");
    } catch {
      setHealthy(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 5s when syncing, 30s otherwise
    const interval = setInterval(fetchData, syncStatus?.running ? 5000 : 30000);
    return () => clearInterval(interval);
  }, [syncStatus?.running]);

  const totalFiles = imagesOnDisk + docsOnDisk + bookmarks;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-strong flex items-center justify-between px-5 py-2.5 z-50"
      style={{ borderBottom: "1px solid hsl(var(--border))", boxShadow: "0 1px 30px -10px hsl(var(--primary)/0.15)" }}
    >
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold gradient-text">InfoStore</span>
      </div>

      <div className="flex items-center gap-2">
        <div className="stat-pill text-xs border border-primary/20">
          <HardDrive className="h-3 w-3 text-primary" />
          <span className="text-muted-foreground">Total Files</span>
          <AnimatedCounter value={totalFiles} />
        </div>
        <div className="stat-pill text-xs">
          <Image className="h-3 w-3 text-muted-foreground" />
          <span className="text-muted-foreground">Images</span>
          <AnimatedCounter value={imagesOnDisk} />
        </div>
        <div className="stat-pill text-xs">
          <FileText className="h-3 w-3 text-muted-foreground" />
          <span className="text-muted-foreground">Documents</span>
          <AnimatedCounter value={docsOnDisk} />
        </div>
        <div className="stat-pill text-xs">
          <BookmarkIcon className="h-3 w-3 text-muted-foreground" />
          <span className="text-muted-foreground">Bookmarks</span>
          <AnimatedCounter value={bookmarks} />
        </div>

        <span className="text-muted-foreground/40 text-xs">|</span>

        <div className="stat-pill text-xs border border-green-500/20">
          <Database className="h-3 w-3 text-green-400" />
          <span className="text-muted-foreground">Indexed</span>
          <AnimatedCounter value={totalIndexed} />
        </div>

        {syncStatus?.running && (
          <div className="stat-pill text-xs border border-yellow-500/30 animate-pulse">
            <Loader2 className="h-3 w-3 text-yellow-400 animate-spin" />
            <span className="text-yellow-400">
              Syncing {syncStatus.processed}/{syncStatus.total}
            </span>
          </div>
        )}

        <div className="flex items-center gap-1.5 ml-1">
          <span
            className={`h-2 w-2 rounded-full transition-colors duration-500 ${
              healthy === true ? "bg-success shadow-[0_0_6px_hsl(var(--success)/0.6)]" :
              healthy === false ? "bg-destructive shadow-[0_0_6px_hsl(var(--destructive)/0.6)]" :
              "bg-muted-foreground animate-pulse"
            }`}
          />
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {healthy === true ? "Connected" : healthy === false ? "Offline" : "Checking..."}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
