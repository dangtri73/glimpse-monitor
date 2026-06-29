"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

type TarotTypeId = "general" | "love" | "yes-no" | "daily" | "one-card" | "three-card";

type TarotType = {
  id: TarotTypeId;
  label: string;
  spreadName: string;
  description: string;
  positions: string[];
  accent: string;
};

type TarotCard = {
  id: string;
  name: string;
  roman: string;
  suit: "Major Arcana";
  keywords: string[];
};

type SelectedCard = TarotCard & {
  position: string;
  orientation: "upright" | "reversed";
};

type TarotPayloadCard = {
  id: string;
  name: string;
  position: string;
  orientation: "upright" | "reversed";
  suit: TarotCard["suit"];
  keywords: string[];
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
  pending?: boolean;
};

type ChatStreamChunk = {
  delta?: string;
  done?: boolean;
  model?: string;
  durationMs?: number;
  error?: string;
  detail?: string;
};

const TAROT_TYPES: TarotType[] = [
  {
    id: "general",
    label: "General",
    spreadName: "Five-card path",
    description: "Self-reflection, current pattern, strengths, friction, and potential.",
    positions: ["Where you are now", "What holds you back", "Your strength", "What needs care", "Potential"],
    accent: "#f7c96f",
  },
  {
    id: "love",
    label: "Love",
    spreadName: "Heart mirror",
    description: "Emotional needs, relationship patterns, connection, tension, and next reflection.",
    positions: ["Your heart", "Their energy", "Connection", "Tension", "Next reflection"],
    accent: "#ff8c9a",
  },
  {
    id: "yes-no",
    label: "Yes / No",
    spreadName: "Single signal",
    description: "One-card symbolic signal with nuance and practical caveats.",
    positions: ["Symbolic signal"],
    accent: "#8fc7ff",
  },
  {
    id: "daily",
    label: "Daily",
    spreadName: "Daily focus",
    description: "One card for mood, focus, and gentle action today.",
    positions: ["Today"],
    accent: "#7ce7c7",
  },
  {
    id: "one-card",
    label: "One Card",
    spreadName: "One-card insight",
    description: "A compact reflection for a clear question.",
    positions: ["Core insight"],
    accent: "#d7a6ff",
  },
  {
    id: "three-card",
    label: "Three Card",
    spreadName: "Past, present, next",
    description: "A three-card sequence for context, present energy, and next step.",
    positions: ["Past pattern", "Present energy", "Next step"],
    accent: "#f0dc75",
  },
];

const TAROT_DECK: TarotCard[] = [
  { id: "fool", name: "The Fool", roman: "0", suit: "Major Arcana", keywords: ["beginning", "trust", "leap"] },
  { id: "magician", name: "The Magician", roman: "I", suit: "Major Arcana", keywords: ["will", "tools", "focus"] },
  { id: "high-priestess", name: "The High Priestess", roman: "II", suit: "Major Arcana", keywords: ["intuition", "mystery", "inner voice"] },
  { id: "empress", name: "The Empress", roman: "III", suit: "Major Arcana", keywords: ["growth", "care", "abundance"] },
  { id: "emperor", name: "The Emperor", roman: "IV", suit: "Major Arcana", keywords: ["structure", "authority", "boundaries"] },
  { id: "hierophant", name: "The Hierophant", roman: "V", suit: "Major Arcana", keywords: ["tradition", "learning", "guidance"] },
  { id: "lovers", name: "The Lovers", roman: "VI", suit: "Major Arcana", keywords: ["choice", "values", "union"] },
  { id: "chariot", name: "The Chariot", roman: "VII", suit: "Major Arcana", keywords: ["direction", "discipline", "momentum"] },
  { id: "strength", name: "Strength", roman: "VIII", suit: "Major Arcana", keywords: ["patience", "courage", "gentleness"] },
  { id: "hermit", name: "The Hermit", roman: "IX", suit: "Major Arcana", keywords: ["solitude", "wisdom", "search"] },
  { id: "wheel", name: "Wheel of Fortune", roman: "X", suit: "Major Arcana", keywords: ["cycle", "change", "timing"] },
  { id: "justice", name: "Justice", roman: "XI", suit: "Major Arcana", keywords: ["truth", "balance", "accountability"] },
  { id: "hanged-man", name: "The Hanged Man", roman: "XII", suit: "Major Arcana", keywords: ["pause", "surrender", "new view"] },
  { id: "death", name: "Death", roman: "XIII", suit: "Major Arcana", keywords: ["ending", "release", "renewal"] },
  { id: "temperance", name: "Temperance", roman: "XIV", suit: "Major Arcana", keywords: ["balance", "healing", "integration"] },
  { id: "devil", name: "The Devil", roman: "XV", suit: "Major Arcana", keywords: ["attachment", "shadow", "choice"] },
  { id: "tower", name: "The Tower", roman: "XVI", suit: "Major Arcana", keywords: ["disruption", "truth", "liberation"] },
  { id: "star", name: "The Star", roman: "XVII", suit: "Major Arcana", keywords: ["hope", "renewal", "clarity"] },
  { id: "moon", name: "The Moon", roman: "XVIII", suit: "Major Arcana", keywords: ["uncertainty", "dream", "emotion"] },
  { id: "sun", name: "The Sun", roman: "XIX", suit: "Major Arcana", keywords: ["joy", "vitality", "openness"] },
  { id: "judgement", name: "Judgement", roman: "XX", suit: "Major Arcana", keywords: ["awakening", "calling", "review"] },
  { id: "world", name: "The World", roman: "XXI", suit: "Major Arcana", keywords: ["completion", "integration", "arrival"] },
];

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "Choose a tarot type, draw the cards, then ask for a reading. I will answer through the Glimpse AI service.",
    meta: "Tarot AI",
  },
];

