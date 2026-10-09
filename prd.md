# SYM — Product Requirements

Status: agreed in the design session of 2026-10-09. Implementation detail belongs in the TRD (see [Deferred to the TRD](#deferred-to-the-trd)).

## 1. Summary

SYM is a personal AI assistant that runs errands for one person on their own Arch Linux laptop. It checks the school learning platform, replies to simple messages on WhatsApp and Instagram for an allowlist of people, and summarises school email. The owner talks to it through a terminal CLI, by typing or by voice.

Two properties matter as much as the errands themselves:

- **Transparency**: the owner can always see what SYM did and why.
- **Extensibility**: a new errand is a new plugin, not a rewrite.

## 2. Context and constraints

| Constraint | Decision |
|---|---|
| Users | One: the owner. No multi-user support, no packaging for others. |
| Where it runs | The owner's laptop only. Nothing happens while the laptop is asleep. |
| Who writes the code | AI, on the `vibecode` branch, directed and reviewed by the owner. |
| Starting point | A fresh start. Earlier prototypes (`~/Projects/temp`, the `Ear` class) are reference only. |
| Cost | Free model tiers only. No paid credits for now. |
| Language | Python 3.13, managed with `uv`. |

## 3. Goals

1. Tell the owner about new homework and notices on mysecondteacher twice a day without them opening the site.
2. Reply to simple messages from allowlisted people on WhatsApp and Instagram, clearly marked as sent by SYM.
3. Send the owner a digest of school email with the important information extracted.
4. Accept commands by voice as well as text.
5. Record every action so the owner can audit it.

## 4. Non-goals

- Writing documents.
- Spoken output (text to speech).
- Making commitments, spending money, or deleting anything on the owner's behalf.
- Starting conversations with people.
- Running on a server or phone, or reaching the owner outside the terminal.
- An always-listening microphone or wake word.

## 5. Interface

### 5.1 Terminal CLI

The CLI is the only interface. The owner uses it to give instructions, start and stop plugins, see pending drafts, approve or reject actions, and read results such as the "what's due" list.

### 5.2 Voice input

- The owner presses a key to start recording.
- Recording ends automatically after a short period of silence.
- Speech is transcribed on the laptop with `faster-whisper`; audio does not leave the machine.
- The transcript is treated exactly like typed input.

### 5.3 Approvals

Anything SYM is not allowed to do on its own appears in the terminal as a pending item. The owner approves or rejects it there. There is no other approval channel.

## 6. Errands

Each errand is one plugin (see [8.3](#83-plugins)).

### 6.1 mysecondteacher

- **What**: report new homework and notices from the owner's school account on mysecondteacher.com.np.
- **When**: 07:00 and 19:00. If the laptop was asleep, a separate service runs the missed check on wake; the model call happens after that.
- **How**: Playwright driving Chromium with a saved login.
- **Output**: a desktop notification for new items, and a "what's due" list in the terminal on request.
- **Access**: read-only. SYM never submits, edits or deletes anything on the platform.

### 6.2 WhatsApp

- **What**: read incoming messages and reply to simple ones from allowlisted people.
- **How**: the `neonize` library, linked to the owner's main number as a companion device.
- **When**: only after the owner starts the plugin, until they stop it.

### 6.3 Instagram

- **What**: read incoming direct messages and reply to simple ones from allowlisted people.
- **How**: Playwright driving Chromium logged in as the owner.
- **When**: only after the owner starts the plugin, until they stop it. While running, it watches for new messages.

### 6.4 School email digest

- **What**: read the school Google account, extract the important information, summarise, and send the digest to the owner's main address.
- **How**: read-only access to the school account. The digest is sent from the owner's personal account to itself, so SYM never sends from the school account.
- **Built last.**

## 7. Reply policy

These rules apply to WhatsApp and Instagram.

| Situation | SYM's behaviour |
|---|---|
| Sender is on the allowlist and the reply is simple | Replies automatically |
| Reply would involve a commitment | Does not send; creates a draft for approval |
| Sender is not on the allowlist | Does not send; creates a draft for approval |
| SYM is unsure | Does not send; creates a draft for approval |

- Every automatic reply carries a tag identifying it as sent by SYM.
- The allowlist is owned and edited by the owner.
- Any action that sends, spends or deletes, other than an allowlisted simple reply, needs the owner's approval. Read-only actions need none.

## 8. Architecture requirements

### 8.1 Model access

- Models are called through a LangChain chat model.
- The tool loop is SYM's own code, not a prebuilt agent framework.
- All calls go through the local OmniRoute gateway (`http://localhost:20128/v1`), which routes to Groq and OpenRouter free tiers.
- Calls are non-streaming, with one tool call at a time.

### 8.2 Allowed models

In priority order, as one OmniRoute combo with the `priority` strategy:

1. `groq/openai/gpt-oss-120b`
2. `groq/openai/gpt-oss-20b`
3. `openrouter/nvidia/nemotron-3-super-120b-a12b:free`

Requirements:

- The list lives in configuration, not in code, because free models are withdrawn often.
- A model joins the list only after passing a fixed test of SYM's tools.
- SYM checks which model actually answered each call. A response from a model outside the list is discarded.
- When a response is discarded or all free quotas are exhausted, the work is queued and retried later. SYM never falls back to an untested model.
- Text sent to a model is trimmed to fit Groq's limit of 8,000 tokens per minute (about 4–5K tokens per page).

### 8.3 Plugins

- One plugin per errand, self-contained.
- Each plugin declares its tools and, for each tool, whether it is read-only or needs approval.
- Adding an errand must not require changing the core loop.

### 8.4 Isolation between sources

Text from messages, emails and web pages is untrusted: anyone can write "ignore your instructions" in a message.

- The automatic reply path has exactly one tool: reply in the same chat.
- It has no access to email, mysecondteacher, other chats or files.
- Each source is processed in its own model call.
- Content read from one source cannot trigger an action in another without the owner's approval.

### 8.5 Transparency

- **Action log**: an append-only record of every model call, tool call, approval and message sent. This is the single record of SYM's activity.
- **Dry-run mode**: shows what SYM would send or do, without doing it.

### 8.6 Credentials

- All secrets (school login, provider keys, tokens) are stored in the system keyring (GNOME Keyring, already running on the laptop). None are stored in files or in the repository.

### 8.7 OmniRoute configuration

- SYM uses its own OmniRoute API key.
- That key has request logging switched off, so message content is stored only in SYM's own log.
- That key is limited to the Groq and OpenRouter connections and the allowed models. SYM must not use sign-in (OAuth) connections such as `antigravity`.
- OmniRoute's API key requirement is switched on and its default dashboard password is changed.
- Groq and OpenRouter connections must be added; neither exists in the current install.

### 8.8 Scheduling

- Background work runs as systemd user services on the laptop.
- Scheduled checks that were missed during sleep run on wake.

## 9. Build order

Each step must be usable on its own before the next starts.

1. **Core**: tool loop, OmniRoute wiring, action log, dry-run mode, plugin structure, approvals in the terminal.
2. **mysecondteacher** plugin.
3. **WhatsApp** plugin.
4. **Instagram** plugin.
5. **Voice input**.
6. **Email digest** plugin.

## 10. Accepted risks

The owner has accepted these knowingly.

| Risk | Detail |
|---|---|
| WhatsApp ban | `neonize` is an unofficial client, which WhatsApp's terms prohibit. A ban would affect the owner's main number. |
| Instagram detection | Automated browsers break Instagram's terms and can trigger challenges or a ban. Page changes will break the plugin. |
| mysecondteacher access | There is no public API. The site can change without notice, and its privacy policy allows access to be ended without notice. |
| Free model churn | Free models are withdrawn or rate-limited at short notice, and tool-call quality varies between them. |
| Data sent to free endpoints | Friends' messages and school content go to free model providers, with no restriction on providers that may train on prompts. |
| Laptop-only | Nothing is checked or answered while the laptop is asleep or off. |

## 11. To verify before or during implementation

These came up in research and were not confirmed.

- Whether `neonize` installs on Python 3.13 on Linux x86_64.
- Whether mysecondteacher is a JavaScript single-page app, and what its notice and homework pages look like once logged in.
- The owner's actual Groq limits (console.groq.com/settings/limits), and whether `gpt-oss-20b` has a quota separate from `gpt-oss-120b`.
- Whether an OmniRoute `priority` combo can ever leave its model list, and whether the `X-OmniRoute-Model` header is present on every non-streaming response.
- The exact OmniRoute model id form for OpenRouter `:free` models.
- Whether a personal, unverified Google app reading the school account must be re-authorised every 7 days.
- The installed OmniRoute is 3.8.50; 3.8.51 is current.

## 12. Deferred to the TRD

- The queue design for discarded and rate-limited work (an `asyncio` queue was suggested).
- How the Instagram plugin detects new messages and how often it looks.
- Limits on automatic replies per chat.
- The format and location of the action log and the configuration files.
- The CLI's commands, and how the CLI talks to the background services.
- The plugin interface in detail.
- The model test suite used to admit a model to the allowed list.
- Silence-detection thresholds and the recording key.
- The wording of the SYM tag on automatic replies, and the definition of a "simple" reply.
- The contents of the email digest and when it is sent.
