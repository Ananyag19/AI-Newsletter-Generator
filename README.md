# AI Newsletter Writer

Turn links, uploaded files, and raw notes into a drafted newsletter — headline,
sections, and call-to-action — using an LLM (Groq or Gemini).

```
User → Upload Links / Notes / Documents
     → Content Extraction (URL scraper + File/Text parser)
     → Cleaning & Chunking
     → AI Summarization & Key Point Extraction
     → Newsletter Structure Generation
     → AI writes headline, sections, CTA
```

## Project structure

```
ai-newsletter-writer/
├── backend/
│   ├── main.py                    FastAPI app, routes, admin auth
│   ├── config.py                  Settings (reads .env)
│   ├── runtime_settings.py        Admin-changeable active provider (persisted to disk)
│   ├── requirements.txt
│   ├── .env.example                Copy to .env and fill in API keys
│   ├── data/
│   │   └── runtime_state.json     Auto-created; stores the admin's provider choice
│   ├── credentials/
│   │   ├── oauth_client.json      You provide this (OAuth client, Desktop app type)
│   │   └── drive_token.json       Auto-created by scripts/get_drive_token.py
│   ├── scripts/
│   │   └── get_drive_token.py     One-time script: authorize Drive as your own account
│   ├── extractors/
│   │   ├── url_scraper.py         newspaper3k + BeautifulSoup fallback
│   │   └── file_parser.py         PDF (PyMuPDF), DOCX (python-docx), TXT
│   ├── processing/
│   │   ├── text_cleaner.py        Boilerplate stripping, whitespace normalization
│   │   └── chunker.py             Word-based chunking with overlap
│   ├── integrations/
│   │   └── google_drive.py        Drive upload/find/download, used by grok_drive provider
│   ├── ai/
│   │   ├── llm_client.py          Unified Groq / Gemini / Qwen / Grok-via-Drive client
│   │   ├── summarizer.py          Chunk -> key point bullets
│   │   └── newsletter_writer.py   Key points -> structured newsletter draft
│   └── models/
│       └── schemas.py             Pydantic request/response models
└── frontend/
    ├── index.html                 Single-page UI ("The Wire Desk") + admin panel
    ├── style.css
    └── app.js                     Talks to the backend over REST
```

## 1. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set AI_PROVIDER=groq (or gemini) and the matching API key
```

Get an API key for whichever provider(s) you want to use:
- Groq: https://console.groq.com/keys (free tier available, fast inference)
- Gemini: https://aistudio.google.com/app/apikey
- Qwen (DashScope): https://dashscope.console.aliyun.com/apiKey

### Setting up the Grok-via-Drive provider (no xAI API key needed)

This provider hands work off to a **scheduled Grok Task** at `grok.com/tasks`
instead of calling an API directly. It's slower (polling-based, can take
minutes) but works entirely off Grok's own Google Drive connector.

**Auth note:** this uses OAuth as *your own* Google account, not a service
account. Service accounts have zero Drive storage quota and fail with a 403
`storageQuotaExceeded` error the moment they try to create a file — even in
a folder shared with them as Editor. Authenticating as yourself avoids this,
and it's still only a **one-time** browser consent, not a login on every
request — the saved token silently refreshes itself forever after.

1. In Google Cloud Console: create/pick a project, enable the **Google
   Drive API** (APIs & Services → Library), then go to APIs & Services →
   Credentials → **Create Credentials → OAuth client ID**, application type
   **Desktop app**. Download the resulting JSON.
2. Save it (e.g. as `backend/credentials/oauth_client.json`) and set
   `GOOGLE_OAUTH_CLIENT_SECRETS_FILE` in `.env` to its path.
3. From `backend/`, run:
   ```bash
   python scripts/get_drive_token.py
   ```
   This opens your browser for a one-time sign-in — use the **same Google
   account** you connected to Grok's Drive connector. After approving, it
   saves a token to `GOOGLE_OAUTH_TOKEN_FILE` (default
   `./credentials/drive_token.json`). You won't need to run this again
   unless you revoke access or delete that file.
4. Pick (or create) a folder that already exists in that account's own
   Drive — no sharing step needed, since you own it outright. Copy its ID
   from the folder's URL (`.../folders/<FOLDER_ID>`) into
   `GOOGLE_DRIVE_FOLDER_ID` in `.env`.
5. **Set up the Grok Task** at `grok.com/tasks`: schedule it to run every
   few minutes, with a prompt roughly like:

   > Check the Drive folder `<folder name>` for files named
   > `inbox_task_*.txt` that don't yet have a matching `outbox_task_*.md`
   > file. For each one you find, read the instructions and input inside it,
   > carry them out, and save your complete response as a new file named
   > exactly `outbox_task_<same id>.md` in the same folder — no extra
   > commentary, just the requested content.

6. In the admin panel (see below), set the active provider to **Grok (via
   Google Drive)**.

Once this is active, every `/generate` call blocks until Grok's scheduled
task picks up the file and writes a result back (or times out after
`GROK_DRIVE_MAX_WAIT_SECONDS`, default 30 minutes) — the frontend shows a
heads-up about the wait when this provider is active.

Run the server:

```bash
python main.py
# or: uvicorn main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

