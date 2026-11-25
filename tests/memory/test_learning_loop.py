"""v0.20.0: the learning loop on the real memory store. He is remembered, the memory reaches the next prompt, a changed
mind replaces the old one, "forget that" works, and nothing is saved while memory is paused or off the record."""
import asyncio
import json
from types import SimpleNamespace

from jarvis.core.learning import Learner


class Bus:
    def __init__(self): self.sent = []
    def publish(self, kind, data=None): self.sent.append((kind, data or {}))


class Keyed:
    async def call(self, run): return await run("key-1")


class Settings:
    def __init__(self): self.values = {}
    def hub(self): return self.values


def fake_claude(replies, seen):
    """An Anthropic client whose answers are scripted; records what it was asked."""
    class Messages:
        async def create(self, **kw):
            seen.append(kw)
            return SimpleNamespace(content=[SimpleNamespace(text=replies.pop(0))])
    return lambda key: SimpleNamespace(messages=Messages())


def test_what_he_says_is_saved_once_used_replaced_and_forgotten(store, run):
    bus, settings = Bus(), Settings()
    learner = Learner(store, Keyed(), bus, settings)
    said = run(learner.save("Prefers the questions opened before the solutions", "preference",
                            his_words="always open the questions first, not the solutions", scope="when pulling up work"))
    assert said == "Saved in memory: Prefers the questions opened before the solutions"
    assert run(learner.save("prefers the questions opened before the solutions.", "preference")) == "Already in memory: nothing to add."
    assert run(store.standing()) == ["Prefers the questions opened before the solutions (when pulling up work)"]
    assert [d["text"] for k, d in bus.sent if k == "toast"] == ["Remembered: Prefers the questions opened before the solutions"]
    assert "Prefers the questions opened before the solutions" in run(learner.recall("pull up the questions for practice six"))

    run(learner.save("Calls GE 122 mechanics", "fact", his_words="mechanics is GE 122"))
    assert run(store.standing()) == ["Prefers the questions opened before the solutions (when pulling up work)"]   # a fact is not a rule

    changed = run(learner.save("Prefers the solutions opened next to the questions", "preference", replaces="questions opened before the solutions"))
    assert changed.startswith("Updated in memory")
    assert run(store.standing()) == ["Prefers the solutions opened next to the questions"]            # the old one is retired, not doubled

    assert run(learner.forget("solutions opened next to the questions")) == "Forgotten: Prefers the solutions opened next to the questions"
    assert run(store.standing()) == []
    assert ("fact.updated", True) in [(k, d.get("forgotten")) for k, d in bus.sent]
    assert run(learner.forget("something never said")).startswith(("Nothing in memory matches", "Forgotten"))


def test_pause_memory_and_off_the_record_stop_every_save(store, run):
    settings = Settings()
    learner = Learner(store, Keyed(), Bus(), settings)
    settings.values = {"memory_paused": True}
    assert run(learner.save("Prefers tea", "preference")) == "Not saved: memory is paused in Controls."
    settings.values = {"off_record": True}
    assert run(learner.save("Prefers tea", "preference")) == "Not saved: this conversation is off the record."
    assert run(store.standing()) == []
    seen = []
    learner = Learner(store, Keyed(), Bus(), settings, client_factory=fake_claude(["[]"], seen))

    async def turn():
        learner.heard("from now on never book anything before nine", "Noted.")
        await asyncio.sleep(0.05)

    run(turn())
    assert seen == []                                               # off the record: the background pass never runs


def test_the_background_pass_only_notices_and_jarvis_offers_once_and_he_decides(store, run):
    """His rule of 2026-11-22: "he should always verify with me before committing things to memory"."""
    seen, bus = [], Bus()
    replies = [json.dumps([{"op": "add", "kind": "procedure", "text": "Never book anything before nine in the morning"},
                           {"op": "add", "kind": "fact", "text": "Studies with Alex on Thursdays", "about": "Study squad"},
                           {"op": "add", "kind": "fact", "text": "A third thing that is over the limit"}]),
               "Sure! Here you go: [not json"]
    learner = Learner(store, Keyed(), bus, Settings(), client_factory=fake_claude(replies, seen))
    noticed = run(learner.learn("from now on never book anything before nine, and I study with Alex on Thursdays", "Noted."))
    assert noticed == ["Never book anything before nine in the morning", "Studies with Alex on Thursdays"]        # two at most
    asked = seen[0]["messages"][0]["content"]
    assert "De Wet said: from now on never book anything before nine" in asked and "Jarvis replied: Noted." in asked
    assert run(store.standing()) == [] and bus.sent == []            # nothing was saved, nothing was shown as remembered
    block = run(learner.recall("what is due this week"))
    assert "# Worth offering to remember" in block and "- Never book anything before nine in the morning" in block
    assert "Worth offering" not in run(learner.recall("what is due this week"))                                 # offered once, not nagged
    assert run(learner.learn("what's the weather like today then", "Cold.")) == []                             # a broken answer notices nothing
    said = run(learner.save("Never book anything before nine in the morning", "procedure", his_words="yes"))    # he said yes
    assert said.startswith("Saved in memory") and run(store.standing()) == ["Never book anything before nine in the morning"]


