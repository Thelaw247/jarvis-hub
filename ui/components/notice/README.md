# jv-notice, jv-toast, jv-toasts (C15)

Calm messages. `<jv-notice kind="info|notice|error|empty" heading text action-label action target>`; errors say what to do next and never blame; empties are a plain card with one action (and drop their box inside a card, sheet or window). `<jv-toast>.toast` and `<jv-toasts>.toasts` show short notices, at most two, that leave on their own. A toast waits while it is hovered or focused; Esc dismisses the focused one; using its action dismisses it; when a toast that holds focus leaves, focus goes back where it was (or the view's h1).

Scene: `?scene=component:notice`.
