import asyncio
import random
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Input, Label, Markdown, RichLog, Static

SYM_THEME = Theme(
    name="sym",
    primary="#F2A574",
    secondary="#5c9cf5",
    accent="#F2A574",
    foreground="#eeeeee",
    background="#0a0a0a",
    surface="#141414",
    panel="#1e1e1e",
    success="#7fd88f",
    warning="#f5a742",
    error="#e06c75",
    dark=True,
)

PROTOCOLS = ["House Party", "Clean Slate"]
MODEL = "gpt-oss-120b"

# Left edge of a user message block.
USER_EDGE = "#B8D4E0"

TAG_COLORS = {
    "SYS": "#808080",
    "MIC": "#F2A574",
    "STT": "#5c9cf5",
    "USR": "#eeeeee",
    "LLM": "#9d7cd8",
    "MND": "#56b6c2",
    "HND": "#7fd88f",
    "TTS": "#e5c07b",
}

DUMMY_ACTIVITY = [
    ("14:01:52", "SYS", "SYM started, protocol House Party"),
    ("14:01:53", "SYS", "gateway up, model gpt-oss-120b"),
    ("14:02:07", "MIC", "listening"),
    ("14:02:11", "MIC", "silence detected, recording stopped"),
    ("14:02:12", "STT", "heard: start replying on whatsapp and show instagram unread"),
    ("14:02:12", "USR", "start replying on whatsapp and show instagram unread"),
    ("14:02:13", "LLM", "planner call, 412 tokens in"),
    ("14:02:15", "MND", "task graph built: 2 steps, 0 dependencies"),
    ("14:02:15", "MND", "s1 whatsapp.start_auto_reply"),
    ("14:02:15", "MND", "s2 instagram.unread"),
    ("14:02:16", "HND", "s1 running"),
    ("14:02:18", "HND", "s1 done: auto-reply on"),
    ("14:02:18", "HND", "s2 running"),
    ("14:02:19", "HND", "s2 done: 7 unread in 3 chats"),
    ("14:02:20", "LLM", "reply drafted, 38 tokens out"),
    ("14:02:20", "TTS", "speaking: WhatsApp auto-reply is on. You have 7 unread on Instagram."),
    ("14:02:24", "TTS", "done"),
    ("14:02:24", "SYS", "idle"),
]


class MicBox(Static):
    """Small square dot that lights up while the microphone is in use."""

    def __init__(self) -> None:
        super().__init__("■", id="mic")


class ChatLog(VerticalScroll):
    """The conversation. Follows new content until the owner scrolls up."""

    follow = True

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if new_value < old_value:
            self.follow = False
        elif new_value >= self.max_scroll_y:
            self.follow = True

    def follow_end(self) -> None:
        if self.follow:
            self.scroll_end(animate=False)


class UserMessage(Static):
    """What the owner sent: a panel with a coloured left edge."""

    def __init__(self, text: str) -> None:
        super().__init__(text, markup=False)
        self.styles.border_left = ("thick", USER_EDGE)


class ThoughtLine(Static):
    """How long the model took before its first token. Hidden until known."""

    def set_ms(self, ms: float) -> None:
        took = f"{ms:.0f}ms" if ms < 1000 else f"{ms / 1000:.1f}s"
        self.update(f"Thought · {took}")
        self.display = True


class AssistantMessage(Markdown):
    """The reply, filled in as tokens arrive."""


class MessageFooter(Static):
    """Protocol, model and total time, shown once a reply is complete."""

    def __init__(self, protocol: str, model: str, total_seconds: float) -> None:
        super().__init__(
            Text.assemble(
                ("▣ ", "dim"),
                (protocol, "bold"),
                (f" · {model} · {total_seconds:.1f}s", "dim"),
            )
        )


class AssistantTurn:
    """Handle for one assistant reply: stream tokens into it, then finish it."""

    def __init__(self, app: "SymApp", protocol: str) -> None:
        self._app = app
        self._protocol = protocol
        self._thought = ThoughtLine()
        self._message = AssistantMessage()
        self._mounted = app.chat.mount(self._thought, self._message)
        self._stream = Markdown.get_stream(self._message)

    def set_thought_ms(self, ms: float) -> None:
        self._thought.set_ms(ms)
        self._app.chat.follow_end()

    async def append(self, token: str) -> None:
        if self._mounted is not None:
            await self._mounted
            self._mounted = None
        await self._stream.write(token)
        self._app.chat.follow_end()

    async def finish(self, total_seconds: float) -> None:
        await self._stream.stop()
        footer = MessageFooter(self._protocol, MODEL, total_seconds)
        await self._app.chat.mount(footer, after=self._message)
        self._app.chat.follow_end()
        self._app.log_activity("LLM", f"reply finished in {total_seconds:.1f}s")


