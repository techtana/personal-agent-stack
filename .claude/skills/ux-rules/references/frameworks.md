# Frameworks mapped to the catalog

Teams rarely review against single rules. They use a few well-known frameworks as lenses: Nielsen's heuristics in a
design review, WCAG in an accessibility audit, HEART when they pick metrics. This file maps each framework item to
the catalog's rule IDs, so a review can be phrased in whatever language the team already uses, and so a framework
item with no strong rule behind it is easy to spot.

## Nielsen's 10 usability heuristics

Jakob Nielsen, 1994 (from Nielsen and Molich 1990); wording refreshed by NN/g in 2020.
https://www.nngroup.com/articles/ten-usability-heuristics/

| # | Heuristic | Catalog rules |
|---|---|---|
| 1 | Visibility of system status | FBK-01, FBK-02, FBK-07, NAV-03 |
| 2 | Match between the system and the real world | CON-02, PER-11, INT-04 |
| 3 | User control and freedom | ERR-02, ERR-06, NAV-07 |
| 4 | Consistency and standards | INT-03, PER-06, PLT-01, NAV-04, CON-06 |
| 5 | Error prevention | ERR-01, ERR-03, FRM-04, FRM-05, FRM-06 |
| 6 | Recognition rather than recall | PER-04, PER-03, INT-02 |
| 7 | Flexibility and efficiency of use | INT-05, INT-06, FRM-11 |
| 8 | Aesthetic and minimalist design | VIS-01, VIS-04, CON-01, PER-07 |
| 9 | Help users recognize, diagnose and recover from errors | ERR-04, FRM-09 |
| 10 | Help and documentation | CON-07, ONB-03 |

Use for: a fast expert review (MEA-02). Not proof: heuristic reviews miss problems and report false ones, so
confirm severe findings with users (MEA-01).

## Norman's principles of interaction design

Don Norman, The Design of Everyday Things (1988; revised and expanded 2013).

| Principle | Catalog rules |
|---|---|
| Discoverability | INT-01, NAV-02, PLT-05 |
| Affordances and signifiers | INT-01, INT-02 |
| Mapping | INT-04 |
| Feedback | FBK-01, FBK-07 |
| Constraints | ERR-01 |
| Conceptual model | PER-11 |
| Slips versus mistakes (error types) | ERR-01, ERR-02, ERR-04 |

## Shneiderman's Eight Golden Rules of interface design

Ben Shneiderman, Designing the User Interface (1986; 6th edition 2016).
https://www.cs.umd.edu/users/ben/goldenrules.html

| # | Rule | Catalog rules |
|---|---|---|
| 1 | Strive for consistency | INT-03, CON-06, NAV-04 |
| 2 | Seek universal usability (novices to experts, diverse abilities) | A11Y-01 to A11Y-10, INT-05 |
| 3 | Offer informative feedback | FBK-01, FBK-02, FBK-07 |
| 4 | Design dialogs to yield closure | FBK-07, PER-09 |
| 5 | Prevent errors | ERR-01, FRM-04 |
| 6 | Permit easy reversal of actions | ERR-02 |
| 7 | Keep users in control | ERR-06, INT-07, AI-04 |
| 8 | Reduce short-term memory load | PER-03, PER-04 |

## ISO 9241-110:2020 interaction principles

The international standard's seven principles for dialogue between people and interactive systems.

| Principle | Catalog rules |
|---|---|
| Suitability for the user's tasks | PER-11, INT-06, FRM-01, VIS-04 |
| Self-descriptiveness | INT-01, CON-02, CON-07, NAV-03 |
| Conformity with user expectations | PER-06, PLT-01, INT-03 |
| Learnability | ONB-03, PER-04, INT-02 |
| Controllability | ERR-06, FBK-02, INT-07, AI-04 |
| Use error robustness | ERR-01 to ERR-05, FRM-06 |
| User engagement | PER-09, ONB-05, VIS-01 |

ISO 9241-11:2018 defines usability itself as effectiveness, efficiency and satisfaction in a specified context of
use; MEA-03 and MEA-04 measure those three.

## WCAG 2.2 (POUR)

W3C, Web Content Accessibility Guidelines 2.2 (Recommendation, October 2023). https://www.w3.org/TR/WCAG22/

| Principle | Catalog rules |
|---|---|
| Perceivable | A11Y-01, A11Y-02, A11Y-04, A11Y-05, A11Y-06, A11Y-10 |
| Operable | A11Y-03, PLT-03, PLT-05, A11Y-05 |
| Understandable | CON-02, FRM-02, FRM-09, ERR-04, NAV-04, A11Y-07 |
| Robust | A11Y-04 |

## Microsoft Guidelines for Human-AI Interaction (HAX)

Amershi et al., CHI 2019: 18 guidelines in four phases. The mapping is in `ai-and-automation.md`.

## "Laws of UX"

Jon Yablonski's collection (lawsofux.com, 2019 onward; book 2020) is the most quoted list in product teams. Its
entries vary a lot in evidence, so check the catalog's grade before leaning on one.

| Law | Catalog | Note |
|---|---|---|
| Aesthetic-usability effect | PER-07 | Mixed: raises perceived ease more reliably than measured performance |
| Doherty threshold (400 ms) | FBK-01 | Weakly sourced (the 1982 IBM report is hard to obtain); the 0.1 s / 1 s / 10 s limits are better supported |
| Fitts's law | PER-01, PLT-03 | Strong |
| Goal-gradient effect | PER-10, ONB-05 | Mixed: strong field studies, but constant progress bars did not cut survey drop-off in a 32-study meta-analysis |
| Hick's law | PER-02 | Mixed: holds for simple choices among known options; not a mandate for "fewer is better" |
| Jakob's law | PER-06 | Moderate |
| Laws of proximity, similarity, common region, uniform connectedness, Prägnanz | PER-05 | Strong (perception research) |
| Miller's law (7±2) | PER-03, MYTH-02 | Misapplied to menus; working memory holds about 4 chunks |
| Peak-end rule | PER-09 | Moderate: strong for pain and mood episodes, but the plain average predicted about as well in a 2022 meta-analysis; software use is an extrapolation |
| Postel's law | FRM-06 | Engineering principle applied to input |
| Serial position effect, von Restorff effect | PER-08 | Moderate: strong for memory; design use is an extrapolation |
| Tesler's law | INT-06 | Weak: a principle, not a measured law |
| Zeigarnik effect | MYTH-06 | Contested: replications are inconsistent |
| Choice overload | MYTH-05, PER-02 | Contested: the average effect across studies is near zero; it depends on context |
| Cognitive load, chunking, working memory | PER-03 | Strong |
| Mental model | PER-11 | Moderate |
| Parkinson's law, Pareto principle, Occam's razor | not in the catalog | Management heuristics, not UX evidence |
