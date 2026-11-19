# Nova — AI-Powered Personalised Tutoring Platform (MVP)

A working demo of the platform described in the Scope of Work. It covers the SOW's Phase 1–2 acceptance criteria and previews Phase 3–4 (voice, whiteboard, avatar, dashboards). KS3/GCSE Mathematics is the initial subject, as the SOW specifies.

**Runs fully locally with no paid APIs.** All maths marking is done by SymPy. A local open-weight model served by Ollama answers students' free-form questions.

## Run it

Requirements: Python 3.11+, Node 18+, and optionally [Ollama](https://ollama.com) with `llama3.2:3b` pulled.

```bash
pip install -r backend/requirements.txt
```

Then double-click **`start-demo.bat`**, or run:

```bash
cd frontend && npm install && npm run build && cd ..
python -m uvicorn app.main:app --app-dir backend --port 8765
```

Open http://localhost:8765. To get fresh demo data before a client meeting, run `start-demo.bat reset` (it deletes `backend/tutor.db`, which is re-seeded on start).

**Use Chrome or Edge.** Voice input relies on the browser's speech recognition. Other browsers still work, but you type instead of speaking.

### Demo accounts (password `demo1234`, all fictional)

| Role | Email | What to show |
|---|---|---|
| Student | amelia@demo.school | Returning learner. Nova remembers her fractions difficulty |
| Parent | parent@demo.school | Amelia's progress, usage controls, data download |
| Teacher | teacher@demo.school | Class heatmap, common misconceptions, assigning work |
| School admin | admin@demo.school | Licences, usage, safeguarding flags, audit log, data deletion |
| Platform admin | super@demo.platform | All institutions |

## Suggested 10-minute client demo

1. **Student → Start lesson** (fractions revision is "Up next"). Nova greets Amelia with *"Last time we practised adding and subtracting fractions. You understood same denominators, but different denominators were tricky. You sometimes add the denominators together. Let's revise that before we continue."* This is the SOW's own memory example, generated from her saved record.
2. Answer the warm-up **wrong on purpose** by adding across (for 1/4 + 1/7 type `2/11`). Nova names the misconception, explains on the whiteboard with fraction bars, walks through the worked solution, then sets a new question.
3. Click **💡 Hint**, type **"just tell me the answer"** (Nova refuses and guides instead), and click **🔄 Explain another way** (it switches teaching method).
4. Ask a free question with the 🎤 or by typing, e.g. *"why can't I add the bottom numbers?"* (answered by the local AI from verified content).
5. Use **✏️ Pen** on the whiteboard to show student ink (mouse, touch or stylus).
6. Answer correctly a few times. Difficulty levels up, then a **Final check** must be passed without hints before the topic advances.
7. **Save & exit**, then start again. Nova resumes the exact question in progress.
8. Sign in as **Parent**, **Teacher** and **School admin** to show the dashboards. To demo safeguarding, type *"people at school bully me"* in a lesson; it shows up under the admin's Safeguarding tab.

## SOW coverage

| SOW module | In this MVP |
|---|---|
| 1 Subject expert engine | 7 KS3/GCSE maths topics, 3 difficulty levels each, generated questions with **SymPy-verified answers**, retrieval over versioned curriculum content (source + version recorded), swappable model providers (`backend/app/llm.py`) |
| 2 Teaching intelligence | State machine for the full 13-step workflow (`backend/app/tutor.py`): greet → recall → objective → diagnostic → explain → worked example → practice → evaluate → misconception → hint / alternative method → reassess → update record → recommend |
| 3 Memory & learning records | Persistent per-student lessons, attempts, answers, misconceptions, Bayesian Knowledge Tracing mastery (evidence-only: claiming to understand never counts), effective teaching method, homework, spaced-repetition revision, recommendations, export and deletion, audit log |
| 4 Voice | British-English text-to-speech and speech recognition (Web Speech API), interruption (speaking or typing stops Nova), automatic fallback to text, transcript saved |
| 5 Avatar | Lightweight animated teacher with lip movement synced to speech, blinking, gaze and a wave, clearly labelled "AI tutor", can be switched off |
| 6 Whiteboard | KaTeX equations, numbered step-by-step working, highlights, fraction bar models, right-angled triangles, coordinate graphs, student pen/eraser (mouse, touch, stylus pressure), board and ink saved with the lesson |
| 7 Curriculum | Organised by country, curriculum, key stage, year, subject strand, topic and objective; prerequisite mapping; content version; English and Science shown as Phase 2 |
| 8 Assessment & adaptivity | Diagnostic warm-up, adaptive difficulty, automated marking, 23 named misconception detectors, evidence-based mastery, revision scheduling |
| 9 Student app | Login, dashboard, subjects, classroom, homework, lesson history (transcript, answers, saved board), progress, revision schedule; responsive layout |
| 10 Dashboards | Parent (progress, strengths/weaknesses, time, revision, daily limit and voice/avatar controls), teacher (class heatmap, common difficulties, results, assign activities, per-student drill-down), school admin |
| 11 Licensing | Organisations with seat licences, pseudonymous student IDs, tenant-scoped admin queries, usage minutes |
| 12 Security & safeguarding | bcrypt passwords, signed expiring tokens, role-based access on every student record, audit logging, safeguarding detection with escalation queue (Childline / 999 signposting), personal-data and language screening, checks that the AI never gives away the answer and that its explanations stay grounded in verified content |

## How the AI is kept safe and accurate

- **The model never marks work.** SymPy checks equivalence (and accepts e.g. `x = 4`, `four` or `£92`). It also asks students to simplify `4/8` or finish expanding brackets.
- **Hints, feedback and worked solutions** come from the verified engine verbatim. With the small local model, the LLM is only used to answer students' free-form questions.
- Every LLM answer passes three checks: no inappropriate content, the current answer is not revealed, and the answer is **grounded** (its key words must come from the verified curriculum content). If any check fails, Nova uses the verified content instead. During testing this rejected a made-up explanation from the 3B model.
- The admin "AI & audit" tab records model, tokens, latency and cost for every call.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `TUTOR_LLM` | `ollama` | `ollama`, `offline` (rule-based voice only) or `claude` (paid API, needs `ANTHROPIC_API_KEY` and `pip install anthropic`) |
| `TUTOR_MODEL` | `llama3.2:3b` | Ollama model name |
| `OLLAMA_NUM_GPU` | `0` | GPU layers. `0` = CPU, because GPU offload crashed Ollama on the development machine. Try `99` on a machine with a working GPU for ~1–3 s answers |
| `TUTOR_LLM_REWRITE` | unset | `all` also lets the model phrase greetings, feedback and hints (only for larger models) |
| `TUTOR_DB` | `backend/tutor.db` | SQLite file |

If Ollama isn't running, Nova falls back automatically to the rule-based voice and the demo still works.

## Known MVP limitations (and their production equivalents)

- On CPU the local model takes about **20–30 s** per free-form question (a "Thinking…" indicator shows meanwhile). Marking, hints and teaching are instant.
- SQLite instead of PostgreSQL and lexical retrieval instead of pgvector. Data access is isolated in `db.py` / `curriculum.retrieve`, so swapping is contained.
- Signed HMAC tokens stand in for OIDC/OAuth 2.0 school SSO.
- Browser speech APIs stand in for a streaming STT/TTS service, and an SVG avatar stands in for a commercial avatar SDK.
- The keyword-based safeguarding screen is a placeholder. Production needs a moderation model, a human review workflow and validation by UK safeguarding and legal specialists before any real pupil uses it (as the SOW states).
- Teaching content has been written to the National Curriculum but not yet reviewed by a qualified maths educator.