class ListModal[T](ModalScreen[None]):
    """A centred dialog that shows a list and an input for adding to it."""

    BINDINGS = [Binding("escape", "dismiss", "Close", show=False)]

    def __init__(
        self,
        title: str,
        placeholder: str,
        items: list[T],
        parse: Callable[[str], T | None],
        show: Callable[[T], str],
    ) -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._items = items
        self._parse = parse
        self._show = show

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._title, id="dialog-title")
            yield Static(id="dialog-items")
            yield Input(placeholder=self._placeholder, id="dialog-input")
            with Horizontal(id="dialog-hints"):
                yield Label("enter", classes="key")
                yield Label("add", classes="muted")
                yield Label("esc", classes="key")
                yield Label("close", classes="muted")

    def on_mount(self) -> None:
        self._refresh_items()
        self.query_one("#dialog-input", Input).focus()

    def _refresh_items(self) -> None:
        items = self.query_one("#dialog-items", Static)
        if self._items:
            items.update(Text("\n".join(self._show(item) for item in self._items)))
        else:
            items.update(Text("Nothing here yet.", style="dim"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if not event.value.strip():
            return
        item = self._parse(event.value)
        if item is None:
            self.notify(f"Expected: {self._placeholder}", severity="warning")
            return
        self._items.append(item)
        event.input.clear()
        self._refresh_items()


def parse_contact(raw: str) -> tuple[str, str] | None:
    name, _, number = raw.partition(",")
    name, number = name.strip(), number.strip()
    return (name, number) if name and number else None


def parse_document(raw: str) -> str | None:
    return Path(raw.strip()).name or None


class SymApp(App):
    TITLE = "SYM"
    ENABLE_COMMAND_PALETTE = False

    # Priority bindings, so the focused Input doesn't swallow them.
    BINDINGS = [
        Binding("tab", "cycle_protocol", "Protocol", show=False, priority=True),
        Binding("ctrl+p", "contacts", "Contacts", show=False, priority=True),
        Binding("ctrl+d", "documents", "Documents", show=False, priority=True),
        Binding("ctrl+b", "toggle_mic", "Mic", show=False, priority=True),
        Binding("f2", "toggle_mic", "Mic", show=False, priority=True),
        Binding("pageup", "scroll_chat(-1)", "Scroll up", show=False, priority=True),
        Binding("pagedown", "scroll_chat(1)", "Scroll down", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
    ]

    CSS = """
    Screen {
        background: $background;
        color: $foreground;
    }

    .muted {
        color: $foreground 50%;
    }

    .key {
        text-style: bold;
        margin-left: 3;
        margin-right: 1;
    }

    Input {
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }

    Input:focus {
        border: none;
    }

    #sidebar {
        width: 40;
        border-right: solid $foreground 15%;
        padding: 1 2;
    }

    #activity-title {
        margin-bottom: 1;
        text-style: bold;
        color: $foreground 50%;
    }

    #activity {
        height: 1fr;
        background: transparent;
        scrollbar-size: 0 0;
    }

    #main {
        width: 1fr;
        padding: 1 2 6 2;
    }

    #mic {
        width: 1;
        height: 1;
        color: $foreground 25%;
    }

    #mic.-active {
        color: $primary;
    }

    #column {
        height: 1fr;
        align: center bottom;
    }

    #chat {
        display: none;
        height: 1fr;
        margin-top: 1;
        scrollbar-size-vertical: 1;
        scrollbar-color: $foreground 20%;
        scrollbar-background: $background;
    }

    #main.-chat {
        padding: 1 2;
    }

    #main.-chat #chat {
        display: block;
    }

    #main.-chat #prompt, #main.-chat #hints {
        max-width: 100%;
    }

    UserMessage {
        background: $surface;
        padding: 1 2;
        margin-bottom: 1;
    }

    ThoughtLine {
        display: none;
        padding: 0 3;
        margin-bottom: 1;
        color: $foreground 50%;
    }

    AssistantMessage {
        padding: 0 3;
        background: transparent;
    }

    MessageFooter {
        padding: 0 3;
        margin-bottom: 2;
    }

    #prompt, #dialog {
        height: auto;
        background: $surface;
        padding: 1 2;
    }

    #dialog {
        border-left: thick $primary;
    }

    #prompt, #hints {
        width: 100%;
        max-width: 75;
    }

    #input {
        width: 1fr;
    }

    #protocol {
        margin-left: 2;
        color: $primary;
    }

    #hints {
        height: 1;
        margin-top: 1;
        align-horizontal: right;
    }

    ListModal {
        align: center middle;
        background: $background 70%;
    }

    #dialog {
        width: 60;
        max-height: 80%;
    }

    #dialog-title {
        color: $primary;
        text-style: bold;
    }

    #dialog-items {
        margin: 1 0;
    }

    #dialog-hints {
        height: 1;
        margin-top: 1;
        align-horizontal: right;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.protocol_index = 0
        self.mic_active = False
        self.contacts: list[tuple[str, str]] = []
        self.documents: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("ACTIVITY", id="activity-title")
                yield RichLog(id="activity", wrap=True, min_width=1)
            with Vertical(id="main"):
                yield MicBox()
                with Vertical(id="column"):
                    yield ChatLog(id="chat", can_focus=False)
                    with Horizontal(id="prompt"):
                        yield Input(placeholder="Ask anything...", id="input")
                        yield Label(PROTOCOLS[0], id="protocol")
                    with Horizontal(id="hints"):
                        yield Label("ctrl+b", classes="key")
                        yield Label("mic", classes="muted")
                        yield Label("ctrl+p", classes="key")
                        yield Label("contacts", classes="muted")
                        yield Label("ctrl+d", classes="key")
                        yield Label("documents", classes="muted")

    def on_mount(self) -> None:
        self.register_theme(SYM_THEME)
        self.theme = "sym"
        self.query_one("#activity", RichLog).can_focus = False
        for at, tag, message in DUMMY_ACTIVITY:
            self.log_activity(tag, message, at=at)
        self.query_one("#input", Input).focus()

    @property
    def protocol(self) -> str:
        return PROTOCOLS[self.protocol_index]

    @property
    def chat(self) -> ChatLog:
        return self.query_one("#chat", ChatLog)

    # Public API: call these from the STT / LLM side.

    def add_user_message(self, text: str) -> None:
        """Show a message from the owner. The first one switches to the chat view."""
        self.query_one("#main").add_class("-chat")
        self.chat.mount(UserMessage(text))
        self.chat.follow = True
        self.chat.follow_end()

    def start_assistant_message(self) -> AssistantTurn:
        """Start an empty reply and return the handle to stream into."""
        return AssistantTurn(self, self.protocol)

    def set_mic(self, active: bool) -> None:
        """Light the mic dot while the microphone is in use."""
        self.mic_active = active
        self.query_one("#mic", MicBox).set_class(active, "-active")

    def log_activity(self, tag: str, message: str, *, at: str | None = None) -> None:
        """Append a line to the activity log. `at` defaults to the current time."""
        at = at or datetime.now().strftime("%H:%M:%S")
        color = TAG_COLORS.get(tag, "#eeeeee")
        entry = Text.assemble((tag, f"bold {color}"), "  ", (at, "dim"), "\n", message, "\n")
        self.query_one("#activity", RichLog).write(entry)

    # Actions

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("cycle_protocol", "contacts", "documents"):
            return not isinstance(self.screen, ModalScreen)
        return True

    def action_cycle_protocol(self) -> None:
        self.protocol_index = (self.protocol_index + 1) % len(PROTOCOLS)
        self.query_one("#protocol", Label).update(self.protocol)
        self.log_activity("SYS", f"protocol changed to {self.protocol}")

    def action_contacts(self) -> None:
        self.push_screen(
            ListModal(
                "Contacts",
                "Name, number",
                self.contacts,
                parse_contact,
                lambda contact: f"{contact[0]}  {contact[1]}",
            )
        )

    def action_documents(self) -> None:
        self.push_screen(
            ListModal("Documents", "Path to a file", self.documents, parse_document, str)
        )

    def action_toggle_mic(self) -> None:
        self.set_mic(not self.mic_active)

    def action_scroll_chat(self, direction: int) -> None:
        if direction < 0:
            self.chat.scroll_page_up()
        else:
            self.chat.scroll_page_down()

    @on(Input.Submitted, "#input")
    def submit_prompt(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        self.log_activity("USR", text)
        self.add_user_message(text)
        self.run_worker(self._simulate_reply(text))

    async def _simulate_reply(self, prompt: str) -> None:
        """Stand-in for the model: streams a canned reply with real measured timings."""
        reply = (
            f"This is a simulated reply to **{prompt}**. No model is connected yet.\n\n"
            "Once the real stream is wired in, this text arrives the same way:\n\n"
            "- `start_assistant_message()` opens an empty reply\n"
            "- `append(token)` adds each token as it comes\n"
            "- `finish(total_seconds)` adds the line below\n"
        )
        started = time.monotonic()
        turn = self.start_assistant_message()
        await asyncio.sleep(random.uniform(0.2, 0.9))
        turn.set_thought_ms((time.monotonic() - started) * 1000)
        for token in re.findall(r"\S+\s*", reply):
            await turn.append(token)
            await asyncio.sleep(random.uniform(0.02, 0.07))
        await turn.finish(time.monotonic() - started)


def main() -> None:
    SymApp().run()


if __name__ == "__main__":
    main()
