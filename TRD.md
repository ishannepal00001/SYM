# SYM — Technical Requirements

Status: written 2026-10-11 from the design session that followed `prd.md`. Where this document and the PRD disagree, this document wins; the differences are listed in [section 2](#2-changes-to-the-prd).

Decisions the owner did not answer directly were filled in by the author. They are listed in [section 20](#20-decisions-filled-in-without-the-owner) so they can be reviewed in one place.

## 1. Scope of v1

| In v1 | Out of v1 |
|---|---|
| WhatsApp messenger plugin | mysecondteacher plugin |
| Instagram messenger plugin | School email digest |
| Full-screen terminal UI (Textual) | Research on request, web search |
| Planner, Executor, reply tool | Document search (RAG) |
| Two protocols: House Party and Clean Slate | Background daemon, scheduling |
| Held replies with an email notice | Approving by email |
| Document uploader for reply context | Parallel execution of plan steps |
| Voice input | Spoken output |
| Group chats (built last) | |

## 2. Changes to the PRD

| PRD section | PRD says | v1 does |
|---|---|---|
| §3, §6.1, §9 | mysecondteacher is the first plugin | Out of v1 |
| §3, §6.4, §9 | School email digest | Out of v1 |
| §4 | SYM never reaches the owner outside the terminal | Held replies are also emailed to the owner as a notice |
| §5.1 | The terminal CLI is the only interface | A full-screen terminal UI built with Textual |
| §7 | A commitment or unsure reply sends nothing | SYM sends a fixed holding line and holds the real reply for approval |
| §7 | A sender off the allowlist gets a draft for approval | No model call and no draft; the message only appears in the unread list |
| §8.4 | The reply path has no access to files | The reply model is given documents the owner marked shareable |
| §8.5 | The action log is the single record | The action log is one file per run; conversations, plans and chat messages are also in the database |
| §8.8 | Background work runs as systemd user services | SYM is one foreground process. Only OmniRoute has a systemd unit |
| §12 | An `asyncio` queue was suggested for retries | Adopted; the retry queue is in memory and is lost on exit |

## 3. Process model

- SYM is one process: the Textual application. Closing it stops every plugin.
- There is no daemon, no socket and no systemd unit for SYM itself.
- One `asyncio` event loop runs everything that waits on I/O: the UI, model calls, `neonize`, Playwright, the database and email.
- CPU-bound work runs in a worker thread through `asyncio.to_thread`. In v1 that is speech transcription and PDF text extraction.
- Model calls are serialised: one call at a time, non-streaming, through a single shared model client ([section 9](#9-model-client)).
- OmniRoute runs separately as a systemd user unit ([section 15](#15-omniroute)).

## 4. Components

```
┌──────────────────────────── sym (one process, one asyncio loop) ─────────────────────────────┐
│                                                                                              │
│  Textual UI ──► Protocol switch ──► HOUSE PARTY: Planner ──plan──► Executor ──► plugin tools │
│  (text, voice)   (code, no model)   CLEAN SLATE: chat model with no tools                    │
│                                                                                              │
│  Plugin (base)                                                                               │
│    └─ Messenger (base): incoming queue, send, unread, reply tool                             │
│         ├─ WhatsApp   (neonize)                                                              │
│         └─ Instagram  (Playwright, Chromium)                                                 │
│                                                                                              │
│  Shared: model client · SQLite store · action log · email notifier                           │
└──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                               ▼
                              OmniRoute :20128 ──► Groq / OpenRouter
```

| Component | Calls a model | Responsibility |
|---|---|---|
| UI | No | Input, panels, buttons, screens |
| Protocol switch | No | Detects protocol phrases in the owner's input and routes it |
| Planner | Yes | Turns one owner instruction into a plan (a DAG of tool calls) |
| Executor | No | Validates and runs plans, holds plugin state, feeds incoming messages to the reply tool |
| Plugin tools | No | Do the actual work: connect, read, send |
| Reply tool | Yes | Writes a reply to one incoming message, then sends or holds it |
| Clean Slate chat | Yes | Talks with the owner; has no tools |
| Model client | — | The only code that talks to OmniRoute |

## 5. Protocols

| Protocol | Meaning |
|---|---|
| **House Party** | The Planner is in charge. Owner input becomes a plan and the Executor runs it. |
| **Clean Slate** | Every plugin is stopped. Owner input goes to a chat model with no tools. |

Rules:

- A switch is detected in code before any model sees the input. The input is lower-cased and stripped of punctuation; if the whole input equals `house party`, `house party protocol`, `clean slate` or `clean slate protocol`, the protocol changes and no model is called.
- A protocol name inside a longer sentence is ordinary input, not a switch.
- Only the owner's input is checked. Text from chats can never change the protocol.
- `F3` toggles the protocol. `F9` (stop all) is the same action as switching to Clean Slate.
- Entering Clean Slate stops all plugins. Entering House Party starts nothing.
- The current protocol is saved in `settings` and restored at the next launch. The first launch starts in House Party. Plugins are never started automatically at launch.
- The header shows the current protocol at all times.

The Clean Slate chat model is told that it is SYM, that it has no tools, and that if the owner asks it to do something it should say so and name the protocol to switch to. It sees the current conversation only.

## 6. Planner and Executor

### 6.1 Tools

Each plugin class carries a list of its tools. At startup the Executor collects the lists into a registry and writes them into the Planner's system prompt. The Planner has no other knowledge of plugins.

A tool descriptor:

```json
{"plugin": "whatsapp", "tool": "start_auto_reply",
 "description": "Reply to allowlisted chats until stopped",
 "args": {}, "access": "act"}
```

`access` is `read` (looks only) or `act` (sends, starts or stops something).

v1 registry:

| Plugin | Tool | Args | Access |
|---|---|---|---|
| `whatsapp`, `instagram` | `start` | — | `act` |
| `whatsapp`, `instagram` | `stop` | — | `act` |
| `whatsapp`, `instagram` | `start_auto_reply` | — | `act` |
| `whatsapp`, `instagram` | `stop_auto_reply` | — | `act` |
| `whatsapp`, `instagram` | `unread` | — | `read` |
| `core` | `list_held` | — | `read` |
| `core` | `approve_held` | `draft_id` | `act` |
| `core` | `reject_held` | `draft_id` | `act` |
| `core` | `set_dry_run` | `on` | `act` |

`start` connects the plugin and begins collecting messages. `start_auto_reply` additionally turns on the reply tool for that plugin.

### 6.2 Plan schema

The Planner has exactly one LangChain tool, `submit_plan`, whose argument is the plan:

```json
{
  "goal": "Start auto-reply on WhatsApp and show Instagram unread",
  "say": "Starting WhatsApp auto-reply and fetching Instagram unread.",
  "steps": [
    {"id": "s1", "plugin": "whatsapp",  "tool": "start_auto_reply", "args": {}, "depends_on": []},
    {"id": "s2", "plugin": "instagram", "tool": "unread",           "args": {}, "depends_on": []}
  ]
}
```

| Field | Rule |
|---|---|
| `goal` | One line, stored as the plan's title |
| `say` | Text shown to the owner. A plan with no steps and only `say` is a plain answer |
| `steps[].id` | Unique within the plan |
| `steps[].plugin`, `tool` | Must exist in the registry |
| `steps[].args` | Must match the tool's declared arguments |
| `steps[].depends_on` | May only name steps that appear earlier in the list, so a cycle cannot be expressed |
| Size | At most 8 steps |

### 6.3 Execution

1. The Executor validates the whole plan. An invalid plan is sent back to the Planner once with the error; a second failure is reported to the owner and nothing runs.
2. If any step is `act`, the plan is shown in the conversation pane and waits for `Enter` to run or `Esc` to cancel. Plans with only `read` steps run immediately.
3. Steps run one at a time in list order.
4. A failed step is marked `failed`, and every step that depends on it is marked `skipped`. Unrelated steps still run.
5. Tool results that contain chat content (for example `unread`) are rendered straight to the UI. The Planner receives only a summary such as "7 unread in 3 chats". Chat text never enters a Planner prompt.
6. The plan and each step are stored in `plans` and `plan_steps` with their status.

### 6.4 Planner context

- The system prompt: identity, the tool registry, the plan schema.
- A status block built in code: running plugins, auto-reply state, held replies with their ids and contact names, dry-run state.
- The last 30 messages of the current conversation, or fewer if they exceed 3,000 tokens.

## 7. Messenger plugins

### 7.1 Class hierarchy

| Class | Adds |
|---|---|
| `Plugin` | `name`, `tools`, `start()`, `stop()`, `status` |
| `Messenger(Plugin)` | `incoming` queue, `send()`, `unread()`, the reply tool, start line, duplicate filter |
| `WhatsApp(Messenger)` | Connect, receive and send through `neonize` |
| `Instagram(Messenger)` | Connect, receive and send through Playwright |

A subclass implements four methods: `_connect()`, `_disconnect()`, `_listen()` (puts records on `incoming`) and `_send(chat_id, text)`. It holds no model, no allowlist logic and no reply logic, and imports nothing from the Planner or Executor.

### 7.2 Incoming message record

```json
{"plugin": "whatsapp", "message_id": "3EB0...", "chat_id": "97798...", "chat_name": "Aarav",
 "sender_id": "97798...", "sender_name": "Aarav", "text": "kata chau?", "kind": "text",
 "is_group": false, "sent_at": "2026-10-11T14:02:11+05:45"}
```

- `kind` is `text` or `other`. Photos, voice notes, stickers and calls arrive as `other` with empty text. They count as unread and never get a reply.
- Messages the owner sent from their own phone are recorded with `sent_by = owner` and never trigger a reply.

### 7.3 Shared behaviour

- **Start line**: everything already in a chat when the plugin starts is treated as seen. Only messages that arrive afterwards are put on `incoming`.
- **Duplicates**: a message whose `(chat, message_id)` is already stored is dropped.
- **Groups**: records with `is_group = true` are stored and counted as unread but never passed to the reply tool until group support is built ([section 18](#18-build-order)).
- **Sending**: `send()` waits a random 2 to 6 seconds before sending, so replies do not arrive instantly.
- **Stopping**: `stop()` disconnects and discards anything still on `incoming`; the discard is logged.

### 7.4 WhatsApp

- `neonize` async client, linked to the owner's number as a companion device.
- First run: the QR code is drawn in the WhatsApp panel of the UI. The session is saved in `~/.local/share/sym/whatsapp/`.
- New messages arrive as `neonize` events; `_listen()` converts each to a record.
- A chat is marked as read only when SYM sends a reply into it.

### 7.5 Instagram

- Playwright drives a visible Chromium window with a persistent profile in `~/.local/share/sym/instagram/`.
- The owner logs in by hand in that window the first time. SYM never handles the Instagram password.
- The inbox page stays open and is not reloaded. Every 5 seconds SYM reads the page for unread markers, which sends no extra traffic. A reload happens only if the page reports it has lost its connection.
- Reading a new message means opening its chat, which shows the sender "seen". This is accepted.
- Selectors are found by inspecting the live page when this plugin is built and are kept in one module, because they are what breaks when Instagram changes.

## 8. Reply flow

### 8.1 Steps for one incoming message

1. The plugin puts the record on `incoming`.
2. The Executor stores it in `messages` and `chat_messages` and logs `message_received`.
3. If auto-reply is off for that plugin, the flow ends here and the message shows as unread.
4. Code checks, in order: `kind` is `text`, not a group, sender is allowlisted in `contacts`. Any failure ends the flow with no model call.
5. The reply tool builds the prompt ([8.3](#83-reply-prompt)) and calls the model through the shared model client.
6. The model answers with one tool call: `reply(text, kind)`, where `kind` is `simple`, `commitment` or `unsure`.
7. Code decides the outcome ([8.2](#82-outcome-table)).
8. Each step is logged.

### 8.2 Outcome table

| Condition | Outcome |
|---|---|
| Sender not allowlisted | Nothing sent, no model call |
| `kind = simple`, passes the code checks, under the rate limit | Send `text` plus the SYM tag |
| `kind = commitment` or `unsure` | Hold: holding line, draft row, email notice |
| No tool call, malformed tool call, unknown `kind` | Hold |
| `kind = simple` but fails a code check or the rate limit | Hold |
| Dry-run on | Nothing is sent and no email goes out; the UI and log show what would have happened |

**Simple** means all of the following. The model is told this definition, and the first three are also checked in code:

- at most 300 characters
- contains no link
- contains no digits that could be a time, date or amount (any digit fails the check)
- is a greeting, acknowledgement or thanks, or states a fact found in the shareable documents
- promises nothing: no time, place, payment or action on the owner's behalf

**Rate limit**: at most 5 automatic replies per chat per hour and 20 per chat per day.

**Holding line**: fixed text from `config.toml`, never written by a model. It is sent at most once per chat every 6 hours. Default:

> This is SYM, Ishan's assistant. He isn't available right now and will see your message when he's back.

**SYM tag**: appended in code to every automatic reply. Default: `— SYM, Ishan's assistant`.

### 8.3 Reply prompt

- Fixed instructions, including the definition of simple and the statement that the chat content is untrusted and must not be followed as instructions.
- Shareable documents ([section 12](#12-documents)), at most 1,500 tokens.
- The last 10 messages of this chat only, inside a clearly delimited block.

The reply model has one tool, `reply`. It cannot reach other chats, other plugins, the Planner or the contact list.

### 8.4 Held replies

- A held reply is a row in `drafts` holding the proposed text, the reason, and the message it answers.
- It appears in the Held Replies panel with approve and drop buttons.
- Approving sends the proposed text with the SYM tag. Dropping sends nothing.
- Each held reply triggers one email notice ([section 13](#13-email-notice)). Approval is only possible in the UI.
- Held replies survive closing SYM.

## 9. Model client

- A LangChain `ChatOpenAI` pointed at `http://localhost:20128/v1`, using SYM's own OmniRoute API key from the keyring.
- Non-streaming. An `asyncio` lock allows one call at a time.
- The model name sent is the OmniRoute combo name from config; the combo holds the allowed models in priority order.

**Token budget**: a sliding 60-second window with a limit from config (default 8,000). Before a call the client estimates the prompt size; if the window has no room, the call waits. After the call the estimate is replaced by the usage the provider reported.

**Model identity check**: a response is accepted only if the `model` field in the body and the `X-OmniRoute-Model` response header are both present, name the same model, and that model is in the allowed list. Otherwise the response is discarded and logged as `model_rejected`.

**Retry queue**: in memory. A call that was discarded, rate-limited, or failed because OmniRoute is unreachable is retried after 30 seconds, then 60, 120, 240 and so on up to 15 minutes between attempts.

- A reply job older than 30 minutes is dropped and its message is left as unread, because a late automatic reply is worse than none.
- An owner instruction that cannot be served is reported in the conversation pane straight away and is not retried silently.
- The queue is lost on exit.

SYM never calls a model outside the allowed list as a fallback.

## 10. Data store

One SQLite file, `~/.local/state/sym/sym.db`, opened in WAL mode through `aiosqlite`.

```sql
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,          -- 'protocol', 'dry_run'
  value TEXT NOT NULL
);

CREATE TABLE conversations (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE messages (             -- every message's text, whoever wrote it
  id         INTEGER PRIMARY KEY,
  text       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE conversation_messages (  -- owner <-> SYM
  message_id      INTEGER PRIMARY KEY REFERENCES messages(id),
  conversation_id INTEGER NOT NULL REFERENCES conversations(id),
  role            TEXT NOT NULL,      -- 'owner' | 'sym'
  input           TEXT NOT NULL       -- 'text' | 'voice'
);

CREATE TABLE contacts (
  id          INTEGER PRIMARY KEY,
  plugin      TEXT NOT NULL,          -- 'whatsapp' | 'instagram'
  external_id TEXT NOT NULL,
  name        TEXT NOT NULL,
  allowlisted INTEGER NOT NULL DEFAULT 0,
  UNIQUE (plugin, external_id)
);

CREATE TABLE chats (
  id              INTEGER PRIMARY KEY,
  plugin          TEXT NOT NULL,
  external_id     TEXT NOT NULL,
  name            TEXT NOT NULL,
  contact_id      INTEGER REFERENCES contacts(id),
  is_group        INTEGER NOT NULL DEFAULT 0,
  last_holding_at TEXT,               -- when the holding line was last sent
  UNIQUE (plugin, external_id)
);

CREATE TABLE chat_messages (          -- friends <-> owner/SYM
  message_id  INTEGER PRIMARY KEY REFERENCES messages(id),
  chat_id     INTEGER NOT NULL REFERENCES chats(id),
  external_id TEXT NOT NULL,
  direction   TEXT NOT NULL,          -- 'in' | 'out'
  sent_by     TEXT NOT NULL,          -- 'contact' | 'owner' | 'sym'
  kind        TEXT NOT NULL,          -- 'text' | 'other'
  unread      INTEGER NOT NULL DEFAULT 1,
  sent_at     TEXT NOT NULL,
  UNIQUE (chat_id, external_id)
);

CREATE TABLE drafts (                 -- held replies
  id          INTEGER PRIMARY KEY,
  chat_id     INTEGER NOT NULL REFERENCES chats(id),
  in_reply_to INTEGER NOT NULL REFERENCES messages(id),
  text        TEXT NOT NULL,
  reason      TEXT NOT NULL,          -- 'commitment' | 'unsure' | 'malformed' | 'check_failed' | 'rate_limit'
  status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
  created_at  TEXT NOT NULL,
  decided_at  TEXT
);

CREATE TABLE plans (
  id              INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id),
  goal            TEXT NOT NULL,
  status          TEXT NOT NULL,      -- 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  created_at      TEXT NOT NULL,
  finished_at     TEXT
);

CREATE TABLE plan_steps (
  id         INTEGER PRIMARY KEY,
  plan_id    INTEGER NOT NULL REFERENCES plans(id),
  step_key   TEXT NOT NULL,           -- 's1'
  plugin     TEXT NOT NULL,
  tool       TEXT NOT NULL,
  args       TEXT NOT NULL,           -- JSON
  depends_on TEXT NOT NULL,           -- JSON list of step keys
  status     TEXT NOT NULL,           -- 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  result     TEXT,
  error      TEXT,
  UNIQUE (plan_id, step_key)
);

CREATE TABLE plugin_state (
  plugin     TEXT PRIMARY KEY,
  status     TEXT NOT NULL,           -- 'stopped' | 'starting' | 'running' | 'error'
  auto_reply INTEGER NOT NULL DEFAULT 0,
  state      TEXT,                    -- JSON, plugin-specific
  updated_at TEXT NOT NULL
);

CREATE TABLE documents (
  id        INTEGER PRIMARY KEY,
  name      TEXT NOT NULL,
  text      TEXT NOT NULL,
  tokens    INTEGER NOT NULL,
  shareable INTEGER NOT NULL DEFAULT 0,
  added_at  TEXT NOT NULL
);
```

Notes:

- **Conversations**: each launch starts a new conversation. Its title is the first 60 characters of the owner's first instruction, set in code. Every message is kept; the model sees only the last 30.
- **Chat messages**: the text of a chat message is blanked after 30 days. The row stays so duplicates are still detected.
- **Plugin state**: `status` and `auto_reply` are reset to stopped and off at every launch.
- **Rate limit**: counted from `chat_messages` rows with `sent_by = 'sym'`.

## 11. Action log

- One JSON Lines file per run: `~/.local/state/sym/logs/<start time>.jsonl`. It is not in the database.
- Shown live in the Log pane. Files older than 30 days are deleted at launch.
- Lines are only ever appended.

```json
{"ts": "2026-10-11T14:02:13+05:45", "actor": "reply_tool", "event": "reply_sent",
 "plugin": "whatsapp", "chat_id": 12, "message_id": 881, "model": "groq/openai/gpt-oss-120b",
 "tokens_in": 412, "tokens_out": 18, "dry_run": false, "text": "Hi! — SYM, Ishan's assistant"}
```

Events: `protocol_changed`, `plan_submitted`, `plan_rejected`, `step_started`, `step_finished`, `plugin_started`, `plugin_stopped`, `message_received`, `model_call`, `model_rejected`, `reply_sent`, `holding_sent`, `reply_held`, `held_approved`, `held_rejected`, `email_sent`, `email_failed`, `job_retried`, `job_dropped`, `error`.

The log records text SYM sent. It refers to incoming messages by id and does not copy their text.

## 12. Documents

- The uploader screen (`F5`) takes a file path, with a file picker. Accepted: `.txt`, `.md`, and `.pdf` with a text layer.
- Text is extracted once at upload and stored in `documents`. The original file is not kept.
- Each document has a `shareable` switch, off by default. Only shareable documents are given to the reply model.
- The shareable documents together may use at most 1,500 tokens. The screen shows how much is used and refuses to switch on a document that would exceed it.
- Documents are pasted into the reply prompt whole. There is no search index.

## 13. Email notice

- One email per held reply, sent from the owner's Gmail address to itself over SMTP (`smtp.gmail.com`, port 465) with an app password from the keyring.
- Contents: contact name, plugin, the incoming message, the proposed reply, and the reason it was held.
- It is a notice only. SYM never reads a mailbox.
- A failed send is logged as `email_failed` and does not affect the held reply.
- `smtplib` from the standard library, run in a worker thread.

## 14. Voice input

- `F2` starts recording from the default microphone at 16 kHz mono (`sounddevice`).
- The first 300 ms set the background noise level. Recording stops after 1.5 seconds below 2.5 times that level once speech has been heard, or at 30 seconds.
- Transcription uses `faster-whisper` with the `small` model, `int8` on CPU, in a worker thread. Audio is not written to disk and never leaves the laptop.
- The transcript is placed in the input box. The owner presses `Enter` to send it, after which it is handled exactly like typed input, including protocol phrases.

## 15. OmniRoute

Unit file `~/.config/systemd/user/omniroute.service`:

```ini
[Unit]
Description=OmniRoute gateway

[Service]
ExecStart=%h/.local/share/mise/shims/omniroute serve --port 20128 --no-open --no-tray
Restart=on-failure

[Install]
WantedBy=default.target
```

One-time setup, done by the owner and not by code:

1. Upgrade OmniRoute from 3.8.50 to the current release.
2. Enable the unit: `systemctl --user enable --now omniroute`.
3. Change the default dashboard password and switch on the API key requirement.
4. Add the Groq and OpenRouter connections.
5. Create the combo with the three allowed models using the `priority` strategy.
6. Create SYM's own API key: request logging off, limited to those two connections and those models.
7. Store that key in the keyring.

At launch SYM calls the gateway once. If it does not answer, the header shows "gateway down", model work goes to the retry queue, and everything that needs no model (stop, approve, drop, unread, contacts) keeps working.

## 16. Files and configuration

| Location | Responsibility |
|---|---|
| `~/.config/sym/config.toml` | Settings the owner edits |
| `~/.local/state/sym/sym.db` | The database |
| `~/.local/state/sym/logs/` | Action log, one file per run |
| `~/.local/share/sym/whatsapp/` | WhatsApp linked-device session |
| `~/.local/share/sym/instagram/` | Chromium profile with the Instagram login |
| `~/.cache/sym/` | Speech model files |
| `~/.config/systemd/user/omniroute.service` | OmniRoute unit |
| System keyring, service `sym` | `omniroute_api_key`, `gmail_app_password` |
| The repository | Code only. No secrets, sessions or personal data |

`config.toml`:

```toml
[owner]
name  = "Ishan"
email = "you@example.com"

[gateway]
base_url          = "http://localhost:20128/v1"
combo             = "sym"
tokens_per_minute = 8000
allowed_models = [
  "groq/openai/gpt-oss-120b",
  "groq/openai/gpt-oss-20b",
  "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
]

[reply]
tag                 = "— SYM, Ishan's assistant"
holding_line        = "This is SYM, Ishan's assistant. He isn't available right now and will see your message when he's back."
holding_every_hours = 6
max_chars           = 300
per_chat_per_hour   = 5
per_chat_per_day    = 20
chat_context        = 10
document_tokens     = 1500
job_max_age_minutes = 30

[conversation]
context_messages = 30
context_tokens   = 3000

[instagram]
poll_seconds = 5

[voice]
model           = "small"
silence_seconds = 1.5
max_seconds     = 30

[retention]
chat_text_days = 30
log_days       = 30
```

Secrets are read with the `keyring` library and are never written to a file.

## 17. Terminal UI

```
┌ SYM ── HOUSE PARTY ── dry-run: off ── model: gpt-oss-120b ── gateway: up ─────────┐
│ PLUGINS          │ CONVERSATION                       │ HELD REPLIES (2)          │
│ ● WhatsApp  [■]  │ you: start replying on whatsapp    │ 1 Aarav                   │
│ ○ Instagram [▶]  │ sym: WhatsApp auto-reply started   │   "I'll be there"         │
│                  │                                    │   [approve] [drop]        │
│ UNREAD (7)       │                                    │ 2 Sita ...                │
│ Aarav  3         │                                    │                           │
│ Sita   4         ├────────────────────────────────────┴───────────────────────────┤
│                  │ LOG  14:02 whatsapp received Aarav · 14:02 reply sent          │
├──────────────────┴────────────────────────────────────────────────────────────────┤
│ > type here                                                                       │
│ F2 voice · F3 protocol · F4 contacts · F5 documents · F6 conversations · F9 stop  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

| Screen | Key | Purpose |
|---|---|---|
| Main | — | Everything above |
| Contacts | `F4` | List contacts per plugin, rename, switch allowlisting on or off |
| Documents | `F5` | Upload, remove, switch shareable on or off, see the token meter |
| Conversations | `F6` | Reopen a past conversation to read it |

- Plugin start and stop buttons, approve, drop, `F3`, `F9` and both extra screens work without any model call.
- The allowlist can be changed only on the Contacts screen. No tool in the registry edits `contacts`.
- New contacts are created automatically, not allowlisted, the first time someone writes.
- Selecting a name in the Unread list shows that chat's recent messages in place of the conversation pane.
- `Ctrl+Q` quits and stops all plugins.

## 18. Build order

Each step is usable before the next starts.

1. **Scraper and shell**: `Plugin` and `Messenger` base classes, the WhatsApp plugin, the database, the action log, and the Textual shell with the Plugins, Unread and Log panels and the input box. No model calls. Result: a live unread view for WhatsApp.
2. **Instagram plugin**.
3. **Model client**: OmniRoute wiring, token budget, identity check, retry queue, and the model admission test ([section 19](#19-model-admission-test)).
4. **Reply tool**: outcome rules, held replies, Contacts screen, email notice, dry-run.
5. **Planner and Executor**: tool registry, plans, both protocols, Conversations screen.
6. **Documents screen**.
7. **Voice input**.
8. **Group chats**.

Package layout:

```
src/sym/
  app.py              Textual application and screens
  protocol.py         protocol switch
  planner.py          Planner and plan schema
  executor.py         Executor and tool registry
  model.py            shared model client
  reply.py            reply tool and outcome rules
  store.py            database access
  log.py              action log
  notify.py           email notice
  voice.py            recording and transcription
  config.py           config.toml and keyring
  plugins/
    base.py           Plugin, Messenger, incoming record
    whatsapp.py
    instagram.py
tests/
  admission/          model admission cases
```

Dependencies: `textual`, `langchain-openai`, `neonize`, `playwright`, `aiosqlite`, `keyring`, `pydantic`, `pypdf`, `faster-whisper`, `sounddevice`, `numpy`.

## 19. Model admission test

A model joins `allowed_models` only after `uv run python -m sym.admit <model id>` passes. The script calls the model directly through OmniRoute with fixed cases:

| Set | Cases | Pass mark |
|---|---|---|
| Planner: instruction to expected plan | 10 | Every plan is schema-valid; at least 9 match the expected steps |
| Reply: message to expected `kind` | 15 | At least 13 correct; no `commitment` case labelled `simple` |
| Injection: messages that try to change SYM's behaviour | 5 | All 5 produce a hold or a harmless simple reply |
| Identity: header and body present and equal | Every call above | All |

Results are printed and appended to the action log. The cases live in `tests/admission/` as JSON.

## 20. Decisions filled in without the owner

These were not answered in the design session. Each is a default in config or a small piece of code, and can be changed without redesign.

| Topic | Decision |
|---|---|
| What documents are for | Reply context only, not for the owner to query |
| Document limit and formats | 1,500 tokens combined; `.txt`, `.md`, text PDFs; `shareable` off by default |
| Definition of a simple reply | Section 8.2 |
| Rate limit | 5 per chat per hour, 20 per chat per day |
| Reply over the rate limit | Held, not dropped |
| Confirming plans | Plans with an `act` step wait for `Enter` |
| Planner tools | One `submit_plan` tool; plugin tools listed in the prompt from the registry |
| `core` tools | Listing, approving and rejecting held replies, and dry-run, are also reachable through the Planner |
| Retry timing | 30 seconds doubling to 15 minutes; reply jobs dropped after 30 minutes |
| Chat context for replies | Last 10 messages of that chat |
| Chat text retention | 30 days |
| Action log retention | 30 days ("30" was heard in the session; the unit was assumed) |
| Message tables | `messages` holds text; `conversation_messages` and `chat_messages` link to it |
| Voice | `small` model, 1.5 seconds of silence, 30 second cap, transcript confirmed with `Enter` |
| Keys | `F2` to `F6`, `F9`, `Ctrl+Q` as in section 17 |
| Model admission pass marks | Section 19 |
| Send delay | Random 2 to 6 seconds |
| `prd.md` | Not edited; section 2 records where this document replaces it |

## 21. To verify during the build

- **`neonize` on Python 3.13**: version 0.5.2 publishes a `py310-none-manylinux2014_x86_64` wheel and requires Python 3.10 or later, so it should install. It has not been installed or run here.
- **`X-OmniRoute-Model` header**: whether it is present on every non-streaming response, and whether `langchain-openai` exposes response headers (`include_response_headers`). If it is not always present, the identity check in section 9 needs another source.
- **Priority combo**: whether an OmniRoute `priority` combo can ever answer from a model outside its list.
- **Model ids**: the exact OmniRoute id for OpenRouter `:free` models.
- **Groq limits**: the owner's actual limits, and whether `gpt-oss-20b` has a quota separate from `gpt-oss-120b`.
- **Instagram**: the inbox selectors, and how the page signals a lost connection.
- **Gmail**: app passwords require two-step verification on the account.
- **OmniRoute unit**: the `ExecStart` path uses the mise shim that exists today; the `serve` flags were read from `omniroute serve --help` on version 3.8.50.
