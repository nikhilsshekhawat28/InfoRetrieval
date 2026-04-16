import { motion } from "framer-motion";
import { Brain, FileText, Image, Bookmark, StickyNote, Globe } from "lucide-react";

const features = [
  { icon: FileText, label: "Documents", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/20" },
  { icon: Image, label: "Images", color: "text-purple-400", bg: "bg-purple-400/10 border-purple-400/20" },
  { icon: Bookmark, label: "Bookmarks", color: "text-amber-400", bg: "bg-amber-400/10 border-amber-400/20" },
  { icon: Globe, label: "URLs", color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/20" },
  { icon: StickyNote, label: "Notes", color: "text-rose-400", bg: "bg-rose-400/10 border-rose-400/20" },
];

export function WelcomeMessage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className="flex flex-col items-center justify-center h-full text-center px-6 select-none"
    >
      {/* Brain icon with animated rings */}
      <div className="relative mb-8">
        {/* Outermost ring */}
        <motion.div
          className="absolute inset-0 rounded-full border border-primary/20"
          style={{ margin: "-28px" }}
          animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.1, 0.4] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Middle ring */}
        <motion.div
          className="absolute inset-0 rounded-full border border-accent/25"
          style={{ margin: "-16px" }}
          animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.15, 0.5] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut", delay: 0.6 }}
        />
        {/* Inner ring */}
        <motion.div
          className="absolute inset-0 rounded-full border border-primary/30"
          style={{ margin: "-6px" }}
          animate={{ scale: [1, 1.06, 1], opacity: [0.6, 0.2, 0.6] }}
          transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut", delay: 1.2 }}
        />

        <motion.div
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.6, type: "spring", stiffness: 200 }}
          className="relative h-20 w-20 rounded-2xl ai-avatar flex items-center justify-center"
        >
          <Brain className="h-10 w-10 text-white" />
        </motion.div>
      </div>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.5 }}
        className="text-5xl font-bold text-foreground mb-4 text-balance tracking-tight"
      >
        Your AI Knowledge Base
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45, duration: 0.5 }}
        className="text-base text-muted-foreground max-w-sm leading-relaxed mb-10"
      >
        Ask me anything. I search across your documents, images, bookmarks, and notes to give you precise answers.
      </motion.p>

      <div className="flex flex-wrap justify-center gap-2.5">
        {features.map((f, i) => (
          <motion.div
            key={f.label}
            initial={{ opacity: 0, y: 12, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.55 + i * 0.07, duration: 0.4, type: "spring", stiffness: 260 }}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-full text-xs font-medium border backdrop-blur-sm ${f.bg}`}
          >
            <f.icon className={`h-3.5 w-3.5 ${f.color}`} />
            <span className="text-foreground/80">{f.label}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
