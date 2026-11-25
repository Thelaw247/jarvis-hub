"""R3: Reach in the hub, the way he'd use it: what Jarvis can do, the Claude task window, its permission ask on the
same approval card, Activity › Tasks with undo, and the email catches in Messages."""
import pytest

SCENES = ["reach", "reach-game", "reach-strict", "reach-empty", "messages-catches", "task-starting", "task-running", "task-waiting",
          "task-ask-again", "task-parked", "task-done", "task-stopped", "task-undone", "tasks", "tasks-empty", "task-detail",
          "task-detail-waiting", "component:agent-task"]


@pytest.mark.parametrize("name", SCENES)
def test_every_reach_scene_opens_cleanly(hub, name):
    hub.scene(name, theme="night")
    hub.page.wait_for_timeout(150)
    assert hub.problems == []


def test_the_ladder_lists_every_rung_and_tool_with_its_status(hub):
    page = hub.scene("reach", theme="night")
    assert page.locator(".jv-reach__rung").count() == 6
    assert page.locator(".jv-reach__tool").count() == 11
    gh = page.locator('[data-tool="github"]')
    assert "Needs sign-in" in gh.text_content() and "Never used" in gh.text_content()
    assert page.locator(".jv-reach__list .jv-reach__path").all_inner_texts() == [
        "Documents", "Desktop", "OneDrive\\Class Content", "OneDrive\\Class Management", "Jarvis Workspace"]
    assert "Not set up" in page.locator('[data-app="office"]').text_content()
    assert page.input_value('input[name="task"]') == "1" and page.input_value('input[name="day"]') == "5"
    page = hub.scene("reach-game", theme="night")
    assert "Paused in game mode" in page.locator('[data-tool="files-a"]').text_content()
    assert "Connected" in page.locator('[data-tool="files-b"]').text_content()  # Laptop B keeps working


def test_reach_controls_go_through_actions_and_are_checked(hub):
    page = hub.scene("reach", theme="night")
    page.click('[data-key="tool-gmail"]')
    page.wait_for_function("window.__jarvis.store.state.reach.tools.find(t => t.id === 'gmail').on === false")
    page.fill("#reach-add", "OneDrive/Projects")
    page.click('[data-key="add"]')
    page.wait_for_function("window.__jarvis.store.state.reach.folders.includes('OneDrive\\\\Projects')")
    page.click('[data-key="rm-0"]')
    page.wait_for_function("!window.__jarvis.store.state.reach.folders.includes('Documents')")
    page.fill("#reach-add", "C:\\Users\\dewet\\AppData")
    page.click('[data-key="add"]')
    page.wait_for_selector("jv-toasts >> text=off limits")
    assert not any("AppData" in f for f in hub.state("s => s.reach.folders"))
    page.fill('input[name="task"]', "9")
    page.click('[data-key="cap-save"]')
    page.wait_for_selector("jv-toasts >> text=whole day's cap")
    page.fill('input[name="task"]', "2")
    page.fill('input[name="day"]', "8")
    page.click('[data-key="cap-save"]')
    page.wait_for_function("window.__jarvis.store.state.reach.caps.task_usd === 2")
    page.click('[data-key="revoke-sp-file"]')
    page.wait_for_function("!window.__jarvis.store.state.settings.standing_permissions.some(p => p.id === 'sp-file')")


def test_the_task_window_has_one_hero_one_line_and_no_buttons_at_rest(hub):
    page = hub.scene("task-running", theme="night")
    win = page.locator("jv-window:has(jv-agent-task)")
    assert "CLAUDE" in win.locator(".jv-window__head").inner_text().upper() and "TASK" in win.inner_text().upper()
    assert win.locator(".jv-agent-task__line").inner_text().endswith("Extruding base · 4 of 7")
    assert win.locator(".jv-agent-task__view img").count() == 1 and win.locator(".jv-agent-task__goal").count() == 0
    assert "$0.15 SO FAR" in page.locator("jv-window:has(jv-agent-task)").inner_text().upper()
    stop = win.locator('[data-key="stop"]')
    page.mouse.move(5, 5)
    assert stop.evaluate("b => getComputedStyle(b.parentElement).opacity") == "0"  # no buttons at rest
    stop.focus()
    assert stop.evaluate("b => getComputedStyle(b.parentElement).opacity") == "1"  # on keyboard focus
    stop.click()
    page.wait_for_function("window.__jarvis.store.state.tasks[0].state === 'stopped'")
    assert win.locator(".jv-agent-task__line").inner_text().endswith("You stopped it.")