export function EntertainmentShell() {
  const [activeTypeId, setActiveTypeId] = useState<TarotTypeId>("general");
  const [question, setQuestion] = useState("What should I understand about my current path?");
  const [deckOrder, setDeckOrder] = useState(TAROT_DECK);
  const [selectedDraws, setSelectedDraws] = useState<
    { cardIndex: number; orientation: "upright" | "reversed" }[]
  >([]);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [assistantPending, setAssistantPending] = useState(false);

  const activeType = TAROT_TYPES.find((type) => type.id === activeTypeId) ?? TAROT_TYPES[0];
  const selectedCards = useMemo<SelectedCard[]>(
    () =>
      selectedDraws.map((draw, index) => ({
        ...deckOrder[draw.cardIndex],
        position: activeType.positions[index] ?? `Card ${index + 1}`,
        orientation: draw.orientation,
      })),
    [activeType.positions, deckOrder, selectedDraws],
  );
  const requiredCards = activeType.positions.length;
  const readyForReading = question.trim().length > 0 && selectedCards.length === requiredCards;

  function chooseType(typeId: TarotTypeId) {
    setActiveTypeId(typeId);
    setSelectedDraws([]);
  }

  function shuffle() {
    setDeckOrder((current) => shuffleCards(current));
    setSelectedDraws([]);
  }

  function selectCard(cardIndex: number) {
    if (selectedDraws.some((draw) => draw.cardIndex === cardIndex) || selectedDraws.length >= requiredCards) {
      return;
    }

    setSelectedDraws((current) => [
      ...current,
      {
        cardIndex,
        orientation: Math.random() > 0.78 ? "reversed" : "upright",
      },
    ]);
  }

  async function requestReading() {
    if (!readyForReading) return;
    await sendTarotMessage(
      `Please read this ${activeType.label} tarot spread for my question: ${question.trim()}`,
      "reading",
    );
  }

  async function askFollowUp() {
    const prompt = chatInput.trim();
    if (!prompt) return;
    await sendTarotMessage(prompt, "chat");
    setChatInput("");
  }

  async function sendTarotMessage(prompt: string, stage: "reading" | "chat") {
    if (assistantPending) return;

    const tarotSelectedCards = selectedCards.map((card) => ({
      id: card.id,
      name: card.name,
      position: card.position,
      orientation: card.orientation,
      suit: card.suit,
      keywords: card.keywords,
    }));
    const trimmedQuestion = question.trim();
    const modelPrompt = buildTarotModelPrompt(prompt, stage, activeType, trimmedQuestion, tarotSelectedCards);
    const userMessage: ChatMessage = {
      id: newId(),
      role: "user",
      content: prompt,
    };
    const pendingMessage: ChatMessage = {
      id: newId(),
      role: "assistant",
      content: "Reading...",
      pending: true,
      meta: "Tarot AI",
    };
    const modelMessages = [...chatMessages.filter((item) => !item.pending), userMessage]
      .slice(-12)
      .map((item) => ({
        role: item.role,
        content: item.id === userMessage.id ? modelPrompt : item.content,
      }));

    setChatMessages((current) => [...current, userMessage, pendingMessage]);
    setAssistantPending(true);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feature: "tarot",
          message: modelPrompt,
          messages: modelMessages,
          stream: true,
          tarot: {
            stage,
            readingType: activeType.id,
            readingLabel: activeType.label,
            spreadName: activeType.spreadName,
            question: trimmedQuestion,
            selectedCards: tarotSelectedCards,
            retrieval: {
              vectorDb: "qdrant-or-pgvector",
              candidateLimit: 24,
              rerankLimit: 8,
              reranker: "cross-encoder-compatible",
            },
          },
        }),
      });

      if (!response.ok || !response.body) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string; detail?: string };
        updateChatMessage(
          pendingMessage.id,
          `${payload.error ?? "Assistant unavailable"}. ${payload.detail ?? ""}`.trim(),
          "error",
          false,
        );
        return;
      }

      let streamedAnswer = "";
      let finalMeta = "Tarot RAG stream";

      for await (const chunk of readSseChunks(response.body)) {
        if (chunk.error) {
          updateChatMessage(
            pendingMessage.id,
            `${chunk.error}. ${chunk.detail ?? ""}`.trim(),
            "error",
            false,
          );
          return;
        }

        if (chunk.delta) {
          streamedAnswer += chunk.delta;
          updateChatMessage(pendingMessage.id, streamedAnswer, finalMeta, true);
        }

        if (chunk.model || chunk.durationMs) {
          finalMeta = `${chunk.model ?? "model"}${chunk.durationMs ? ` - ${chunk.durationMs} ms` : ""}`;
        }
      }

      updateChatMessage(
        pendingMessage.id,
        streamedAnswer.trim() || "The AI service returned an empty reading.",
        finalMeta,
        false,
      );
    } catch (error) {
      updateChatMessage(
        pendingMessage.id,
        error instanceof Error ? error.message : "Assistant request failed.",
        "error",
        false,
      );
    } finally {
      setAssistantPending(false);
    }
  }

  function updateChatMessage(messageId: string, content: string, meta: string, pending: boolean) {
    setChatMessages((current) =>
      current.map((message) => (message.id === messageId ? { ...message, content, meta, pending } : message)),
    );
  }

  return (
    <main className="entertain-shell">
      <nav className="surface-nav" aria-label="Glimpse sections">
        <a href="/">Monitor</a>
        <a className="active" href="/entertain" aria-current="page">
          Entertain
        </a>
      </nav>

      <section className="entertain-hero">
        <div>
          <p className="eyebrow">Glimpse Entertain</p>
          <h1>Tarot readings with an AI companion.</h1>
          <p>
            Select a spread, draw cards, and continue the conversation through the same local AI service
            used by the monitor.
          </p>
        </div>
        <div className="tarot-orbit" aria-hidden="true">
          {TAROT_DECK.slice(0, 8).map((card, index) => (
            <span key={card.id} style={{ "--orbit-index": index } as CSSProperties}>
              {card.roman}
            </span>
          ))}
        </div>
      </section>

      <section className="entertain-layout">
        <section className="panel tarot-control-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Tarot Type</p>
              <h2>{activeType.spreadName}</h2>
            </div>
            <span>{requiredCards} cards</span>
          </div>

          <div className="tarot-type-grid">
            {TAROT_TYPES.map((type) => (
              <button
                key={type.id}
                className={type.id === activeType.id ? "tarot-type active" : "tarot-type"}
                type="button"
                onClick={() => chooseType(type.id)}
                style={{ "--type-accent": type.accent } as CSSProperties}
              >
                <strong>{type.label}</strong>
                <small>{type.description}</small>
              </button>
            ))}
          </div>

          <label className="tarot-question">
            <span>Question</span>
            <textarea
              maxLength={200}
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a focused question"
            />
            <small>{question.length}/200</small>
          </label>

          <div className="spread-slots">
            {activeType.positions.map((position, index) => {
              const card = selectedCards[index];
              return (
                <article className={card ? "spread-slot filled" : "spread-slot"} key={position}>
                  <small>{position}</small>
                  {card ? (
                    <>
                      <strong>{card.name}</strong>
                      <span>{card.orientation}</span>
                    </>
                  ) : (
                    <strong>Awaiting card</strong>
                  )}
                </article>
              );
            })}
          </div>

          <div className="tarot-actions">
            <button className="primary-button" type="button" onClick={requestReading} disabled={!readyForReading}>
              Start AI reading
            </button>
            <button type="button" onClick={shuffle}>
              Shuffle
            </button>
            <button type="button" onClick={() => setSelectedDraws([])}>
              Clear
            </button>
          </div>
          <p className="tarot-disclaimer">
            18+. Entertainment and self-reflection only. Not medical, legal, financial, or professional advice.
          </p>
        </section>

        <section className="panel tarot-deck-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Draw</p>
              <h2>Major Arcana deck</h2>
            </div>
            <span>
              {selectedCards.length}/{requiredCards}
            </span>
          </div>
          <div className="tarot-deck-grid">
            {deckOrder.map((card, cardIndex) => {
              const selectedIndex = selectedDraws.findIndex((draw) => draw.cardIndex === cardIndex);
              const selected = selectedIndex >= 0;
              return (
                <button
                  className={selected ? "tarot-card selected" : "tarot-card"}
                  type="button"
                  key={card.id}
                  onClick={() => selectCard(cardIndex)}
                  disabled={!selected && selectedDraws.length >= requiredCards}
                  aria-label={selected ? `${card.name}, ${selectedCards[selectedIndex]?.position}` : "Face-down tarot card"}
                >
                  {selected ? (
                    <>
                      <small>{card.roman}</small>
                      <strong>{card.name}</strong>
                      <span>{card.keywords.slice(0, 2).join(" / ")}</span>
                    </>
                  ) : (
                    <>
                      <i />
                      <span>Glimpse Tarot</span>
                    </>
                  )}
                </button>
              );
            })}
          </div>
        </section>

        <TarotChatPanel
          input={chatInput}
          messages={chatMessages}
          pending={assistantPending}
          onAsk={askFollowUp}
          onInputChange={setChatInput}
        />
      </section>
    </main>
  );
}

