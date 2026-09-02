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
  const [open, setOpen] = useState(false);
  const socketRef = useRef(null);
  const endRef = useRef(null);

  // Escape closes the panel, as expected for a drawer.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

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
    <>
      {/* Launcher — only rendered while the panel is closed. */}
      {!open && (
        <button type="button" className="chat__launcher" onClick={() => setOpen(true)}>
          <span aria-hidden="true">💬</span> Ask about these results
        </button>
      )}

      {/* Backdrop is only interactive on narrow screens, where the panel overlays. */}
      <div
        className={`chat__scrim${open ? " chat__scrim--on" : ""}`}
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />

      <aside
        className={`chat chat--panel${open ? " chat--open" : ""}`}
        aria-label="Follow-up chat"
        aria-hidden={!open}
      >
        <header className="chat__head">
          <h2>Ask about these results</h2>
          <div className="chat__head-right">
            <span className={`chat__status chat__status--${status}`}>
              {status === "open"
                ? "connected"
                : status === "connecting"
                  ? "connecting…"
                  : "disconnected"}
            </span>
            <button
              type="button"
              className="chat__close"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
            >
              ×
            </button>
          </div>
        </header>

      <div className="chat__log">
        {/* Rendered locally rather than sent by the server: it is a greeting,
            not part of the conversation the agent reasons over. */}
        <div className="bubble bubble--assistant">
          Hi, I am Lab Agent — happy to answer your questions.
        </div>

        {messages.length === 0 && (
          <div className="chat__empty">
            <p>I already have this panel in context — ask me a follow-up question.</p>
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
      </aside>
    </>
  );
}
