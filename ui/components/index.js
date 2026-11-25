// Component registry. Only the overseer edits this file (one import per merged component).
// Each component folder registers its own custom element when imported.
import "./window/window.js";        // C06
import "./orb/orb.js";              // C01
import "./now-card/now-card.js";    // C13
import "./tabs/tabs.js";            // C04
import "./source-chip/source-chip.js"; // C07
import "./notice/notice.js";        // C15
import "./clock/clock.js";  // C02
import "./status-line/status-line.js";  // C03
import "./big-number/big-number.js";  // C09
import "./caption/caption.js";  // C16
import "./working-on/working-on.js";  // C20
import "./file-tile/file-tile.js";  // C19
import "./plant/plant.js";  // C17
import "./command-bar/command-bar.js";  // C05
import "./fact-card/fact-card.js";  // C08
import "./mini-chart/mini-chart.js";  // C10
import "./action-row/action-row.js";  // C11
import "./approval-card/approval-card.js";  // C12
import "./branch-card/branch-card.js";  // C14
import "./timeline/timeline.js";  // C18
import "./glance/glance.js";  // N5a: the seven glance codes
import "./thumb/thumb.js";  // N5a: pictures with big labels
import "./rail/rail.js";  // N4: the Rail
import "./resume-card/resume-card.js";  // N6: "here's where you stopped"
import "./day-dial/day-dial.js";  // N3: today around the orb
import "./agent-task/agent-task.js";  // R3: the Claude task window (registers window kind agent_task)
import "./agent-ask/agent-ask.js";  // R3: Allow / Deny / Allow for this task on agent asks (approval-card answers hook)
import "./web-frame/web-frame.js";  // R1: web windows (registers window kind web)
import "./day-map/day-map.js";  // R2: the campus map window (registers window kind map)
