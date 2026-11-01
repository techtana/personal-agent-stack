# Platform conventions, mobile and touch (PLT)

How a UI fits its host: platform conventions (mobile and desktop, including menus, tray and window controls), thumb reach, touch and click target size, responsive layout, gestures, and unreliable networks and interruptions. Load this file when auditing a native app, a phone or tablet layout, a desktop app with a tray icon, or any control that people tap, drag or swipe. Target size is covered only here (PLT-03); accessibility rules point back to it.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| PLT-01 | Follow the platform's conventions | Moderate | native mobile and desktop apps, web apps in platform shells |
| PLT-02 | Put primary touch actions within thumb reach | Mixed | handheld touch UIs (phones, small tablets) |
| PLT-03 | Make touch and click targets big enough, with spacing | Strong | any pointer or touch UI |
| PLT-04 | Design responsive, mobile-first layouts | Moderate | websites and web apps used on more than one screen size |
| PLT-05 | Give every gesture a visible alternative | Strong | swipe, pinch, drag, long-press and other gestures |
| PLT-06 | Design for interruptions and poor networks | Weak | web and mobile apps with network calls, forms, long tasks |

---

### PLT-01 Follow the platform's conventions

**What it is.** Use the host platform's standard controls and patterns for navigation, Back, dialogs, menus, window chrome, shortcuts, type and system surfaces (tray or menu bar, notifications). Deviate only with test evidence. Reference sets: Apple HIG, Google Material and Android, Microsoft Windows app design and Fluent, GNOME HIG.

**Why it works.**
- People bring expectations from the apps they use all day. Nielsen's heuristic 4 tells designers to follow platform and industry conventions, and links it to Jakob's law (PER) [1].
- The guidelines converge on concrete behavior. Android: Up never exits the app, Back pops screens in reverse order, a deep link builds a realistic back stack [2]. Apple: avoid custom window frames and controls, since imperfect imitations make an app feel broken [3]; keep the macOS menu order (App, File, Edit, View, custom menus, Window, Help) and the standard shortcuts [4]. Windows: a 32 px title bar, system caption buttons, drag on empty title-bar space, double-click to maximize or restore [5].
- Some conventions differ by platform, so copying one is wrong on another. Apple puts the default alert button on the trailing side and Cancel on the leading side [6]; Windows recommends OK, Accept and Yes to the left of Cancel, No and Reject [7].
- Tray rules matter for desktop apps. Microsoft's guide (written for Windows 7, not updated, "much of the guidance still applies"): use the notification area only for notifications and status, not for launching; one icon per component; a left click must show something; right click opens a context menu with the default command in bold; offer "Display icon in notification area" and Exit; act on mouse-up; most icons are hidden by default and only the user can promote them [8].
- Apple: people decide whether a menu-bar extra appears, and the system may hide it, so do not rely on its position [4]. GNOME's HIG pages we checked contain no tray-icon pattern, and its notification page says the app window should show everything a notification says [9].

**Evidence: Moderate.** Consensus across the major platform guidelines; we found no controlled study of native versus custom controls. The Windows notification-area guide is dated and says so [8].

**Limitations.**
- Platforms disagree (button order, menu placement, tray support), so a cross-platform app must adapt per platform or accept one platform's convention.
- Guidelines change with releases, and a convention can be wrong for your task; check the current version and deviate only when testing shows it, keeping the deviation consistent (INT-03).
- Brand styling is cheap (color, type, icons); behavior changes (Back, window controls, dialogs) cost the most familiarity.
- A tray or menu-bar icon can be hidden by the user or the system, and GNOME has none, so never make it the only route to a function [4][8][9].

**How to measure.**
- Usability test with experienced users of each platform (first-time success on navigation, Back, quitting and reopening; error counts), plus a heuristic review against that platform's own checklist (menus, shortcuts, window controls, dark mode, text scaling).
- Support questions such as "where did it go" or "how do I quit"; store reviews that say the app does not feel native. Lagging: ratings.

**Implemented by.**
- Microsoft, Windows 7 (2009): hid most notification-area icons by default after the area grew noisy, leaving promotion to the user [8]. Apple, macOS: fixed menu-bar structure; menu-bar extras are optional and user-controlled [4].
- Google, Android Navigation component: back stack and Up semantics [2]. GNOME HIG: header bars with main actions at the start and the menu at the end [10]. No outcome numbers published for any of these.

