// View registry. Only the overseer edits this file (one import + one route per merged view).
import { router } from "../core/router.js";
import "./now/now.js";            // V01
import "./today/today.js";        // V02
import "./life/life.js";          // V03a, V03b, V03c (+ branch page V03d)
import "./memory/memory.js";      // V03e
import "./activity/activity.js";  // V04
import "./controls/controls.js";  // V05
import "./hood/hood.js";          // V06
import "./strip/strip.js";        // V07
import "./phone/phone.js";        // V08
import "./reader/reader.js";      // N6: /read/<thread id> (registers its own route)
import "./reach/reach.js";        // R3: /controls/reach and /activity/tasks (register their own routes)
import "./keys/keys.js";          // K2: /controls/keys (registers its own route)

router.register("/now", "jv-view-now", "now", "Now");
router.register("/today", "jv-view-today", "today", "Today");
router.register("/life", "jv-view-life", "life", "Life");
router.register("/activity", "jv-view-activity", "activity", "Activity");
router.register("/controls", "jv-view-controls", "controls", "Controls");
router.register("/debug", "jv-view-placeholder", "controls", "Event log");
router.register("/controls/hood", "jv-view-hood", "controls", "Under the hood");
router.register("/strip", "jv-view-strip", "now", "Strip");
router.register("/life/memory", "jv-view-memory", "life", "Everything Jarvis knows");
router.register("/life/unsorted", "jv-view-unsorted", "life", "Unsorted");