def test_the_ask_is_the_approval_card_with_allow_and_deny(hub):
    page = hub.scene("task-detail-waiting", theme="night")
    card = page.locator("jv-approval-card")
    assert card.locator("button").all_inner_texts() == ["Allow", "Deny"]  # Allow for this task only after a similar ask
    assert "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?" in card.inner_text()
    card.locator('[data-key="yes"]').click()
    page.wait_for_function("window.__jarvis.store.state.tasks[0].state === 'running'")
    assert hub.state("s => s.approvals.find(a => a.id === 'ap-task-stand-1').status") == "approved"
    page = hub.scene("task-ask-again", theme="night")
    assert page.locator("jv-approval-card button").all_inner_texts() == ["Allow", "Deny", "Allow for this task"]
    page.click('jv-approval-card [data-key="task"]')
    page.wait_for_function("window.__jarvis.store.state.tasks[0].allowed.includes('create:fusion projects')")
    page = hub.scene("activity", theme="night")  # an ordinary approval keeps its own answers
    assert page.locator("jv-approval-card button").first.inner_text() == "Yes, do it"


def test_tasks_in_activity_keep_their_transcript_and_undo(hub):
    page = hub.scene("task-detail", theme="night")
    assert page.locator(".jv-tasks__steps li").count() == 7
    assert "Stand v1.f3d" in page.locator(".jv-tasks__files").inner_text()
    assert page.locator(".jv-tasks__log li").count() >= 3
    page.click('[data-key="undo-task-stand"]')
    page.wait_for_function("window.__jarvis.store.state.tasks[0].state === 'undone'")
    assert "In the undo bin" in page.locator(".jv-tasks__files").text_content()
    page = hub.scene("tasks", theme="night")
    assert page.locator(".jv-tasks__row").count() == 2
    page.click('[data-key="open-task-stand"]')
    assert page.evaluate("window.__jarvis.router.current.path") == "/activity/tasks/task-stand"


def test_parked_is_not_failed(hub):
    page = hub.scene("task-parked", theme="night")
    line = page.locator("jv-agent-task .jv-agent-task__line")
    assert line.locator(".jv-glance").get_attribute("aria-label") == "Parked" and "create Stand v1.f3d" in line.inner_text()
    assert any(i["ref"] == "ap-task-stand-1" for i in hub.state("s => s.rail.slots.yes.items")) or hub.state("s => s.approvals[0].status") == "pending"


def test_email_catches_are_one_line_each_and_read_only(hub):
    page = hub.scene("messages-catches", theme="night")
    cards = page.locator(".jv-rail__card")
    titles = cards.locator(".jv-rail__title").all_inner_texts()
    assert "Prof: GE 122 lab moved to Thursday" in titles
    assert page.locator(".jv-rail__fan :text-matches('Reply|Draft', 'i')").count() == 0


def test_the_demo_task_plays_on_the_hub(hub):
    page = hub.open("#/activity/tasks")
    page.click('[data-key="demo"]')
    page.wait_for_function("(window.__jarvis.store.state.tasks || []).some(t => t.id === 'task-stand' && t.state === 'waiting')", timeout=20_000)
    ask = hub.state("s => s.approvals.find(a => a.category === 'agent' && a.status === 'pending')")
    assert ask["read_back"] == "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?"
    page.goto(f"{hub.base}/#/activity/tasks/task-stand")
    page.click('jv-approval-card [data-key="yes"]')
    page.wait_for_function("window.__jarvis.store.state.tasks.find(t => t.id === 'task-stand').state === 'done'")
    page.click('[data-key="undo-task-stand"]')
    page.wait_for_function("window.__jarvis.store.state.tasks.find(t => t.id === 'task-stand').state === 'undone'")
    assert hub.problems == []