**How to detect it.**
- *Applied:* tab bar or bottom navigation on phones, sidebar on desktop; system Back works; native dialogs and sheets; standard menu bar and shortcuts; system caption buttons; a tray icon with tooltip, left-click action and a right-click menu with Open and Quit; dark mode and text size honored.
- *Violated:* a custom window frame without minimize, maximize, close or snap; an in-content Back that exits unexpectedly; iOS-style tabs on Android with no reason (or the reverse); a tray icon with no menu or a left click that does nothing; an app reachable only through its tray icon; Ctrl and Cmd mixed up.
- *In code:* Electron `new BrowserWindow({ frame: false })`, `titleBarStyle`, `new Tray(`, `Menu.setApplicationMenu(null)`; Qt `QSystemTrayIcon`; Python `pystray.Icon(` with no `menu` or default item; .NET `NotifyIcon` without `ContextMenuStrip`; web `appearance: none` on native controls, `history.pushState` hijacks; Android `onBackPressed` overrides; iOS `interactivePopGestureRecognizer.isEnabled = false`.
- *Quick test:* on each target platform press Back or Esc, use the standard shortcuts (close, quit, preferences), resize and snap the window, right-click the tray icon, hide the tray icon and still find the app, then try dark mode and 200% text.

**How to implement.**
1. List the target platforms, read each current guideline set, and build with the native or official component library (SwiftUI/UIKit, Jetpack Compose with Material 3, WinUI with Fluent, GTK4 with libadwaita, Qt styles).
2. Use the system navigation model and Back; override only for a tested reason.
3. Use native alerts, sheets and menus; set dialog button order per platform (Apple: default trailing; Windows: OK left of Cancel).
4. On desktop, provide the standard menus and shortcuts and keep the system title bar; if custom, match the caption buttons, drag regions and double-click behavior [5].
5. For a tray or menu-bar icon: limit it to status and notifications; left click opens the main window or a status flyout; right click opens a menu with Open, a start-at-login toggle, Display icon and Quit; add a tooltip; keep another way to open the app (Start menu, Dock, window).
6. In cross-platform frameworks, branch by platform for button order, shortcut modifiers and Back.
7. Test on each platform with its accessibility settings on.