function TarotChatPanel({
  input,
  messages,
  pending,
  onInputChange,
  onAsk,
}: {
  input: string;
  messages: ChatMessage[];
  pending: boolean;
  onInputChange: (question: string) => void;
  onAsk: () => void;
}) {
  const threadRef = useRef<HTMLDivElement | null>(null);
  const previousMessageCountRef = useRef(messages.length);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;

    const behavior: ScrollBehavior = messages.length > previousMessageCountRef.current ? "smooth" : "auto";
    previousMessageCountRef.current = messages.length;
    thread.scrollTo({ top: thread.scrollHeight, behavior });
  }, [messages]);

  return (
    <section className="panel tarot-chat-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">AI Chat</p>
          <h2>Tarot companion</h2>
        </div>
        <span>ai-service</span>
      </div>
      <div className="chat-thread" aria-live="polite" ref={threadRef}>
        {messages.map((message) => (
          <article
            className={message.role === "user" ? "chat-message user" : "chat-message assistant"}
            key={message.id}
          >
            <small>{message.role === "user" ? "You" : message.meta ?? "Assistant"}</small>
            <p>{message.content}</p>
          </article>
        ))}
      </div>
      <textarea
        value={input}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            onAsk();
          }
        }}
        rows={4}
        placeholder="Ask a follow-up about the spread"
      />
      <button className="primary-button" type="button" onClick={onAsk} disabled={pending || !input.trim()}>
        {pending ? "Reading..." : "Send"}
      </button>
    </section>
  );
}