## 2. Frontend setup

The frontend is plain HTML/CSS/JS with no build step. Just open it:

```bash
cd frontend
python -m http.server 5500
# then open http://localhost:5500 in your browser
```

(Opening `index.html` directly by double-clicking also works in most
browsers, but serving it avoids some browsers' file:// CORS quirks.)

If your backend runs somewhere other than `http://localhost:8000`, update
`BACKEND_URL` at the top of `frontend/app.js`.

## 3. Using it

1. **Links tab** — paste one or more article URLs (one per line) and click
   "Fetch & Extract". The backend scrapes each page with newspaper3k,
   falling back to a raw BeautifulSoup parse if that fails.
2. **Files tab** — drag in PDF, DOCX, or TXT/MD files to extract their text.
3. **Notes tab** — paste raw notes or bullet points; these are treated as
   high-priority input and go straight to the writer step (no scraping needed).
4. Fill in the **edition settings** — title/theme, audience, tone, number of
   sections, and whether to include a call-to-action.
5. Click **Generate Newsletter**. The pipeline indicator at the top shows
   progress through Extract → Clean → Summarize → Draft.
6. Copy the Markdown or download it as `newsletter.md` from the Proof panel.

## Admin panel — choosing which AI provider is active

There are now four providers (Groq, Gemini, Qwen, Grok-via-Drive), but
**regular users never see or choose between them** — only whoever holds the
admin token can switch providers, and the choice applies to everyone using
the app.

1. Set `ADMIN_TOKEN` in `backend/.env` to any long random string. Leaving it
   blank disables the admin panel (the endpoints return 500).
2. In the frontend, click the small **"⚙ Admin"** link in the footer.
3. Enter the token and click **Unlock** — this reveals a dropdown of the
   four providers and a **Save** button.
4. The chosen provider is persisted server-side in
   `backend/data/runtime_state.json`, so it survives a server restart, and
   applies to every `/generate` request from any user until changed again.

The admin token is only ever kept in browser memory for that tab (never
written to localStorage/disk) and is sent via the `X-Admin-Token` header —
`GET`/`POST /admin/provider` reject anything else with a 401.

## API reference

| Method | Path              | Description                                       |
|--------|-------------------|-----------------------------------------------------|
| GET    | `/health`         | Health check + which AI provider is currently active |
| POST   | `/extract/urls`   | `{ "urls": ["https://..."] }` → extracted text per URL |
| POST   | `/extract/file`   | multipart file upload → extracted text              |
| POST   | `/generate`       | contents/notes + settings → newsletter draft         |
| GET    | `/admin/provider` | **Admin only.** Current + available providers        |
| POST   | `/admin/provider` | **Admin only.** `{ "provider": "groq"\|"gemini"\|"qwen"\|"grok_drive" }` |

Full request/response schemas are in `backend/models/schemas.py`, and are
also browsable at `/docs` once the server is running.

## Notes & known limitations

- **JS-heavy sites**: the URL scraper does a plain HTTP fetch + HTML parse.
  Sites that render content client-side (heavy React/Vue apps without SSR)
  may return little or no text — the response will include an `error` field
  explaining this.
- **LLM output isn't guaranteed valid JSON** on every provider/model
  combination. `llm_client.generate_json` strips common markdown code-fence
  wrapping, but if a model still misbehaves, the `/generate` endpoint returns
  a 502 with the underlying error message.
- **Rate limits / costs**: Groq and Gemini both have their own rate limits
  and (for Gemini) usage costs beyond the free tier — check current pricing
  on each provider's site.
- **spaCy / NLTK**: listed in `requirements.txt` per the original tech stack
  for future NLP enhancements (e.g. smarter sentence-boundary chunking,
  named-entity highlighting), but the current cleaning/chunking pipeline
  works on plain regex + word counts and doesn't require downloading models.
  If you extend `text_cleaner.py` or `chunker.py` to use spaCy, remember to
  run `python -m spacy download en_core_web_sm` once.
