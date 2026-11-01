// UX rules live-page probe. Measures what a static scan can't: rendered target sizes, real contrast,
// accessible names, zoom and reflow, open dialogs, competing primary buttons, layout shift and timing.
//
// Run it in the page: paste into the browser console, pass the file's text to a page-evaluate tool
// (Playwright page.evaluate, the built-in browser's javascript tool), or load it as a bookmarklet.
// It reads the page and changes nothing, except with FOCUS_CHECK = true, which moves keyboard focus
// through the first 40 focusable elements to see whether each one shows a focus indicator.
// Every result is a candidate with a selector; confirm it on screen before calling it a finding.

(async () => {
  const FOCUS_CHECK = false;
  const MAX_EXAMPLES = 15;

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity !== 0;
  };
  const path = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && parts.length < 4; n = n.parentElement) {
      let p = n.tagName.toLowerCase();
      if (n.id) { parts.unshift(p + '#' + n.id); break; }
      const cls = [...n.classList].slice(0, 2).join('.');
      if (cls) p += '.' + cls;
      const sib = n.parentElement ? [...n.parentElement.children].filter((c) => c.tagName === n.tagName) : [];
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(n) + 1})`;
      parts.unshift(p);
    }
    return parts.join(' > ');
  };
  const text = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const sample = (arr) => ({ count: arr.length, examples: arr.slice(0, MAX_EXAMPLES) });

  // Color helpers (WCAG 2.x relative luminance).
  const parseRGB = (s) => {
    const m = s && s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b, a = 1] = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [r, g, b, a];
  };
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const over = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1);
  const contrast = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
  const backgroundOf = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null; // image or gradient: can't compute
      const c = parseRGB(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    return layers.reverse().reduce((acc, c) => over(c, acc), [255, 255, 255, 1]);
  };

  const vw = innerWidth || document.documentElement.clientWidth;
  const vh = innerHeight || document.documentElement.clientHeight;
  const out = {
    url: location.href,
    viewport: { width: vw, height: vh, dpr: devicePixelRatio, visibility: document.visibilityState },
    note: 'Candidates only. Confirm each on screen; rule IDs refer to the ux-rules catalog.',
  };
  if (!vw || !vh) out.warning = 'The viewport has no size (hidden tab?): set a window or viewport size and run again.';

  // Interactive elements.
  const interactiveSel = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], ' +
    '[role=link], [role=checkbox], [role=radio], [role=switch], [role=tab], [role=menuitem], [onclick], ' +
    '[tabindex]:not([tabindex="-1"])';
  const controls = [...document.querySelectorAll(interactiveSel)].filter(visible);

  // PLT-03 target size: WCAG 2.5.8 wants 24x24 CSS px, except inline links in a sentence and undersized
  // targets whose 24 px circle (centered on the target) touches no other target and no other such circle.
  const rects = controls.map((el) => el.getBoundingClientRect());
  const undersized = rects.map((r) => r.width < 24 || r.height < 24);
  const center = (r) => [r.left + r.width / 2, r.top + r.height / 2];
  const inSentence = (el) => el.tagName === 'A' && getComputedStyle(el).display === 'inline' &&
    [...(el.parentElement?.childNodes || [])].some((n) => n.nodeType === 3 && n.textContent.trim());
  const small24 = [], small44 = [];
  controls.forEach((el, i) => {
    const r = rects[i];
    const w = Math.round(r.width), h = Math.round(r.height);
    if (undersized[i]) {
      if (inSentence(el)) return;
      const [cx, cy] = center(r);
      const crowded = rects.some((o, j) => {
        if (j === i) return false;
        if (undersized[j]) { const [ox, oy] = center(o); return Math.hypot(ox - cx, oy - cy) < 24; }
        return Math.hypot(Math.max(o.left - cx, 0, cx - o.right), Math.max(o.top - cy, 0, cy - o.bottom)) < 12;
      });
      small24.push({ selector: path(el), size: `${w}x${h}`, text: text(el), spacingExceptionApplies: !crowded });
    } else if (w < 44 || h < 44) {
      small44.push({ selector: path(el), size: `${w}x${h}`, text: text(el) });
    }
  });
  out.targetsUnder24px_PLT03 = sample(small24);
  out.targetsUnder44px_touch_PLT03 = sample(small44);

  // A11Y-04 / FRM-02 accessible names.
  const nameOf = (el) => {
    const by = el.getAttribute('aria-labelledby');
    if (by) return by.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ').trim();
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    if (el.labels && el.labels.length) return [...el.labels].map(text).join(' ').trim();
    const own = text(el) || [...el.querySelectorAll('img[alt], svg title')].map((n) => n.getAttribute('alt') || n.textContent).join(' ').trim();
    if (own && !/^(input|select|textarea)$/i.test(el.tagName)) return own;
    return (el.getAttribute('title') || '').trim();
  };
  const unnamed = [], placeholderOnly = [];
  controls.forEach((el) => {
    if (nameOf(el)) return;
    if (el.getAttribute('placeholder')) placeholderOnly.push({ selector: path(el), placeholder: el.getAttribute('placeholder') });
    else unnamed.push({ selector: path(el), tag: el.tagName.toLowerCase(), type: el.type || el.getAttribute('role') || '' });
  });
  out.controlsWithoutName_A11Y04 = sample(unnamed);
  out.placeholderAsOnlyLabel_FRM02 = sample(placeholderOnly);
  out.imagesWithoutAlt_A11Y04 = sample([...document.images].filter((i) => visible(i) && !i.hasAttribute('alt'))
    .map((i) => ({ selector: path(i), src: (i.currentSrc || i.src).split('/').pop() })));
  out.nonControlsWithClickHandler_A11Y03 = sample([...document.querySelectorAll('[onclick]')]
    .filter((el) => visible(el) && !el.matches('a[href], button, input, select, textarea, summary, [role], [tabindex]'))
    .map((el) => ({ selector: path(el), text: text(el) })));

  // A11Y-01 text contrast.
  const lowContrast = [];
  let checked = 0, unknownBg = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  });
  const seen = new Set();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!el || seen.has(el) || !visible(el)) continue;
    seen.add(el);
    const cs = getComputedStyle(el);
    const fg = parseRGB(cs.color);
    const bg = backgroundOf(el);
    if (!fg) continue;
    if (!bg) { unknownBg++; continue; }
    checked++;
    const ratio = contrast(over(fg, bg), bg);
    const px = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = px >= 24 || (bold && px >= 18.66);
    const need = large ? 3 : 4.5;
    const disabled = el.closest('[disabled], [aria-disabled=true]');
    if (ratio < need && !disabled) {
      lowContrast.push({ selector: path(el), text: text(el), ratio: +ratio.toFixed(2), need, fontPx: px, color: cs.color });
    }
  }
  lowContrast.sort((a, b) => a.ratio - b.ratio);
  out.lowContrastText_A11Y01 = { checked, skippedImageBackgrounds: unknownBg, ...sample(lowContrast) };

  // VIS-03 small text.
  const smallText = [...seen].filter((el) => parseFloat(getComputedStyle(el).fontSize) < 12)
    .map((el) => ({ selector: path(el), fontPx: parseFloat(getComputedStyle(el).fontSize), text: text(el) }));
  out.textUnder12px_VIS03 = sample(smallText);
  out.bodyFontPx = parseFloat(getComputedStyle(document.body).fontSize);

  // Document structure (A11Y-04, NAV-03).
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible);
  const skips = [];
  headings.reduce((prev, h) => { const lvl = +h.tagName[1]; if (prev && lvl > prev + 1) skips.push(`${'h' + prev} -> ${h.tagName.toLowerCase()} "${text(h)}"`); return lvl; }, 0);
  out.structure = {
    lang: document.documentElement.lang || null,
    title: document.title || null,
    h1Count: headings.filter((h) => h.tagName === 'H1').length,
    headingLevelSkips: skips.slice(0, MAX_EXAMPLES),
    landmarks: ['main', 'nav', 'header', 'footer'].filter((t) => document.querySelector(`${t}, [role=${{ main: 'main', nav: 'navigation', header: 'banner', footer: 'contentinfo' }[t]}]`)),
  };

  // A11Y-05 zoom and reflow.
  const vp = document.querySelector('meta[name=viewport]')?.content || '';
  out.zoomBlocked_A11Y05 = /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b/i.test(vp) ? vp : false;
  out.horizontalOverflowPx_A11Y05 = vw ? Math.max(0, document.documentElement.scrollWidth - vw) : null;
  out.reflowNote = vw > 400 ? 'Resize to 320 CSS px wide and run again to test WCAG 1.4.10 reflow.' : 'Measured at narrow width.';

  // A11Y-05 / A11Y-06 motion and media.
  let reducedMotionRule = false;
  for (const sheet of document.styleSheets) {
    try { if ([...sheet.cssRules].some((r) => r.cssText.includes('prefers-reduced-motion'))) reducedMotionRule = true; } catch (e) { /* cross-origin */ }
  }
  out.motion = {
    runningAnimations: document.getAnimations ? document.getAnimations().length : null,
    reducedMotionRuleFound: reducedMotionRule,
    autoplayWithSound_A11Y06: [...document.querySelectorAll('video[autoplay], audio[autoplay]')].filter((m) => !m.muted).map(path),
    videosWithoutCaptions_A11Y06: [...document.querySelectorAll('video')].filter((v) => !v.querySelector('track[kind=captions], track[kind=subtitles]')).map(path),
  };

  // INT-07 dialogs open on load; VIS-01 competing primary buttons.
  const overlays = [...document.querySelectorAll('dialog[open], [role=dialog], [aria-modal=true], body *')]
    .filter((el) => {
      if (!visible(el)) return false;
      if (el.matches('dialog[open], [role=dialog], [aria-modal=true]')) return true;
      const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      return cs.position === 'fixed' && r.width >= vw * 0.9 && r.height >= vh * 0.9;
    });
  out.dialogsOrOverlaysOpen_INT07 = sample(overlays.map((el) => ({ selector: path(el), text: text(el) })));
  const filled = controls.filter((el) => el.matches('button, [role=button], a, input[type=submit], .btn')).filter((el) => {
    const c = parseRGB(getComputedStyle(el).backgroundColor);
    return c && c[3] > 0.5 && Math.max(...c.slice(0, 3)) - Math.min(...c.slice(0, 3)) > 40; // saturated fill
  });
  const groups = new Map();
  filled.forEach((el) => {
    const box = el.closest('form, section, [role=dialog], dialog, main, body');
    const key = path(box) + ' | ' + getComputedStyle(el).backgroundColor;
    groups.set(key, [...(groups.get(key) || []), text(el)]);
  });
  out.samePrimaryStyleButtons_VIS01 = [...groups].filter(([, v]) => v.length >= 3).map(([k, v]) => ({ container: k, buttons: v }));

  // CON-05 / CON-03 vague links and generic buttons.
  out.vagueLinks_CON05 = sample([...document.querySelectorAll('a')].filter((a) => visible(a) &&
    /^(click here|here|read more|learn more|more|link)$/i.test(text(a))).map((a) => ({ selector: path(a), text: text(a) })));
  out.genericButtons_CON03 = sample(controls.filter((el) => /^(ok|okay|submit|yes|no|go)$/i.test(text(el)))
    .map((el) => ({ selector: path(el), text: text(el) })));

  // CHO-01 pre-checked consent.
  out.precheckedConsent_CHO01 = sample([...document.querySelectorAll('input[type=checkbox]:checked')].filter((c) => {
    const label = [...(c.labels || [])].map(text).join(' ') || text(c.parentElement || c);
    return /newsletter|marketing|offer|promo|subscribe|partner|third.?part|share/i.test(label);
  }).map((c) => ({ selector: path(c), label: [...(c.labels || [])].map(text).join(' ') })));

  // FBK-05 / FBK-06 timing and layout shift from the performance timeline.
  const buffered = (type) => new Promise((resolve) => {
    const list = [];
    try {
      const po = new PerformanceObserver((l) => list.push(...l.getEntries()));
      po.observe({ type, buffered: true });
      setTimeout(() => { po.disconnect(); resolve(list); }, 100);
    } catch (e) { resolve(null); }
  });
  const [lcp, shifts, longTasks] = await Promise.all([buffered('largest-contentful-paint'), buffered('layout-shift'), buffered('longtask')]);
  const nav = performance.getEntriesByType('navigation')[0];
  out.performance_FBK05 = {
    ttfbMs: nav ? Math.round(nav.responseStart) : null,
    domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
    loadMs: nav ? Math.round(nav.loadEventEnd) : null,
    lcpMs: lcp && lcp.length ? Math.round(lcp[lcp.length - 1].startTime) : null,
    clsSoFar: shifts ? +shifts.filter((s) => !s.hadRecentInput).reduce((a, s) => a + s.value, 0).toFixed(3) : null,
    longTasksOver50ms: longTasks ? longTasks.length : null,
    note: 'Lab numbers from one load. Judge Core Web Vitals on field data (CrUX or RUM, 75th percentile). ' +
      'INP needs real interactions; LCP is not recorded while the tab is hidden.',
  };
  out.imagesWithoutDimensions_FBK06 = sample([...document.images].filter((i) => visible(i) &&
    !(i.getAttribute('width') && i.getAttribute('height')) && !getComputedStyle(i).aspectRatio.includes('/'))
    .map((i) => path(i)));

  // A11Y-03 focus visibility (opt-in: it moves focus).
  if (FOCUS_CHECK) {
    const before = document.activeElement;
    const noIndicator = [];
    const keys = ['outlineStyle', 'outlineWidth', 'outlineColor', 'boxShadow', 'borderColor', 'backgroundColor', 'textDecorationLine'];
    controls.filter((el) => el.tabIndex >= 0).slice(0, 40).forEach((el) => {
      el.blur();
      const a = getComputedStyle(el); const blurred = keys.map((k) => a[k]);
      el.focus({ preventScroll: true });
      const b = getComputedStyle(el); const focused = keys.map((k) => b[k]);
      const outlineNone = b.outlineStyle === 'none' || parseFloat(b.outlineWidth) === 0;
      if (document.activeElement === el && outlineNone && focused.every((v, i) => v === blurred[i])) noIndicator.push(path(el));
    });
    if (before && before.focus) before.focus({ preventScroll: true });
    out.focusWithoutVisibleIndicator_A11Y03 = sample(noIndicator);
  } else {
    out.focusWithoutVisibleIndicator_A11Y03 = 'skipped: set FOCUS_CHECK = true, or tab through the page and watch the focus ring';
  }

  console.log('[ux-rules probe]', out);
  return out;
})();
