"""The page script behind read_page and find: an accessibility-style tree with element references.

Each element worth naming gets a stable ``data-jv-ref="ref_N"`` attribute (scoped to the tab; stale after a
navigation), so a later click or form fill can target it exactly, as in Claude's own browser tools.
"""

SNAPSHOT_JS = r"""
({ rootRef, depth, filter, query }) => {
  const MAX = 50000;
  if (!window.__jvRef) window.__jvRef = 0;
  const INTERACTIVE = new Set(['a','button','input','select','textarea','summary','details','option']);
  const roleOf = (el) => {
    const r = el.getAttribute('role'); if (r) return r;
    const t = el.tagName.toLowerCase();
    if (t === 'a') return el.hasAttribute('href') ? 'link' : '';
    if (t === 'button' || t === 'summary') return 'button';
    if (t === 'select') return 'combobox';
    if (t === 'textarea') return 'textbox';
    if (t === 'input') {
      const ty = (el.getAttribute('type') || 'text').toLowerCase();
      if (ty === 'hidden') return '';
      if (['button','submit','reset','image'].includes(ty)) return 'button';
      if (ty === 'checkbox') return 'checkbox';
      if (ty === 'radio') return 'radio';
      if (ty === 'password') return 'password';
      if (ty === 'search') return 'searchbox';
      return 'textbox';
    }
    if (/^h[1-6]$/.test(t)) return 'heading';
    return {img:'img', nav:'navigation', main:'main', form:'form', table:'table', tr:'row', td:'cell', th:'columnheader',
            li:'listitem', ul:'list', ol:'list', dialog:'dialog', header:'banner', footer:'contentinfo', label:'label',
            p:'paragraph', iframe:'iframe'}[t] || '';
  };
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inView = (el) => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.right > 0 &&
    r.top < innerHeight && r.left < innerWidth; };
  const clip = (s, n) => { s = (s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
  const nameOf = (el, role) => {
    const a = el.getAttribute('aria-label'); if (a) return clip(a, 100);
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const t = lb.split(/\s+/).map((id) => document.getElementById(id)?.innerText || '').join(' '); if (t.trim()) return clip(t, 100); }
    if (el.tagName === 'IMG') return clip(el.getAttribute('alt') || el.getAttribute('title') || '', 100);
    if (['textbox','searchbox','combobox','checkbox','radio','password'].includes(role)) {
      if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clip(l.innerText, 100); }
      const wrap = el.closest('label'); if (wrap) return clip(wrap.innerText, 100);
      return clip(el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || '', 100);
    }
    return clip(el.innerText || el.getAttribute('title') || '', role === 'paragraph' || role === 'cell' ? 200 : 100);
  };
  const ref = (el) => { let r = el.getAttribute('data-jv-ref'); if (!r) { r = 'ref_' + (++window.__jvRef); el.setAttribute('data-jv-ref', r); } return r; };
  const interactive = (el, role) => INTERACTIVE.has(el.tagName.toLowerCase()) || ['button','link','checkbox','radio',
    'textbox','searchbox','combobox','menuitem','tab','switch','option','password'].includes(role) || el.hasAttribute('onclick')
    || el.getAttribute('contenteditable') === 'true';
  const extra = (el, role) => {
    const out = [];
    if (role === 'link') { const h = el.getAttribute('href') || ''; if (h && !h.startsWith('javascript')) out.push('href="' + clip(h, 120) + '"'); }
    if (['textbox','searchbox','combobox'].includes(role) && el.value) out.push('value="' + clip(el.value, 60) + '"');
    if (role === 'password') out.push('(password: never type here)');
    if (['checkbox','radio'].includes(role)) out.push(el.checked ? 'checked' : 'unchecked');
    if (role === 'heading') out.push('level=' + el.tagName[1]);
    if (el.disabled) out.push('disabled');
    return out.length ? ' ' + out.join(' ') : '';
  };
  const root = rootRef ? document.querySelector(`[data-jv-ref="${rootRef}"]`) : document.body;
  if (!root) return { error: `No element ${rootRef} on this page (it may be stale: read the page again).` };
  const lines = []; let size = 0; const found = [];
  const words = (query || '').toLowerCase().split(/\W+/).filter((w) => w.length > 1);
  const walk = (el, d, ind) => {
    if (size > MAX || d > depth) return;
    for (const c of el.children) {
      if (!visible(c)) continue;
      const role = roleOf(c);
      const inter = interactive(c, role);
      const keep = role && (filter !== 'interactive' || inter) && (filter === 'all' || inView(c) || query);
      let next = ind;
      if (keep) {
        const name = nameOf(c, role);
        if (name || inter) {
          const line = `${'  '.repeat(ind)}- ${role}${name ? ' "' + name.replace(/"/g, "'") + '"' : ''} [${ref(c)}]${extra(c, role)}`;
          if (words.length) {
            const hay = (role + ' ' + name + ' ' + (c.getAttribute('placeholder') || '')).toLowerCase();
            const score = words.filter((w) => hay.includes(w)).length;
            if (score) found.push([score + (inter ? 0.5 : 0), line.trim()]);
          } else { lines.push(line); size += line.length + 1; }
          next = ind + 1;
        }
      }
      if (!['SELECT','SVG','svg'].includes(c.tagName)) walk(c, d + 1, next);
    }
  };
  walk(root, 0, 0);
  if (words.length) {
    found.sort((a, b) => b[0] - a[0]);
    return { text: found.slice(0, 20).map((f) => f[1]).join('\n') || 'No matching elements.' };
  }
  let text = lines.join('\n');
  if (size > MAX) text = text.slice(0, MAX) + '\n[…cut at 50,000 characters: read a subtree with ref, or a smaller depth]';
  return { text: text || '(nothing visible: scroll, or read with filter "all")' };
}
"""

PAGE_TEXT_JS = r"""
() => {
  const pick = document.querySelector('main, article, [role=main]') || document.body;
  const t = (pick.innerText || '').replace(/\n{3,}/g, '\n\n').trim();
  return t.length > 50000 ? t.slice(0, 50000) + '\n[…cut at 50,000 characters]' : t;
}
"""
