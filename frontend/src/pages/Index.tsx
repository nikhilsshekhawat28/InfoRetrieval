import { useState, useRef, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { StatsBar } from "@/components/StatsBar";
import { ChatMessageBubble, TypingIndicator } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { AppSidebar } from "@/components/AppSidebar";
import { WelcomeMessage } from "@/components/WelcomeMessage";
import { ThemeToggle } from "@/components/ThemeToggle";

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function Index() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await api.chat(text);
      const assistantMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        evaluation: res.evaluation,
        cragTriggered: res.crag_triggered,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      toast.error(err.message || "Request failed");
      const errorMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "Sorry, I encountered an error processing your request. Please check that the backend is running and try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        {/* Dot grid */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(circle, hsl(263 70% 65% / 0.13) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
        {/* Orbs */}
        <div
          className="absolute top-[-20%] right-[3%] w-[900px] h-[900px] rounded-full bg-primary/[0.18] blur-[110px] animate-blob"
        />
        <div
          className="absolute bottom-[-20%] left-[8%] w-[750px] h-[750px] rounded-full bg-accent/[0.14] blur-[100px] animate-blob"
          style={{ animationDelay: "4s" }}
        />
        <div
          className="absolute top-[30%] left-[-12%] w-[600px] h-[600px] rounded-full bg-primary/[0.10] blur-[90px] animate-blob"
          style={{ animationDelay: "8s" }}
        />
        {/* Vignette — darkens edges to frame the center */}
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse 90% 80% at 50% 50%, transparent 40%, hsl(228 35% 3% / 0.75) 100%)",
          }}
        />
      </div>

      <StatsBar />

      <ThemeToggle />

      <div className="flex-1 flex overflow-hidden relative">
        <AppSidebar />

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin">
            {messages.length === 0 ? (
              <WelcomeMessage />
            ) : (
              <div className="max-w-2xl mx-auto px-6 py-8">
                {messages.map((msg) => (
                  <ChatMessageBubble key={msg.id} message={msg} />
                ))}
                {isLoading && <TypingIndicator />}
              </div>
            )}
          </div>

          {/* Input */}
          <ChatInput
            onSend={handleSend}
            disabled={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
