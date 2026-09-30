# Suraksha Sathi — Mine Safety Drill Assistant (LangChain + Groq)

## ⚠️ First: rotate your API key
A Groq key was pasted in plain chat text earlier — treat it as compromised.
Go to https://console.groq.com/keys, revoke it, and generate a new one.
Put the new key only in a local `.env` file (already gitignored via
`.env.example` pattern), never in code or chat.

## How it works

1. **Knowledge base** (`drill_data/*.txt`) — one file per drill (8 total).
   Replace the placeholder files with your real drill content: steps,
   do's/don'ts, scoring, equipment, duration.
2. **Vector store (FAISS)** — the 8 files are chunked and embedded locally
   with `sentence-transformers/all-MiniLM-L6-v2` (free, runs on CPU, no
   API cost) and cached to `vectorstore_index/`.
3. **Relevance gate** — before ever calling the LLM, the app checks the
   similarity score of the best-matching chunk. If it's below
   `RELEVANCE_SCORE_THRESHOLD`, the question is off-topic and the app
   returns the fixed refusal line directly — no LLM call, no chance of
   hallucination, and it's cheaper/faster.
4. **RAG chain (LangChain + Groq)** — for in-scope questions, the top
   chunks are stuffed into the system prompt as `{context}` and
   `ChatGroq` (e.g. `llama-3.3-70b-versatile`) generates the answer,
   constrained by the persona rules in `system_prompt.py`.
5. **Emergency short-circuit** — messages matching real-emergency phrases
   (gas leak, fire, collapse, injury as *real* events) skip the LLM
   entirely and return the fixed emergency-escalation line.
6. **Language matching** — `langdetect` picks English vs Hindi; the
   system prompt also instructs the model to mirror whatever language the
   worker used, including transliterated Hindi.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your NEW (rotated) Groq key
python app.py
```

First run builds the FAISS index from `drill_data/`; later runs load the
cached index. Delete `vectorstore_index/` and rerun after editing drill
content.

## Plugging in voice (STT/TTS)

`app.py`'s `handle_message()` is transport-agnostic — it takes a text
string in, returns a text string out. To make it a voice bot:

- **Speech-to-text**: pipe microphone audio through something like
  `faster-whisper`, Groq's own Whisper endpoint, or a browser
  `SpeechRecognition` API, then pass the transcript into `handle_message`.
- **Text-to-speech**: take the returned string and pass it to a TTS engine
  (e.g. Coqui TTS for offline Hindi/English, Google/Azure TTS, or
  ElevenLabs) — the persona already writes short, punctuation-light,
  spoken-word-friendly sentences for this.
- Wrap the CLI `main()` loop with your real-time audio I/O (e.g. a
  WebSocket server + browser mic capture, or a Flask/FastAPI endpoint
  called by an IVR/kiosk app).

## Tuning notes

- `RELEVANCE_SCORE_THRESHOLD` in `app.py` needs tuning once you load your
  real 8 drills — test with several clearly off-topic questions and
  several genuine drill questions, and pick a cutoff that separates them.
- `current_drill_name` should be updated by your app whenever a worker
  starts a specific drill (e.g. tapped "Drill 3" on a kiosk), so refusal
  messages and Voice Explanation Mode reference the right drill.
- Consider logging every refusal + the user's question (without PII) so
  you can spot real gaps in the 8-drill content over time.