function shuffleCards(cards: TarotCard[]) {
  const next = [...cards];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
  }
  return next;
}

function buildTarotModelPrompt(
  prompt: string,
  stage: "reading" | "chat",
  activeType: TarotType,
  question: string,
  selectedCards: TarotPayloadCard[],
) {
  if (selectedCards.length === 0) return prompt;

  const cards = selectedCards
    .map(
      (card, index) =>
        `${index + 1}. ${card.position}: ${card.name} (${card.orientation}; keywords: ${
          card.keywords.join(", ") || "none"
        })`,
    )
    .join("\n");
  const instruction =
    stage === "reading"
      ? "Use these selected cards as the basis for the reading."
      : "Use the same selected cards and spread context when answering this follow-up.";

  return [
    prompt,
    "",
    "Selected tarot spread context:",
    `Type: ${activeType.label}`,
    `Spread: ${activeType.spreadName}`,
    `Question: ${question || "not provided"}`,
    "Selected cards:",
    cards,
    instruction,
    "Answer language: Vietnamese. Reply naturally in Vietnamese while preserving card names as needed.",
  ].join("\n");
}

async function* readSseChunks(stream: ReadableStream<Uint8Array>): AsyncGenerator<ChatStreamChunk> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");

        if (!data) continue;
        yield JSON.parse(data) as ChatStreamChunk;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function newId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
