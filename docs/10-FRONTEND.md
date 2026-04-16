# 10 — Frontend

## Overview

The frontend is a **single-page application (SPA)** built with React 18, Vite, and Tailwind CSS. It communicates with the FastAPI backend via HTTP fetch calls. There is no client-side routing complexity — the app has one main page (`Index.tsx`) and a 404 fallback.

---

## Stack

| Technology | Version | Role |
|------------|---------|------|
| React | 18 | UI framework |
| TypeScript | 5 | Static typing |
| Vite + SWC | latest | Build tool + fast JS compiler |
| Tailwind CSS | 3 | Utility-first styling |
| shadcn/ui | latest | Pre-built Radix UI component wrappers |
| Framer Motion | latest | Animations and transitions |
| react-markdown | latest | Renders LLM markdown output |
| next-themes | latest | Dark/light theme management |
| react-router-dom | 6 | Client-side routing |
| @tanstack/react-query | 5 | (Available, not heavily used currently) |

---

## Entry Points

### `index.html`
```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

### `src/main.tsx`
```tsx
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(<App />)
```

### `src/App.tsx`
```tsx
import { ThemeProvider } from 'next-themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Index from './pages/Index'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
```

---

## Global Styling (`src/index.css`)

### Dark Theme Background
```css
body {
  background-color: hsl(228 35% 4%);    /* Very dark blue-black */
  background-image:
    radial-gradient(ellipse 140% 80% at 15% 20%, hsl(263 70% 50% / 0.12) 0%, transparent 60%),
    radial-gradient(ellipse 100% 60% at 85% 80%, hsl(196 80% 50% / 0.08) 0%, transparent 55%),
    radial-gradient(ellipse 80% 90% at 50% 50%, hsl(263 60% 30% / 0.06) 0%, transparent 70%);
}
```

### Ambient Orbs (in `Index.tsx`)
Three absolute-positioned `div`s with:
- Large radial gradient blobs (600–900px, blur 90–110px)
- Slow floating animation via `animate-blob` keyframes
- Different hues (primary purple + accent teal) at different offsets
- Vignette overlay (dark center-fade radial gradient)

### Keyframe Animations
```css
@keyframes blob-drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%       { transform: translate(30px, -50px) scale(1.05); }
  66%       { transform: translate(-20px, 20px) scale(0.95); }
}

@keyframes ring-pulse {
  0%, 100% { opacity: 0.15; transform: scale(1); }
  50%      { opacity: 0.35; transform: scale(1.08); }
}