**Sources.**
[1] Nielsen, J. (1994; reviewed Jan 30, 2024). 10 Usability Heuristics for User Interface Design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Google. Principles of navigation. Android Developers. https://developer.android.com/guide/navigation/principles
[3] Apple. Human Interface Guidelines, Windows. https://developer.apple.com/design/human-interface-guidelines/windows
[4] Apple. Human Interface Guidelines, The menu bar. https://developer.apple.com/design/human-interface-guidelines/the-menu-bar
[5] Microsoft. Windows app title bar. https://learn.microsoft.com/en-us/windows/apps/design/basics/titlebar-design
[6] Apple. Human Interface Guidelines, Alerts. https://developer.apple.com/design/human-interface-guidelines/alerts
[7] Microsoft. Command bar (Windows apps), placement of Accept and Cancel commands. https://learn.microsoft.com/en-us/windows/apps/design/controls/command-bar
[8] Microsoft. Notification Area, Windows UX guidelines (Win32). https://learn.microsoft.com/en-us/windows/win32/uxguide/winenv-notification
[9] GNOME. Human Interface Guidelines, Notifications (https://developer.gnome.org/hig/patterns/feedback/notifications.html); guideline index checked for a tray pattern (https://developer.gnome.org/hig/guidelines.html)
[10] GNOME. Human Interface Guidelines, Header bars. https://developer.gnome.org/hig/patterns/containers/header-bars.html

---

### PLT-02 Put primary touch actions within thumb reach

**What it is.** On handheld screens, place the controls used most (primary action, main navigation, frequent tools) in the lower and central area the holding hand reaches without a stretch, and put rare or risky controls where they are hard to hit by accident.

**Why it works.**
- Hoober's field observation (UXmatters, Feb 18, 2013): 1,333 people observed in public places over two months ending Jan 8, 2013. Of the 780 touching the screen, 49% used one hand, 36% cradled the phone and touched with the other hand, 15% used two hands; 72% of cradlers touched with a thumb [1].
- Thumb reach is anatomical. Bergstrom-Lehtovirta and Oulasvirta (CHI 2014) fit a model of the thumb's functional area from 20 participants' thumb motions; it depends on screen size, hand size and index-finger position [2].
- Touch accuracy varies with place. Henze et al. (MobileHCI 2011) logged 120,626,225 touches from 91,731 game installs and found touch positions systematically skewed; a compensation function cut the error rate by 7.79% in a 12,201-install follow-up [3].
- Industry moved controls down. Apple placed Safari's tab bar at the bottom in iOS 15 (announced June 7, 2021) so controls are easier to reach with one hand [4]. Microsoft advises bottom command bars on small handheld devices and top bars on larger screens [5]. Material's navigation bar sits at the bottom with three to five destinations [6].

**Evidence: Mixed.** Grip observations and a reach model support lower placement, but the popular "thumb zone" chart is disputed by the researcher who counted the grips, and we found no published A/B test of bottom versus top navigation.

**Limitations.**
- Hoober (2017) calls the common thumb-zone chart outdated and misleading: it assumes a small phone, a thumb and bottom-only tapping, while people shift grip, cradle the phone and use fingers; accuracy is best at screen center and worse at edges and corners [7].
- 49% one-handed means over half use another grip; tablets and large phones are mostly two-handed.
- Bottom-edge targets collide with system gesture areas (home indicator, back swipe); keep safe-area padding.
- Easy reach raises the risk of accidental taps. Microsoft says targets with severe consequences need more padding and distance from edges [8]; do not put destructive actions in the easiest spot (ERR).
- Left- and right-hand reach differ; do not design for right-handed users only.

**How to measure.**
- One-handed lab task on a 6-inch-class phone: completion time and misses for the primary action in top versus bottom positions; expect fewer misses at lower, central positions.
- Touch heatmaps and mis-tap rate (taps followed by an immediate back or undo) by screen region.
- Lagging: primary-action conversion and task completion on mobile.

**Implemented by.**
- Apple, Safari in iOS 15 (2021): bottom tab bar for one-handed use; no outcome published [4].
- Microsoft, WinUI guidance: bottom command bars on small handhelds [5].
- Google, Material navigation bar at the bottom [6]. Many social apps use bottom tab bars (observed; no outcome published).

**How to detect it.**
- *Applied:* bottom tab bar or sticky bottom action bar; primary call to action in the lower half; bottom sheets for secondary choices; titles and rare actions at the top.
- *Violated:* primary action in the top-right on a tall phone; close or back only in the top-left of a full-screen modal; frequent tools in the top corners; tiny targets in screen corners.
- *In code:* `position: sticky; bottom: 0`, `env(safe-area-inset-bottom)`; `BottomNavigationView`, `NavigationBar`, `ModalBottomSheet`; `UITabBar`, `ToolbarItemGroup(placement: .bottomBar)`; primary buttons at `top: 0; right: 0`.
- *Quick test:* hold a large phone in one hand and tap the primary action and the main navigation with your thumb; list everything you cannot reach without shifting your grip.

**How to implement.**
1. Rank actions by frequency and put the top few in the lower half and center.
2. On phones, use a bottom tab bar or navigation bar for three to five top-level destinations; use a sidebar or top bar on tablets and desktop.
3. Use a sticky bottom action bar for the main task action and bottom sheets for secondary choices.
4. Keep top corners for rare or low-risk controls; offer swipe-back or edge gestures only as a supplement (PLT-05).
5. Pad the bottom for the home indicator and keep destructive actions away from the easiest spot.
6. Check with left- and right-hand grips and on a small and a large phone.

**Sources.**
[1] Hoober, S. (2013). How Do Users Really Hold Mobile Devices? UXmatters, Feb 18, 2013. https://www.uxmatters.com/mt/archives/2013/02/how-do-users-really-hold-mobile-devices.php
[2] Bergstrom-Lehtovirta, J., Oulasvirta, A. (2014). Modeling the functional area of the thumb on mobile touchscreen surfaces. CHI 2014, pp. 1991-2000. https://doi.org/10.1145/2556288.2557354
[3] Henze, N., Rukzio, E., Boll, S. (2011). 100,000,000 taps: analysis and improvement of touch performance in the large. MobileHCI 2011, pp. 133-142. https://doi.org/10.1145/2037373.2037395
[4] Apple (2021). iOS 15 brings powerful new features to stay connected, focus, explore, and more. Apple Newsroom, June 7, 2021. https://www.apple.com/newsroom/2021/06/ios-15-brings-powerful-new-features-to-stay-connected-focus-explore-and-more/
[5] Microsoft. Command bar (Windows apps), placement. https://learn.microsoft.com/en-us/windows/apps/design/controls/command-bar
[6] Material Components for Android. Navigation bar (BottomNavigation) documentation. https://raw.githubusercontent.com/material-components/material-components-android/master/docs/components/BottomNavigation.md
[7] Hoober, S. (2017). Design for Fingers, Touch, and People, Part 1. UXmatters, Mar 6, 2017. https://www.uxmatters.com/mt/archives/2017/03/design-for-fingers-touch-and-people-part-1.php
[8] Microsoft. Targeting, Windows apps. https://learn.microsoft.com/en-us/windows/apps/design/input/guidelines-for-targeting

---

### PLT-03 Make touch and click targets big enough, with spacing

**What it is.** Every control that takes a tap or click needs a hit area large enough to hit reliably and enough space from its neighbors. Common floors: 24 CSS px (WCAG AA), 44 pt (Apple default), 48 dp (Android and Material), about 7.5 mm (Microsoft). The hit area may be larger than the visible icon.

**Why it works.**
- Fingers are imprecise and cover what they touch, so errors rise as targets shrink and crowd together; Fitts's law (PER) covers pointer speed. Parhi, Karlson and Bederson (MobileHCI 2006) studied one-handed thumb use: speed improved as targets grew, and they recommend 9.2 mm for discrete tasks (buttons, checkboxes) and 9.6 mm for serial tasks (typing). The participant count was not in the abstract we read [1].
- Henze et al. (2011), 120.6 million touches: error rates depend on target size and screen position, and touches are skewed [2]. Hoober (2017) sizes targets to catch about 95% of observed taps: roughly 7 mm at screen center and 12 mm in corners [3].
- The standards set floors. WCAG 2.2 SC 2.5.8 needs at least 24×24 CSS px unless an exception applies [4]; SC 2.5.5 (AAA) asks for 44×44 [5]. Apple lists a 44×44 pt default and 28×28 pt minimum on iOS, with about 12 pt padding around bezeled controls and 24 pt around bezel-less ones [6]. Google says at least 48×48 dp [7]. Microsoft says about 7.5 mm, or 40×40 px at 135 PPI and 1.0x scale [8].

**Evidence: Strong.** Peer-reviewed touch studies (2006, 2011), a formal standard and four platform guidelines agree on the order of magnitude.
Required: WCAG 2.2 SC 2.5.8 Target Size (Minimum) (AA); SC 2.5.5 (AAA) is optional.

**Limitations.**
- SC 2.5.8 has five exceptions: spacing (a 24 px circle centered on each undersized target must not touch another target or circle), an equivalent control elsewhere, inline text links, user-agent-sized controls, and essential presentation [4].
- Units are not physical (CSS px, pt and dp scale with the device; Hoober argues for millimeters [3]) and the numbers differ by source (24, 44, 48; about 7 to 12 mm). Apple's iOS minimum is 28 pt and 44 pt is its default, so "44 pt minimum" is a common overstatement [6]. Treat 44 to 48 as the comfortable size for primary touch controls.
- Big targets cost density. Pointer-only desktop UIs can be smaller (macOS default 28 pt, minimum 20 pt [6]); offer a compact mode there and keep touch sizes on touch devices.
- Fingertip widths attributed to an "MIT Touch Lab" paper (Dandekar et al. 2003) are widely repeated, but the abstract lists no dimensions and we could not open the full text, so we did not use them [9].
- WCAG 2.1 AA has no minimum-size criterion (its 2.5.5 is AAA; not re-checked in this pass), so policies that cite only 2.1 do not require 2.5.8.

**How to measure.**
- Mis-tap rate: taps that land on a neighbor and are followed within a second or two by back or undo; rage taps; expect lower.
- Lab: error rate and time on a tap-heavy task at current versus enlarged sizes, one-handed and while walking.
- Automated: Lighthouse's tap-target audit treats 48×48 CSS px as always passing (page last updated 2019) [10]. Lagging: mobile task completion.

**Implemented by.**
- Apple (HIG), Google (Android docs) and Microsoft (WinUI) publish the floors above [6][7][8]; W3C added SC 2.5.8 at AA in WCAG 2.2 (2023) [4].
- No company published a before-and-after for enlarged targets in the sources checked; Henze's 7.79% error reduction came from an offset-compensation function, not larger targets [2].

**How to detect it.**
- *Applied:* icon buttons padded to 44 to 48 px; list rows tappable across the full width; at least 8 px between adjacent targets; larger targets near edges and corners; labels that wrap checkboxes and radios.
- *Violated:* 16 to 24 px icon buttons with no padding; a close "×" in a 12 px box; stacked links 4 px apart; native-size checkboxes; adjacent small buttons; tiny pagination dots.
- *In code:* `min-width` and `min-height` of 44px or 48px, `padding` on icon buttons, `::after { inset: -8px }` hit-area expansion, `<label for>`; `width: 20px; height: 20px` on a `button`; Android `minimumWidth`/`minimumHeight` 48dp, `Modifier.minimumInteractiveComponentSize()`; SwiftUI `.frame(minWidth: 44, minHeight: 44)` with `.contentShape(Rectangle())`.
- *Quick test:* run Lighthouse or an accessibility checker with a target-size rule; then tap every pair of neighboring controls with a thumb on a real phone.

**How to implement.**
1. Set a token such as `--target-min: 44px` (48px for Android) and apply it as `min-width` and `min-height` on buttons, toolbar links and form controls.
2. For small visuals, enlarge the hit area with padding or a pseudo-element, not the icon.
3. Keep at least 8 px between adjacent targets (Apple: about 12 pt with a bezel, 24 pt without); add more for destructive actions and near edges.
4. Make whole rows and labels tappable, and use larger targets in corners and along screen edges.
5. Offer compact density only for pointer-only layouts; do not shrink touch UIs.
6. Test one-handed on a real phone.

**Sources.**
[1] Parhi, P., Karlson, A. K., Bederson, B. B. (2006). Target size study for one-handed thumb use on small touchscreen devices. MobileHCI 2006, pp. 203-210. https://doi.org/10.1145/1152215.1152260 (abstract read via OpenAlex; publisher page returned 403)
[2] Henze, N., Rukzio, E., Boll, S. (2011). 100,000,000 taps: analysis and improvement of touch performance in the large. MobileHCI 2011, pp. 133-142. https://doi.org/10.1145/2037373.2037395
[3] Hoober, S. (2017). Design for Fingers, Touch, and People, Part 1. UXmatters, Mar 6, 2017. https://www.uxmatters.com/mt/archives/2017/03/design-for-fingers-touch-and-people-part-1.php
[4] W3C. Understanding SC 2.5.8 Target Size (Minimum). https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
[5] W3C. Understanding SC 2.5.5 Target Size (Enhanced). https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html
[6] Apple. Human Interface Guidelines, Accessibility (control sizes and spacing). https://developer.apple.com/design/human-interface-guidelines/accessibility
[7] Google. Make apps more accessible. Android Developers. https://developer.android.com/guide/topics/ui/accessibility/apps
[8] Microsoft. Targeting, Windows apps. https://learn.microsoft.com/en-us/windows/apps/design/input/guidelines-for-targeting
[9] Dandekar, K., Raju, B. I., Srinivasan, M. A. (2003). 3-D finite-element models of human and monkey fingertips to investigate the mechanics of tactile sense. Journal of Biomechanical Engineering 125(5):682-691. https://doi.org/10.1115/1.1613673 (abstract only, no fingertip dimensions)
[10] Google. Lighthouse tap targets audit (page last updated 2019-05-02). https://developer.chrome.com/docs/lighthouse/seo/tap-targets

---

### PLT-04 Design responsive, mobile-first layouts

**What it is.** Build layouts that adapt from a 320 CSS px phone width up to desktop. Start from the smallest screen's content and priorities, add layout as space grows (`min-width` queries), and never require horizontal scrolling or drop functions on small screens.

**Why it works.**
- Wroblewski (post of Nov 3, 2009; book "Mobile First," A Book Apart, 2011) gave three reasons: mobile growth, small-screen constraints that force prioritization, and device capabilities such as location and touch [1]. His 2009 growth figures are dated.
- Audience: Statcounter, September 2026, worldwide page views: mobile 59.06%, desktop 39.2%, tablet 1.75% [2]. This is a share of page views, not of revenue or time.
- Search: Google predominantly uses the mobile version of content for indexing and ranking and expects equivalent primary content on mobile [3]. Its October 2023 post "Mobile-first indexing has landed" marks the end of the rollout (title seen in the blog archive; body not read) [4].
- Standards: WCAG 2.2 SC 1.4.10 Reflow (AA): content must work at 320 CSS px wide without two-dimensional scrolling, equal to 400% zoom on a 1280 px window; maps, data tables and similar content that needs two dimensions are exempt [5]. SC 1.3.4 Orientation (AA): do not lock the display to one orientation unless essential [6].

**Evidence: Moderate.** Reflow and orientation are formal standards; the claim that designing small-first yields better products rests on practitioner argument and traffic shifts, not a controlled comparison.
Required: WCAG 2.2 SC 1.4.10 Reflow (AA) and SC 1.3.4 Orientation (AA).

**Limitations.**
- Traffic share varies by audience; internal or data-dense tools can be desktop-heavy, and a page-view share is not a conversion share.
- Mobile-first is a build order, not mobile-only; complex desktop workflows still need desktop layouts.
- Hiding content on mobile can cost it in search, because Google indexes the mobile version [3].
- Wide tables, maps and editors need their own scroll containers or the reflow exception, not a broken page.
- Breakpoints tied to device models age badly; break where the content breaks.

**How to measure.**
- At 320×568 and at 400% zoom on a 1280 px window: no horizontal page scroll, no clipped controls, every function reachable.
- Field: mobile versus desktop conversion and task-completion parity; mobile bounce; Core Web Vitals on mobile (FBK).
- Search Console: indexed pages and mobile content parity.

**Implemented by.**
- Google (rollout completed October 2023 per the post title): Search indexes and ranks from the mobile version of pages [3][4].
- Twitter Lite (2017): a mobile web app (PWA); figures under PLT-06.
- No other company outcomes verified; Wroblewski's argument is widely adopted but anecdotal.

**How to detect it.**
- *Applied:* a viewport meta tag; base CSS for narrow screens with `@media (min-width: …)` additions; fluid grids; images with `max-width: 100%`; navigation that collapses; no horizontal scroll at 320 px; text that reflows at 400% zoom.
- *Violated:* fixed widths such as `width: 960px`; containers with `min-width` above 320; horizontal page scroll; `user-scalable=no` or `maximum-scale=1`; locked orientation; only `max-width` (desktop-first) queries; content or functions missing on mobile.
- *In code:* `<meta name="viewport" content="width=device-width, initial-scale=1">`; count of `@media (min-width` versus `@media (max-width`; `grid-template-columns: repeat(auto-fit, minmax(`; `clamp(`; `@container`; `screen.orientation.lock`; Android `android:screenOrientation="portrait"`; iOS `supportedInterfaceOrientations`.
- *Quick test:* set DevTools to 320 px wide, zoom the browser to 400% at 1280 px, and rotate; look for horizontal scrollbars and overlapping elements.

**How to implement.**
1. Add the viewport meta tag and do not disable zoom.
2. List content and actions by priority and design the single-column layout first.
3. Write base CSS for narrow screens, then add `min-width` queries where the content needs them.
4. Use fluid layout (grid or flex with `minmax`, `clamp()`, relative units) and responsive images (`srcset`, `sizes`).
5. Let wide content (tables, code) scroll inside its own container; keep the page free of horizontal scroll.
6. Keep content and functions identical across sizes and support both orientations.
7. Test at 320 px, at 400% zoom and on real devices.

**Sources.**
[1] Wroblewski, L. (2009). Mobile First. LukeW, Nov 3, 2009. https://www.lukew.com/ff/entry.asp?933 (book: Wroblewski, L. (2011). Mobile First. A Book Apart; not opened)
[2] Statcounter Global Stats. Desktop vs mobile vs tablet market share worldwide, September 2026. https://gs.statcounter.com/platform-market-share/desktop-mobile-tablet/worldwide
[3] Google. Mobile-first indexing, Search Central documentation (exact page title not recorded). https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing (the page gives no completion date; a July 2024 cut-off for sites unreachable by mobile Googlebot is widely reported but not verified here)
[4] Google. "Mobile-first indexing has landed - thanks for all your support." Google Search Central Blog, Oct 2023 (title and month seen in the blog archive listing). https://developers.google.com/search/blog/2023/10/mobile-first-is-here (the URL we opened returned the archive listing, not the post body, which we did not read)
[5] W3C. Understanding SC 1.4.10 Reflow. https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
[6] W3C. Understanding SC 1.3.4 Orientation. https://www.w3.org/WAI/WCAG22/Understanding/orientation.html

---

### PLT-05 Give every gesture a visible alternative

**What it is.** Any action reachable only by swipe, pinch, long-press, drag or another gesture must also be reachable by a visible control (button, menu item, typed input) that works with a single tap or click. Gestures stay as shortcuts.

**Why it works.**
- Hidden gestures are hard to discover and remember. Norman and Nielsen (interactions, Sept 2010) argued that many gesture-driven interfaces lacked visible cues, feedback and consistency (record verified; text not opened) [1]. Apple says a custom gesture must be discoverable and never the only way to do an important action, and warns that a gesture you cannot describe in simple words and graphics will be hard to learn [2].
- Not everyone can perform a gesture. People use voice, keyboard or Switch Control, and some cannot make multi-finger or path gestures; Apple tells designers not to assume a specific gesture will work [2].
- WCAG 2.2 SC 2.5.1 Pointer Gestures (A): functionality that uses multipoint or path-based gestures must work with a single pointer without a path-based gesture, unless the gesture is essential. Examples: a map with pinch-zoom also has plus and minus buttons; a swipe carousel also has arrow buttons [3].
- WCAG 2.2 SC 2.5.7 Dragging Movements (AA): anything that relies on dragging must work with a single pointer without dragging. Examples: a slider whose track can be clicked, Kanban cards moved by tap plus arrow buttons or a menu [4].

**Evidence: Strong.** Two formal standards (2.5.1 is Level A) and consistent platform guidance; the discoverability argument is practitioner-based (2010).
Required: WCAG 2.2 SC 2.5.1 (A) and SC 2.5.7 (AA).

**Limitations.**
- Both criteria exempt essential gestures (signing, freehand drawing) and gestures supplied by the browser, OS or assistive technology, such as browser back-swipe and pull to refresh [3][4].
- A keyboard alternative alone does not satisfy them; a single-pointer alternative is required [3][4].
- Extra controls add clutter; use a menu, a long-press menu, edit mode or a "More" button where space is tight, but keep them findable (VIS).
- Gestures are good accelerators when a visible path exists (INT-05); do not remove them.
- Custom gestures must not collide with system gestures such as edge swipes [2].

**How to measure.**
- Discoverability test: share of new users who find and complete the action unaided, with and without the visible alternative.
- Log input source (gesture versus button) as an event property; accidental activation shows as undo right after a swipe action.
- Accessibility check: complete the task with VoiceOver or TalkBack, Switch Control and voice control.

**Implemented by.**
- Apple, HIG: shortcut gestures supplement standard navigation; keep a visible Back button even with swipe-from-edge [2].
- W3C's own examples: map zoom buttons, carousel arrows, slider track click, Kanban move buttons [3][4].
- Gmail and iOS Mail list swipes (archive, delete) have matching buttons or menu items in the open message or edit mode (observed behavior; not checked against documentation).

**How to detect it.**
- *Applied:* each swipe action has a button or menu equivalent; drag-and-drop has "Move to…" or up and down buttons; zoom has plus and minus; pull-to-refresh has a Refresh control; first-use hints for gestures.
- *Violated:* swipe-only delete or archive; drag-only reorder; pinch-only zoom on a map; long-press-only menus; two-finger or shake gestures as the only path.
- *In code:* `touchstart`/`touchmove`/`pointermove` handlers, `react-swipeable`, `Hammer`, `useDrag`, `draggable="true"` with no sibling button; iOS `UISwipeGestureRecognizer`, `UIPanGestureRecognizer`, `swipeActions`; Android `SwipeToDismiss`, `detectDragGestures`, `ItemTouchHelper`; check for a matching `<button>` or `<input type="range">`.
- *Quick test:* list every gesture in the app and ask what the single-tap way to do the same thing is; try the task with VoiceOver or TalkBack on.

**How to implement.**
1. Inventory gestures (swipe, drag, pinch, long-press, multi-finger).
2. For each, add a visible control that does the same thing with one tap or click (button, menu item, typed value).
3. For drag-and-drop: add "Move to…" or up and down buttons; for sliders: allow a track click and typed input; for maps and images: zoom buttons.
4. For swipe actions on rows: add a "More" or context menu and an edit mode.
5. Teach gestures with a hint or a peek on first use (ONB); keep them as accelerators.
6. Do not override system gestures.
7. Test with a screen reader, Switch Control and voice control.

**Sources.**
[1] Norman, D. A., Nielsen, J. (2010). Gestural interfaces: a step backward in usability. interactions 17(5):46-49. https://doi.org/10.1145/1836216.1836228 (bibliographic record verified via OpenAlex; article text not opened)
[2] Apple. Human Interface Guidelines, Gestures. https://developer.apple.com/design/human-interface-guidelines/gestures
[3] W3C. Understanding SC 2.5.1 Pointer Gestures. https://www.w3.org/WAI/WCAG22/Understanding/pointer-gestures.html
[4] W3C. Understanding SC 2.5.7 Dragging Movements. https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html

---

### PLT-06 Design for interruptions and poor networks

**What it is.** Assume connections drop, slow down or stop, and that people get interrupted (app switch, call, lock screen, session timeout). Keep what they entered, show honest status, retry safely, and keep the core usable from cache.

**Why it works.**
- Twitter Lite (2017), a progressive web app, per Google's case study: 65% more pages per session, 75% more Tweets sent, 20% lower bounce rate; first loads under 5 seconds on 3G on most devices and repeat loads under 3; about 600 KB over the wire versus 23.5 MB for the Android app; image optimization cut data use by up to 70%. Offline support was added in steps (offline page, static cache, app shell) and a data-saver mode lets users control media downloads. The page does not state the comparison baseline [1].
- Offline patterns are documented: cache then network, network falling back to cache, and an outbox for failed sends with background sync (Archibald, last updated Dec 9, 2014) [2].
- Google Docs lets people create and edit files offline (Chrome or Edge with the extension) and shows status: a cloud icon in the file and a check mark in Drive for offline-ready files [3].
- Saved state is partly a standards matter. WCAG 2.2 SC 3.3.7 Redundant Entry (A): do not make people retype information from earlier in the same process [4]. SC 2.2.5 Re-authenticating (AAA): after a session expires, people can continue without losing data [5].
- Facebook's "2G Tuesdays" (2015) reportedly gave employees a slow connection one day a week so they would feel it; we could not retrieve a primary source, so treat the details as unverified.

**Evidence: Weak.** Company-reported before-and-after figures with no stated comparison method, plus documentation of patterns; no controlled studies found. The principle is uncontroversial and partly required.
Required in part: WCAG 2.2 SC 3.3.7 Redundant Entry (A); SC 2.2.5 (AAA) is optional.

**Limitations.**
- Twitter Lite's gains came with a rewrite for speed and size; the share due to offline behavior is unknown, so the numbers are not causal evidence for this rule.
- Offline-first adds work: conflict resolution, cache invalidation and stale data; show data age.
- Queued is not sent: never say "sent" for a queued write; show the pending state.
- Retries can duplicate actions (double charge) without idempotency keys.
- Cached or drafted personal data on a device is a privacy risk; clear it on logout.
- Not every product needs full offline use, but every product needs graceful failure.

**How to measure.**
- Lab: DevTools Offline and Slow 3G; kill the connection mid-submit; background the app for five minutes mid-form. Pass means no data loss, honest status and recovery without retyping.
- Field: error and completion rates by connection quality (Network Information API where available), retry success rate, queued-send delivery rate, draft-recovery rate.
- Lagging: pages per session and bounce in low-bandwidth segments (the metrics Twitter Lite reported [1]).

**Implemented by.**
- Twitter, Twitter Lite (2017): service-worker caching, offline page, data-saver mode; figures above [1].
- Google, Docs offline: edit without a connection with visible offline status [3].
- Facebook, 2G Tuesdays (2015): unverified, see above.

**How to detect it.**
- *Applied:* an offline banner or status line; cached content shown offline with its age; queued sends with retry; autosaved drafts; scroll and input restored after reload; timeouts with a Retry button; idempotent submits.
- *Violated:* a blank white screen offline; an endless spinner; "Something went wrong" with no retry; a form wiped by timeout or refresh; a double charge on retry; login expiry that discards input.
- *In code:* `navigator.onLine`, `addEventListener('offline'`, `navigator.serviceWorker.register`, `caches.open`, Workbox, `indexedDB.open`, draft writes to `localStorage`, `fetch` with `AbortController` and backoff, an `Idempotency-Key` header, `visibilitychange` or `pagehide` save handlers; iOS `NWPathMonitor`, `waitsForConnectivity`, `scenePhase`; Android `ConnectivityManager.NetworkCallback`, `WorkManager`, `onSaveInstanceState`.
- *Quick test:* DevTools Network set to Offline, then reload; fill a form, go offline and submit; lock the phone for five minutes and come back.

**How to implement.**
1. Register a service worker, precache the app shell and add an offline page.
2. Use cache then network for reads, and show a "last updated" time.
3. Queue writes in an outbox (IndexedDB) and sync later; label them "Saved on this device, will send when online".
4. Autosave drafts on input and on `pagehide` or `visibilitychange`; restore them on return.
5. Retry with backoff and jitter, idempotency keys, timeouts and a manual Retry button.
6. Offer a data-saver mode and set a size budget (Twitter Lite shipped about 600 KB).
7. Do not let session timeouts discard input; re-authenticate in place.
8. Test under throttled and offline conditions before release.

**Sources.**
[1] Google (2017). Twitter Lite progressive web app case study. web.dev (page title not recorded; figures dated 2017 on the page). https://web.dev/case-studies/twitter
[2] Archibald, J. The Offline Cookbook. web.dev (last updated 2014-12-09). https://web.dev/articles/offline-cookbook
[3] Google. Working offline in Google Docs, Sheets and Slides (Docs Editors Help page; exact title not recorded). https://support.google.com/docs/answer/6388102
[4] W3C. Understanding SC 3.3.7 Redundant Entry. https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html
[5] W3C. Understanding SC 2.2.5 Re-authenticating. https://www.w3.org/WAI/WCAG22/Understanding/re-authenticating.html
