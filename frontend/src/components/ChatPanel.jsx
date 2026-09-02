import { useEffect, useRef, useState } from "react";
import { chatSocketUrl } from "../api";

const SUGGESTIONS = [
  "Which result is most urgent?",
  "What could be causing this?",
  "What should I do next?",
];

export default function ChatPanel({ threadId }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState("connecting");
  const [pending, setPending] = useState(false);
  const socketRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (!threadId) return undefined;

    const socket = new WebSocket(chatSocketUrl(threadId));
    socketRef.current = socket;

    socket.onopen = () => setStatus("open");
    socket.onclose = () => setStatus("closed");
    socket.onerror = () => setStatus("error");
    socket.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (payload.type === "status") return;
      setPending(false);
      setMessages((prev) => [
        ...prev,
        { role: payload.type === "error" ? "error" : "assistant", content: payload.content },
      ]);
    };

    return () => socket.close();
  }, [threadId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, pending]);

  function send(text) {
    const question = text.trim();
    if (!question || pending || status !== "open") return;
    socketRef.current?.send(JSON.stringify({ question }));
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setDraft("");
    setPending(true);
  }

  if (!threadId) return null;

  return (
    <section className="chat">
      <header className="chat__head">
        <h2>Ask about these results</h2>
        <span className={`chat__status chat__status--${status}`}>
          {status === "open"
            ? "connected"
            : status === "connecting"
              ? "connecting…"
              : "disconnected"}
        </span>
      </header>

      <div className="chat__log">
        {messages.length === 0 && (
          <div className="chat__empty">
            <p>The assistant already has this panel in context — ask a follow-up question.</p>
            <div className="chat__suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chat__chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, i) => (
          <div key={i} className={`bubble bubble--${message.role}`}>
            {message.content}
          </div>
        ))}

        {pending && (
          <div className="bubble bubble--assistant bubble--pending">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="chat__form"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={status === "open" ? "Ask a follow-up question…" : "Reconnecting…"}
          disabled={status !== "open" || pending}
          aria-label="Your question"
        />
        <button type="submit" className="btn btn--primary" disabled={!draft.trim() || pending}>
          Send
        </button>
      </form>
    </section>
  );
}