def test_remember_does_nothing_until_he_has_said_yes(store, run):
    from jarvis.tools.remember import handler

    ctx = SimpleNamespace(learner=Learner(store, Keyed(), Bus(), Settings()))
    first = run(handler.run({"text": "Prefers the notes open beside the assignment", "kind": "preference"}, ctx))
    assert first.content.startswith("Not saved yet: he wants to be asked first") and first.is_error is False
    assert run(store.standing()) == []
    yes = run(handler.run({"text": "Prefers the notes open beside the assignment", "kind": "preference", "confirmed": True}, ctx))
    assert yes.content.startswith("Saved in memory") and run(store.standing()) == ["Prefers the notes open beside the assignment"]


def test_a_turn_never_waits_for_learning_and_short_turns_are_skipped(store, run):
    seen = []
    learner = Learner(store, Keyed(), Bus(), Settings(), client_factory=fake_claude(["[]", "[]"], seen))

    async def turns():
        learner.heard("yes please", "Done.")                         # nothing to learn from two words
        learner.saved_this_turn = True
        learner.heard("always open the questions first please", "Noted.")   # he was already saved on purpose this turn
        await asyncio.sleep(0.05)
        first = len(seen)
        learner.heard("I usually study in the library after lunch", "Good to know.")
        waited = len(seen)                                           # heard() returned at once: nothing ran yet
        await asyncio.sleep(0.05)
        return first, waited, len(seen)

    assert run(turns()) == (0, 0, 1)
    assert run(learner.recall("hi")) == ""                           # one word: no lookup


def test_recall_gives_up_rather_than_hold_the_answer(run):
    class Slow:
        async def hot_recall(self, text):
            await asyncio.sleep(1)

    assert run(Learner(Slow(), Keyed(), Bus()).recall("what is due this week")) == ""


def test_the_talker_gets_memory_before_it_answers_and_hands_the_turn_over_after():
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.talker_t1 import TalkerT1

    talker = TalkerT1(VoiceConfig(), keyed=None, now_card=lambda: "# Now\nSunday")
    talker._recalled = "# From memory\n- Prefers the questions first"
    blocks = [b["text"] for b in talker.build_request("pull up practice six")["system"]]
    assert blocks[-1].startswith("# From memory") and blocks[-2].startswith("# Now")
    assert "cache_control" not in talker.build_request("x")["system"][-1]      # it changes every turn: never cached
    learned = []
    talker.on_learn = lambda user, reply: learned.append((user, reply))
    talker.remember("always open the questions first", "Noted.")
    assert learned == [("always open the questions first", "Noted.")] and len(talker.history) == 2
    talker.on_learn = lambda user, reply: 1 / 0                                # learning can never break a turn
    talker.remember("again", "Yes.")


def test_the_core_wires_the_learner_and_the_hubs_forget_button(tmp_path):
    from fastapi.testclient import TestClient

    from jarvis.core.app import create_app
    from jarvis.core.config import Config
    from jarvis.core.sessions import HubSessions

    config = Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver",), keystore="memory", voice_preload=False, hub_feed=False)
    app = create_app(config, log_to_stderr=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("test-hub", can_write=True)
    with TestClient(app, headers={"X-Jarvis-Session": token}) as client:
        toolkit = app.state.toolkit
        assert toolkit.learner is not None and toolkit.make_ctx().learner is toolkit.learner
        assert getattr(app.state.voice, "learner", None) is toolkit.learner
        rows = {r["id"]: r["status"] for r in toolkit.reach()["tools"]}
        assert rows["remember"] == "connected" and rows["forget"] == "connected"
        bad = client.post("/api/act", json={"action": "forget", "target": "x", "args": {}}).json()
        assert bad["ok"] is False and "Nothing was changed" in bad["message"]
        assert client.post("/api/act", json={"action": "forget", "target": "f-424242", "args": {}}).json()["ok"] is True
