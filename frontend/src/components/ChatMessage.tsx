import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { RefreshCw, BarChart3, Bot, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { SourceCard } from "./SourceCard";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy"
      className="p-1 rounded-md text-muted-foreground/50 hover:text-muted-foreground hover:bg-white/[0.06] transition-all duration-150"
    >
      {copied
        ? <Check className="h-3.5 w-3.5 text-emerald-400" />
        : <Copy className="h-3.5 w-3.5" />
      }
    </button>
  );
}

export function ChatMessageBubble({ message }: { message: ChatMessageType }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isUser = message.role === "user";
  const sources = message.sources || [];
  const searchResults = message.searchResults || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5 group`}
    >
      {/* AI avatar */}
      {!isUser && (
        <div className="flex-shrink-0 h-7 w-7 rounded-full ai-avatar flex items-center justify-center mr-2.5 mt-1">
          <Bot className="h-3.5 w-3.5 text-white" />
        </div>
      )}

      <div className={`${isUser ? "max-w-[72%]" : "max-w-[82%]"}`}>
        <div
          className={`message-bubble relative ${
            isUser
              ? "gradient-accent text-primary-foreground rounded-br-md shadow-lg"
              : "glass rounded-bl-md"
          }`}
          style={isUser ? {
            boxShadow: "0 4px 20px -4px hsl(var(--primary) / 0.35)"
          } : undefined}
        >
          {isUser ? (
            <p className="text-base whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-base max-w-none
              dark:prose-invert
              prose-p:leading-relaxed prose-p:mb-2 prose-p:text-foreground
              prose-code:bg-muted/60 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-accent prose-code:font-mono prose-code:text-sm
              prose-pre:bg-muted/40 prose-pre:border prose-pre:border-border prose-pre:rounded-lg
              prose-headings:gradient-text prose-headings:font-semibold
              prose-a:text-accent prose-a:no-underline hover:prose-a:underline
              prose-strong:text-foreground prose-strong:font-semibold
              prose-ul:my-1.5 prose-li:my-0.5
              prose-blockquote:border-l-primary/50 prose-blockquote:text-muted-foreground">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Timestamp + copy button row */}
        <div className={`flex items-center gap-1.5 mt-1.5 px-1 ${isUser ? "justify-end" : "justify-start"}`}>
          <span className="text-[10px] text-muted-foreground/40">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-150">
            <CopyButton text={message.content} />
          </span>
        </div>

        {/* CRAG + Evaluation badges */}
        {!isUser && (message.cragTriggered || message.evaluation) && (
          <div className="flex items-center gap-2 mt-1 px-1">
            {message.cragTriggered && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <RefreshCw className="h-2.5 w-2.5" />
                CRAG rewrite
              </span>
            )}
            {message.evaluation && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <BarChart3 className="h-2.5 w-2.5" />
                Quality: {(message.evaluation.overall * 100).toFixed(0)}%
                {" "}(F:{(message.evaluation.faithfulness * 100).toFixed(0)}
                {" "}R:{(message.evaluation.answer_relevancy * 100).toFixed(0)}
                {" "}P:{(message.evaluation.context_precision * 100).toFixed(0)})
              </span>
            )}
          </div>
        )}

        {/* Sources section with toggle */}
        {!isUser && sources.length > 0 && (
          <div className="mt-2 px-1">
            <button
              onClick={() => setSourcesOpen(!sourcesOpen)}
              className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70 hover:text-muted-foreground transition-colors py-0.5"
            >
              {sourcesOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {sources.length} source{sources.length > 1 ? "s" : ""}
            </button>
            <AnimatePresence>
              {sourcesOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                  className="overflow-hidden"
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                    {sources.map((r, i) => (
                      <SourceCard key={r.id || i} source={r} showSummary highlighted={i === 0} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Search Results: top match highlighted */}
        {searchResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col gap-2 mt-3 px-1"
          >
            <SourceCard source={searchResults[0]} showSummary highlighted />
            {searchResults.length > 1 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {searchResults.slice(1).map((r, i) => (
                  <SourceCard key={r.id || i} source={r} showSummary />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-start mb-5"
    >
      <div className="flex-shrink-0 h-7 w-7 rounded-full ai-avatar flex items-center justify-center mr-2.5 mt-1">
        <Bot className="h-3.5 w-3.5 text-white" />
      </div>
      <div className="glass message-bubble rounded-bl-md flex items-center gap-2 py-4 px-5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full gradient-accent animate-typing-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </motion.div>
  );
}
