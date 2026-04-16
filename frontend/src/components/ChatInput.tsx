import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [text]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="border-t border-border p-4 glass-strong"
    >
      <div className="max-w-2xl mx-auto flex items-end gap-3">
        <div className="flex-1 glass rounded-2xl flex items-end px-4 py-3 focus-within:border-primary/40 focus-within:[box-shadow:0_0_0_3px_hsl(var(--primary)/0.1),0_0_30px_-8px_hsl(var(--primary)/0.3)] transition-all duration-300">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
            disabled={disabled}
            rows={1}
            className="flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground/60 resize-none outline-none py-1 scrollbar-thin max-h-[150px]"
          />
          <button
            onClick={handleSubmit}
            disabled={disabled || !text.trim()}
            className="flex-shrink-0 ml-2 p-2 rounded-xl gradient-accent text-primary-foreground disabled:opacity-20 hover:opacity-90 transition-all active:scale-95 shadow-lg hover:shadow-primary/30"
            style={{ boxShadow: text.trim() ? "0 4px 14px -4px hsl(var(--primary)/0.5)" : undefined }}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
      <p className="text-center text-[10px] text-muted-foreground/35 mt-2">
        Enter to send · Shift+Enter for new line
      </p>
    </motion.div>
  );
}