@keyframes typing-dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
  40%           { transform: scale(1); opacity: 1; }
}
```

### Glassmorphism Classes
```css
.glass {
  background: hsl(228 35% 8% / 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid hsl(228 30% 18% / 0.6);
  border-radius: 16px;
}

.glass-strong {
  background: hsl(228 35% 10% / 0.85);
  backdrop-filter: blur(32px) saturate(200%);
  border: 1px solid hsl(228 30% 22% / 0.7);
}
```

### CSS Custom Properties (Dark Mode)
Defined in `:root` and `.dark`:
```css
:root {
  --background: 228 35% 4%;
  --foreground: 220 20% 92%;
  --primary: 263 70% 65%;       /* Purple */
  --accent: 196 80% 55%;        /* Cyan/teal */
  --muted: 228 25% 14%;
  --border: 228 25% 18%;
  /* ... more semantic tokens */
}
```

---

## Component Architecture

```
App.tsx
└── Index.tsx (main page)
    ├── Background (orbs + dot grid) — inline divs in JSX
    ├── StatsBar.tsx (top)
    ├── ThemeToggle.tsx (top-right)
    ├── AppSidebar.tsx (left panel)
    └── Main content area (scrollable)
        ├── WelcomeMessage.tsx (when no messages)
        └── ChatMessage.tsx[] (when messages exist)
            └── SourceCard.tsx (collapsible sources per message)
    └── ChatInput.tsx (bottom, sticky)
```

---

## Component: `WelcomeMessage.tsx`

Shown when the conversation is empty. Features:
- Animated brain/ring visualization (3 pulsing concentric rings via Framer Motion)
- Title: "Your AI Knowledge Base"
- Feature pills in 5 categories with color coding:
  - Documents (blue)
  - Images (purple)
  - Bookmarks (amber)
  - URLs (emerald)
  - Notes (rose)
- Staggered entrance animations (spring physics)

```tsx
const features = [
  { icon: FileText, label: "Documents", color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
  { icon: Image, label: "Images", color: "bg-purple-500/10 text-purple-400 border-purple-500/20" },
  // ...
];
```

---

## Component: `StatsBar.tsx`

Top bar showing live knowledge base statistics.

**State:**
```typescript
const [stats, setStats] = useState<StatsResponse | null>(null);
const [status, setStatus] = useState<"checking" | "connected" | "offline">("checking");
const [syncing, setSyncing] = useState(false);
```

**Polling:**
```typescript
useEffect(() => {
  const interval = setInterval(fetchStats, syncing ? 5000 : 30000);
  fetchStats(); // immediate
  return () => clearInterval(interval);
}, [syncing]);
```

**AnimatedCounter:** Each statistic uses a custom component that animates from 0 to the target value over 1200ms using a quadratic easing function:
```typescript
const easeInOut = (t: number) => t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t;
```

---

## Component: `AppSidebar.tsx`

The sidebar handles all data ingestion from the UI.

**Sections:**
1. **Logo/Branding** — InfoStore with gradient text
2. **Quick Actions** — 4 buttons: Sync Bookmarks, Upload File, Add URL, Add Note
3. **Watchdog Control** — Multi-line textarea for paths, Start/Stop buttons
4. **Status indicators** — Loading spinners per operation

**File upload pattern:**
```tsx
const fileInputRef = useRef<HTMLInputElement>(null);

// Hidden input
<input
  ref={fileInputRef}
  type="file"
  accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.webp"
  onChange={handleFileUpload}
  className="hidden"
/>

// Button triggers it
<Button onClick={() => fileInputRef.current?.click()}>Upload File</Button>

const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  await api.storeFile(formData);
};
```

---

## Component: `ChatMessage.tsx`

Renders one message in the conversation. Two exported components:

### `ChatMessageBubble`

**User messages:**
- Right-aligned (`justify-end`)
- Gradient background (primary purple → accent teal)
- White text, plain (no markdown)
- `rounded-br-md` (sharp bottom-right corner for "speech tail" effect)

**Assistant messages:**
- Left-aligned (`justify-start`)
- Bot avatar (7×7 circle with gradient)
- Glassmorphism bubble
- `rounded-bl-md`
- **ReactMarkdown** with custom prose CSS:
  - Code blocks: muted background + accent color text
  - Headings: gradient text
  - Links: accent color, no underline by default
  - Blockquotes: primary/50 border
- **Hover-reveal copy button** (using Tailwind `group` / `group-hover`)
- **Sources section** (collapsible, chevron toggle)
- **CRAG badge** (amber, RefreshCw icon) — shown if `cragTriggered === true`
- **Quality badge** (emerald, BarChart3 icon) — shown if `evaluation` present, displays `F:XX R:XX P:XX` percentages

### `TypingIndicator`
Shown while `isLoading === true`. Three dots animated with `typing-dot` keyframes and staggered 200ms delays.

---

## Component: `SourceCard.tsx`

Displays one retrieved source item.

**Layout:**
```
┌──────────────────────────────────────────┐
│ ▌  [Icon] Title                  [Badge] │  ← left accent bar + type icon + "Best Match" badge
│                                          │
│   "T5 summary text..."                   │  ← summary (shown if showSummary)
│   82% match  ↑ 4.2 rerank               │  ← scores row
│   [tag] [tag] [tag]                      │  ← tag pills
└──────────────────────────────────────────┘
```

**Score display:**
- Distance → similarity percentage: `(1 - distance) * 100`
- Rerank score shown with green text and up-arrow icon
- RRF score shown if available

---

## Component: `ChatInput.tsx`

Auto-expanding textarea with keyboard handling:

```tsx
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
  // Shift+Enter: default behavior (newline)
};

// Auto-resize
useEffect(() => {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px";
}, [value]);
```

---

## API Client: `src/lib/api.ts`

**Timeout handling:**
```typescript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 120_000);  // 2 min
```

**All methods:**
```typescript
export const api = {
  health:         () => apiFetch("/health"),
  stats:          () => apiFetch("/api/stats"),
  chat:           (req) => apiFetch("/api/chat", { method: "POST", body: JSON.stringify(req) }),
  search:         (req) => apiFetch("/api/search", { method: "POST", body: JSON.stringify(req) }),
  storeUrl:       (req) => apiFetch("/api/store/url", { method: "POST", body: JSON.stringify(req) }),
  storeText:      (req) => apiFetch("/api/store/text", { method: "POST", body: JSON.stringify(req) }),
  storeFile:      (formData) => apiFetch("/api/store/file", { method: "POST", body: formData }),
  syncBookmarks:  (req) => apiFetch("/api/bookmarks/sync", { method: "POST", body: JSON.stringify(req) }),
  watchdogStart:  (req) => apiFetch("/api/watchdog/start", { method: "POST", body: JSON.stringify(req) }),
  watchdogStop:   () => apiFetch("/api/watchdog/stop", { method: "POST" }),
};
```

---

## Theme System

Uses `next-themes` with `attribute="class"` strategy. Dark mode is the default.

When dark: `<html class="dark">` is set. All Tailwind `dark:` variants activate.

ThemeToggle component cycles between `dark` and `light` modes using `useTheme()` hook.

---

## Build Configuration

### `vite.config.ts`
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    host: "::",
    port: 5173,
    hmr: { overlay: false }       // Disable error overlay
  },
  resolve: {
    alias: { "@": path.resolve("./src") },
    dedupe: ["react", "react-dom"]  // Prevent duplicate React instances
  }
});
```

### `tailwind.config.ts`
```typescript
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "..." },
        // All colors reference CSS variables for dynamic theming
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "typing-dot": { "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.3" }, "40%": { ... } },
        // ...
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "typing-dot": "typing-dot 1.2s infinite ease-in-out both",
        "blob": "blob-drift 20s infinite ease-in-out",
      }
    }
  }
}
```
