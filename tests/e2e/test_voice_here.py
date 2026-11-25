"""v0.15.0: one icon. Controls says where Jarvis is listening, moves the voice here, and has the microphone switch."""
import json

STATE = "window.__jarvis.store.state"


def serve(page, answers, posts):
    """Stand in for the hub's own /api/voicehost: the answers in turn (the last one repeats)."""
    def handle(route):
        if route.request.method == "POST":
            posts.append(route.request.url)
            if len(answers) > 1:
                answers.pop(0)
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True}))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(answers[0]))
    page.route("**/api/voicehost**", handle)


def test_another_laptop_has_the_voice_and_talk_here_moves_it(hub):
    posts, answers = [], [{"state": "waiting", "device": "laptop-b", "message": ""},
                          {"state": "live", "device": "", "message": ""}]
    serve(hub.page, answers, posts)
    page = hub.open("#/controls", scene="controls-live")
    row = page.locator('[data-setting="voice_here"]')
    row.get_by_text("Laptop B has the voice").wait_for(timeout=5000)
    page.click('[data-voice="take"]')
    row.get_by_text("Jarvis is listening and speaking through this laptop").wait_for(timeout=5000)
    assert len(posts) == 1 and posts[0].endswith("/api/voicehost/take")
    assert page.locator('[data-voice="take"]').count() == 0          # nothing to take any more


def test_it_says_in_words_when_the_voice_is_not_running_here(hub):
    serve(hub.page, [{"state": "off", "device": "", "message": "The voice part isn't installed on this laptop. Run Set up Laptop A.bat (or setup-voice.bat on Laptop B)."}], [])
    page = hub.open("#/controls", scene="controls-live")
    page.locator('[data-setting="voice_here"]').get_by_text("isn't installed on this laptop").wait_for(timeout=5000)


def test_the_microphone_switch_turns_the_mic_off_and_on(hub):
    serve(hub.page, [{"state": "live", "device": "", "message": ""}], [])
    page = hub.open("#/controls", scene="controls-live")
    mic = page.locator('[role=switch][aria-label=Microphone]')
    assert mic.get_attribute("aria-checked") == "true" and mic.inner_text() == "On"
    mic.click()
    assert page.evaluate(f"{STATE}.settings.muted") is True
    mic = page.locator('[role=switch][aria-label=Microphone]')
    assert mic.get_attribute("aria-checked") == "false" and mic.inner_text() == "Off"
    mic.click()
    assert page.evaluate(f"{STATE}.settings.muted") is False


def test_every_controls_group_still_has_at_most_four_rows(hub):
    serve(hub.page, [{"state": "live", "device": "", "message": ""}], [])
    page = hub.open("#/controls", scene="controls-live")
    rows = page.evaluate("[...document.querySelectorAll('.jv-controls__grid > section')].map(s => s.querySelectorAll(':scope > .jv-row').length)")
    assert rows and all(1 <= n <= 4 for n in rows), rows


def test_a_late_voice_answer_does_not_take_the_focus_off_the_row_he_jumped_to(hub):
    held, answer = [], {"status": 200, "content_type": "application/json",
                        "body": json.dumps({"state": "waiting", "device": "laptop-b", "message": ""})}
    late = {"on": True}
    hub.page.route("**/api/voicehost**", lambda route: held.append(route) if late["on"] else route.fulfill(**answer))
    page = hub.scene("now-awake")
    page.keyboard.press("Control+k")
    page.keyboard.type("pause memory")
    page.wait_for_function("document.getElementById('jv-live-polite').textContent.includes('result')")
    page.keyboard.press("Enter")
    focused = "document.activeElement?.closest('[data-setting]')?.dataset.setting === 'memory_paused'"
    page.wait_for_function(focused)                       # the jump has landed; the voice row is still "Starting"
    assert "Starting the voice" in page.locator('[data-setting="voice_here"]').inner_text()
    late["on"] = False
    for route in held:
        route.fulfill(**answer)                           # now the answer arrives and the view redraws
    page.locator('[data-setting="voice_here"]').get_by_text("Laptop B has the voice").wait_for(timeout=5000)
    assert page.evaluate(focused) is True
    assert hub.problems == []
