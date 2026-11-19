# Nova Academy - LMS for digital courses with personalised AI tutors

A complete learning management system for a single online academy. Every course comes with **Nova**, a personal AI tutor. It answers from that course's own material, adapts to how each learner likes to learn, and quizzes them on what they find hardest.

**Runs fully locally, with no paid APIs.** The tutor uses a local open-weight model served by [Ollama](https://ollama.com). If Ollama isn't running, it answers directly from the course content, so everything still works.

## Run it

Requirements: Python 3.11+, Node 18+, and optionally Ollama with `llama3.2:3b` pulled (`ollama pull llama3.2:3b`).

```bash
pip install -r backend/requirements.txt
```

Then double-click **`start-demo.bat`**, or:

```bash
cd frontend && npm install && npm run build && cd ..
python -m uvicorn app.main:app --app-dir backend --port 8765
```

Open http://localhost:8765. `start-demo.bat reset` wipes `backend/lms.db` so the demo data is re-seeded fresh. Use Chrome or Edge for voice input.

### Demo accounts (password `demo1234`, all fictional)

| Role | Email | What to show |
|---|---|---|
| Learner | aisha@learner.demo | Career changer; finished Excel (has a certificate), half-way through Python with **loops** as a weak spot |
| Content team | daniel@academy.demo | Course builder, insights, grading |
| Admin | admin@academy.demo | Platform stats, users, moderation, AI usage, audit log |

Anyone can also **create an account** from the sign-in page and go through onboarding.

## Features

**Learners**
- Sign-up and onboarding: goal, interests, experience, preferred explanation style, weekly time goal
- Personal home: continue learning, day streak, weekly goal progress, spaced-review reminders, recommended courses (each with a reason)
- Catalogue with search and filters; course pages with outcomes, curriculum, instructor and reviews
- One-click free enrolment
- Course player: article, video (YouTube, Vimeo or MP4), quiz and assignment lessons; outline with progress; private notes; lesson discussions
- Quizzes are auto-marked with explanations (pass mark 70%, retakes allowed). A failed quiz points to the lessons to revisit
- Assignments get an instant automated rubric check, then a grade and feedback from the course team
- Certificates on completion, with a public verification link and print / save-as-PDF
- Profile and preferences; download all of your data

**Personalised AI tutor (in every lesson)**
- **Quiz me**: practice on the learner's weakest concept, marked instantly. It updates per-concept mastery (Bayesian Knowledge Tracing) and schedules spaced review
- **Explain simply** / **Example**: instant, from the lesson's verified "Key points" and "Example" sections
- **Free questions**: retrieves relevant passages from the course (BM25 search), then the local model answers in the learner's style and level, with sources shown. Answers stream word by word
- Safety checks on every answer:
  - must be grounded in the course text, otherwise the learner sees the course passage itself
  - never gives away answers to a quiz the learner hasn't passed
  - inappropriate output is blocked
- Learner messages are screened: personal data is redacted, and wellbeing or abuse concerns are flagged to admins with crisis-line signposting
- Optional voice (British text-to-speech and speech input) and an animated avatar labelled as AI

**Content team (studio)**
- Create courses; edit details, outcomes, category, level, icon and colour; publish or unpublish
- Modules and lessons: add, rename, delete, reorder; markdown editor; quiz editor (multiple choice and short answer, with concept tags and explanations); assignment rubric editor
- Insights per course:
  - completion funnel
  - hardest quiz questions
  - concept mastery across learners
  - **what learners ask the AI tutor** (anonymised)
  - learner roster with weak spots
  - unanswered discussion questions
- Grading queue with the automated rubric check alongside

**Admin**
- Stats: learners, weekly activity, enrolments, completions, certificates, learning minutes; daily chart; courses by enrolment
- User management: change roles, deactivate, export or erase a learner's data (UK GDPR access and erasure)
- Moderation queue, AI usage (calls, tokens, latency, cost per learner) and the audit log

## Architecture

| Layer | Implementation |
|---|---|
| Frontend | React 18 + Vite, markdown via marked + DOMPurify |
| Backend | Python FastAPI (`backend/app/main.py`) |
| Data | SQLite (`db.py`, PostgreSQL-ready schema) |
| Learning engine | `learning.py`: progress, marking, mastery, spaced review, certificates, recommendations |
| AI tutor | `tutor.py` (orchestration and guards), `retrieval.py` (RAG over course content), `llm.py` (swappable providers: Ollama, offline, optional Claude) |
| Safety | `safety.py`: input screening, redaction, grounding and quiz-leak checks |
| Demo content | `seed_content.py`: 4 published courses and 1 draft, original material; `seed.py`: users and activity |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `TUTOR_LLM` | `ollama` | `ollama`, `offline` (course-content answers only) or `claude` (paid; needs `ANTHROPIC_API_KEY` and `pip install anthropic`) |
| `TUTOR_MODEL` | `llama3.2:3b` | Model name |
| `OLLAMA_NUM_GPU` | `0` | `0` = CPU (GPU offload crashed Ollama on the development PC). Use `99` with a working GPU for answers in 1-3 s |
| `TUTOR_DB` | `backend/lms.db` | SQLite file |

## Known limitations

- On CPU the local model takes about **10-15 s to start answering and 25-40 s to finish**. Quiz me, Explain simply, Example and all marking are instant. Some local-model answers are swapped for the course passage by the grounding check.
- Payments are not implemented; all courses are free (a commented placeholder sits in `llm.py`).
- SQLite and in-process BM25 retrieval suit a demo. Production should use PostgreSQL and pgvector, managed authentication (OIDC), and a streaming speech service.
- The automated rubric check is keyword-based: it gives a first pass, and the course team assigns the grade.

The earlier school-tutoring MVP is kept in `archive/school-mvp/` for reference.
