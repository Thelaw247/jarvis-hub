# jv-page-dots and jv-tabs (C04; HUD v3 §14 decision 2)

**Page dots** (`<jv-page-dots>`): the five views (Now · Today · Life · Activity · Controls) as Huw's dots under the
icon row; the Rail draws one on every screen but the phone. The view he is on is a short bar, the others small
dots; each is a plain link (24 × 20 target) named by its view, with `aria-current="page"` on the one he's on and
`aria-keyshortcuts` 1–5. ← → Home End move along them. The landmark is named "Views". The count of things
waiting for his yes is said to screen readers on Activity; its amber mark is the Your yes icon's badge, so it
isn't repeated here.

**Tabs** (`<jv-tabs>`): the same five, now only the phone's bottom tab bar (an icon above each word, the orb at
the bar's right end, `core/shell.css`). On every other screen the header's copy is hidden: no pills in the
top-right corner. The one badge is the count waiting for your yes, on Activity.

`.tabs`, `.current`, `.badge`. Both emit `jv-nav`. Keys 1–5 are handled by `core/keys.js`.
Scene: `?scene=component:tabs`.
