import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  PanelLeftClose,
  PanelLeft,
  RefreshCw,
  Upload,
  Link,
  StickyNote,
  Play,
  Square,
  FolderSearch,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export function AppSidebar() {
  const [open, setOpen] = useState(false);
  const [urlModal, setUrlModal] = useState(false);
  const [noteModal, setNoteModal] = useState(false);
  const [url, setUrl] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteText, setNoteText] = useState("");
  const [watchDirs, setWatchDirs] = useState("");
  const [watchdogRunning, setWatchdogRunning] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSync = async () => {
    setLoading("sync");
    try {
      const res = await api.syncBookmarks();
      toast.success(`Synced ${res.processed} bookmarks (${res.errors} errors)`);
    } catch (e: any) {
      toast.error(e.message || "Sync failed");
    } finally {
      setLoading(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading("file");
    try {
      const res = await api.storeFile(file);
      toast.success(res.message || "File uploaded");
    } catch (err: any) {
      toast.error(err.message || "Upload failed");
    } finally {
      setLoading(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleAddUrl = async () => {
    if (!url.trim()) return;
    setLoading("url");
    try {
      const res = await api.storeUrl(url.trim());
      toast.success(res.message || "URL added");
      setUrl("");
      setUrlModal(false);
    } catch (err: any) {
      toast.error(err.message || "Failed to add URL");
    } finally {
      setLoading(null);
    }
  };

  const handleAddNote = async () => {
    if (!noteText.trim()) return;
    setLoading("note");
    try {
      const res = await api.storeText(noteText.trim(), noteTitle.trim());
      toast.success(res.message || "Note added");
      setNoteTitle("");
      setNoteText("");
      setNoteModal(false);
    } catch (err: any) {
      toast.error(err.message || "Failed to add note");
    } finally {
      setLoading(null);
    }
  };

  const handleWatchdogStart = async () => {
    const dirs = watchDirs.split("\n").map((d) => d.trim()).filter(Boolean);
    if (!dirs.length) { toast.error("Enter at least one directory"); return; }
    setLoading("watchdog");
    try {
      await api.watchdogStart(dirs);
      setWatchdogRunning(true);
      toast.success("Watchdog started");
    } catch (err: any) {
      toast.error(err.message || "Failed to start watchdog");
    } finally {
      setLoading(null);
    }
  };

  const handleWatchdogStop = async () => {
    setLoading("watchdog");
    try {
      await api.watchdogStop();
      setWatchdogRunning(false);
      toast.success("Watchdog stopped");
    } catch (err: any) {
      toast.error(err.message || "Failed to stop");
    } finally {
      setLoading(null);
    }
  };

  const btnClass = "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-sidebar-foreground hover:bg-white/[0.04] hover:text-foreground transition-all duration-200 disabled:opacity-50";

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed top-2.5 left-3 z-[60] glass rounded-lg p-2 hover:border-white/[0.12] transition-all"
      >
        {open ? <PanelLeftClose className="h-4 w-4 text-foreground" /> : <PanelLeft className="h-4 w-4 text-foreground" />}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-background/50 backdrop-blur-sm z-40"
              onClick={() => setOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 bottom-0 w-72 glass-strong z-50 flex flex-col overflow-y-auto scrollbar-thin"
              style={{ borderRight: "1px solid hsl(var(--border))", boxShadow: "4px 0 40px -8px hsl(var(--primary)/0.12)" }}
            >
              <div className="p-5 pt-14">
                <h2 className="text-sm font-semibold gradient-text mb-1">InfoStore</h2>
                <p className="text-xs text-muted-foreground">Knowledge Base Manager</p>
              </div>

              {/* Quick Actions */}
              <div className="px-4 pb-4">
                <h3 className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold mb-3 px-1">Quick Actions</h3>
                <div className="space-y-1">
                  <button className={btnClass} onClick={handleSync} disabled={loading === "sync"}>
                    <RefreshCw className={`h-4 w-4 text-accent ${loading === "sync" ? "animate-spin" : ""}`} />
                    Sync Bookmarks
                  </button>
                  <button className={btnClass} onClick={() => fileRef.current?.click()} disabled={loading === "file"}>
                    <Upload className="h-4 w-4 text-accent" />
                    {loading === "file" ? "Uploading…" : "Upload File"}
                  </button>
                  <input
                    ref={fileRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.doc,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.webp"
                    onChange={handleFileUpload}
                  />
                  <button className={btnClass} onClick={() => setUrlModal(true)}>
                    <Link className="h-4 w-4 text-accent" />
                    Add URL
                  </button>
                  <button className={btnClass} onClick={() => setNoteModal(true)}>
                    <StickyNote className="h-4 w-4 text-accent" />
                    Add Note
                  </button>
                </div>
              </div>

              {/* Watchdog */}
              <div className="px-4 pb-4">
                <h3 className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold mb-3 px-1">Watchdog</h3>
                <textarea
                  value={watchDirs}
                  onChange={(e) => setWatchDirs(e.target.value)}
                  placeholder="Enter directories (one per line)"
                  className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg text-xs p-2.5 text-foreground placeholder:text-muted-foreground/50 resize-none outline-none focus:border-primary/30 transition-colors h-20 font-mono"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      watchdogRunning
                        ? "bg-white/[0.04] text-muted-foreground"
                        : "gradient-accent text-primary-foreground"
                    }`}
                    onClick={handleWatchdogStart}
                    disabled={watchdogRunning || loading === "watchdog"}
                  >
                    <Play className="h-3 w-3" /> Start
                  </button>
                  <button
                    className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      !watchdogRunning
                        ? "bg-white/[0.04] text-muted-foreground"
                        : "bg-destructive/20 text-destructive border border-destructive/30"
                    }`}
                    onClick={handleWatchdogStop}
                    disabled={!watchdogRunning || loading === "watchdog"}
                  >
                    <Square className="h-3 w-3" /> Stop
                  </button>
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* URL Modal */}
      <AnimatePresence>
        {urlModal && (
          <Modal onClose={() => setUrlModal(false)} title="Add URL">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm p-3 text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/30 transition-colors"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleAddUrl()}
            />
            <button
              onClick={handleAddUrl}
              disabled={loading === "url" || !url.trim()}
              className="w-full mt-3 py-2.5 rounded-xl gradient-accent text-primary-foreground text-sm font-medium disabled:opacity-50 transition-all active:scale-[0.98]"
            >
              {loading === "url" ? "Adding…" : "Add URL"}
            </button>
          </Modal>
        )}
      </AnimatePresence>

      {/* Note Modal */}
      <AnimatePresence>
        {noteModal && (
          <Modal onClose={() => setNoteModal(false)} title="Add Note">
            <input
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder="Title"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm p-3 text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/30 transition-colors mb-3"
              autoFocus
            />
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Note content…"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg text-sm p-3 text-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/30 transition-colors resize-none h-32"
            />
            <button
              onClick={handleAddNote}
              disabled={loading === "note" || !noteText.trim()}
              className="w-full mt-3 py-2.5 rounded-xl gradient-accent text-primary-foreground text-sm font-medium disabled:opacity-50 transition-all active:scale-[0.98]"
            >
              {loading === "note" ? "Adding…" : "Add Note"}
            </button>
          </Modal>
        )}
      </AnimatePresence>
    </>
  );
}

function Modal({ children, onClose, title }: { children: React.ReactNode; onClose: () => void; title: string }) {
  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-background/60 backdrop-blur-sm z-[70]"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ type: "spring", damping: 25, stiffness: 400 }}
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90%] max-w-md glass-strong rounded-2xl p-6 z-[80]"
      >
        <h3 className="text-sm font-semibold text-foreground mb-4">{title}</h3>
        {children}
      </motion.div>
    </>
  );
}
