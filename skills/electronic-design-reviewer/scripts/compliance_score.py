#!/usr/bin/env python3
"""compliance_score.py - weighted guide compliance, coverage and verdict gate.

1) Make an assessment skeleton for the review stage, then fill in each rule's status:
     compliance_score.py --rules ../references/guide-rosenberg-v5.md --stage schematic --template > assessment.json
2) Score it (markdown matrix to stdout, optional JSON):
     compliance_score.py --rules ../references/guide-rosenberg-v5.md --assessment assessment.json [--json out.json]

Assessment JSON:
  {"project": "...", "rev": "...", "stage": "schematic",
   "rules":    [{"id": "SCH-01", "status": "fail", "evidence": "[EDA] netlist_lint ...", "findings": ["F-03"]}],
   "findings": [{"id": "F-03", "severity": "S2", "status": "open", "title": "...", "rule": "SCH-01"}]}
Rule status: pass | partial | fail | na | unverified | waived
Finding status: open | fixed | waived | accepted-risk
Several --rules files may be given (user guide first = highest precedence).

Score    = sum(w * s) / sum(w) over pass(1) / partial(0.5) / fail(0) rules.
Coverage = (pass + partial + fail + waived) / (in-stage rules - na). Unassessed counts as unverified.
Verdict  = NOT READY (open S1) > READY AFTER FIXES (open S2) > INCOMPLETE (coverage < 80%) > READY.
"""
import argparse
import json
import re
import sys

STAGES = {
    'concept': ['framework'],
    'schematic': ['framework', 'schematic', 'components'],
    'placement': ['framework', 'schematic', 'components', 'mechanics', 'placement', 'library'],
    'layout': ['framework', 'schematic', 'components', 'mechanics', 'placement', 'library', 'layout'],
    'release': None,
}
STATUS_SCORE = {'pass': 1.0, 'partial': 0.5, 'fail': 0.0}
HEAD = re.compile(r'^#{2,4}\s+([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+[A-Za-z]?)\s+[—–-]\s+(.+?)\s*$')
META = re.compile(r'^`(.+)`\s*$')


def load_rules(paths):
    rules, order = {}, []
    for path in paths:
        lines = open(path, encoding='utf-8').read().splitlines()
        for i, line in enumerate(lines):
            m = HEAD.match(line)
            if not m:
                continue
            meta = {}
            for nxt in lines[i + 1:i + 4]:
                mm = META.match(nxt.strip())
                if mm:
                    for part in re.split(r'\s+·\s+|\s+\|\s+', mm.group(1)):
                        if ':' in part:
                            k, v = part.split(':', 1)
                            meta[k.strip().lower()] = v.strip()
                    break
            rid = m.group(1)
            if rid in rules:
                continue                      # first file wins (precedence)
            try:
                w = float(meta.get('w', meta.get('weight', '1')))
            except ValueError:
                w = 1.0
            rules[rid] = {'id': rid, 'title': m.group(2), 'sev': meta.get('sev', 'S3'), 'w': w,
                          'phase': meta.get('phase', 'misc'), 'applies': meta.get('applies', 'always'),
                          'verify': meta.get('verify', ''), 'page': meta.get('page', ''), 'source': path}
            order.append(rid)
    return rules, order


def in_stage(rule, phases):
    return phases is None or rule['phase'] in phases


def template(rules, order, phases, stage):
    return {'project': '', 'rev': '', 'stage': stage,
            'rules': [{'id': r, 'status': 'unverified', 'evidence': '', 'findings': [],
                       'applies': rules[r]['applies'], 'verify': rules[r]['verify']}
                      for r in order if in_stage(rules[r], phases)],
            'findings': []}


def score(rules, order, phases, assessment):
    given = {r['id']: r for r in assessment.get('rules', [])}
    rows, by_phase = [], {}
    tot_w = got_w = 0.0
    n_applicable = n_assessed = 0
    unknown_ids = sorted(set(given) - set(rules))
    for rid in order:
        rule = rules[rid]
        if not in_stage(rule, phases):
            continue
        a = given.get(rid, {})
        st = (a.get('status') or 'unverified').lower()
        ph = by_phase.setdefault(rule['phase'], {'w': 0.0, 'got': 0.0, 'applicable': 0, 'assessed': 0, 'fail': 0})
        if st != 'na':
            n_applicable += 1
            ph['applicable'] += 1
        if st in STATUS_SCORE or st == 'waived':
            n_assessed += 1
            ph['assessed'] += 1
        if st in STATUS_SCORE:
            tot_w += rule['w']
            got_w += rule['w'] * STATUS_SCORE[st]
            ph['w'] += rule['w']
            ph['got'] += rule['w'] * STATUS_SCORE[st]
            if st == 'fail':
                ph['fail'] += 1
        rows.append({'id': rid, 'title': rule['title'], 'sev': rule['sev'], 'w': rule['w'], 'phase': rule['phase'],
                     'status': st, 'evidence': a.get('evidence', '') or a.get('reason', ''),
                     'findings': a.get('findings', [])})
    findings = assessment.get('findings', [])
    open_ = [f for f in findings if (f.get('status') or 'open').lower() == 'open']
    s1 = [f for f in open_ if f.get('severity') == 'S1']
    s2 = [f for f in open_ if f.get('severity') == 'S2']
    cov = n_assessed / n_applicable if n_applicable else 0.0
    sc = got_w / tot_w if tot_w else None
    if s1:
        verdict, why = 'NOT READY', f"{len(s1)} open blocker(s): " + ', '.join(f.get('id', '?') for f in s1)
    elif s2:
        verdict, why = 'READY AFTER FIXES', f"{len(s2)} open major finding(s): " + ', '.join(f.get('id', '?') for f in s2)
    elif cov < 0.8:
        verdict, why = 'INCOMPLETE', f"no open blockers, but only {cov * 100:.0f}% of applicable guide rules verified (need 80%)"
    else:
        verdict, why = 'READY', 'no open S1/S2 findings and coverage >= 80%'
    return {'score': sc, 'coverage': cov, 'applicable': n_applicable, 'assessed': n_assessed,
            'verdict': verdict, 'verdict_reason': why, 'rows': rows, 'by_phase': by_phase,
            'open_counts': {s: sum(1 for f in open_ if f.get('severity') == s) for s in ('S1', 'S2', 'S3', 'S4')},
            'unknown_rule_ids': unknown_ids,
            'unverified': [r['id'] for r in rows if r['status'] == 'unverified']}


def to_markdown(res, stage):
    sc = 'n/a' if res['score'] is None else f"{res['score'] * 100:.0f}%"
    oc = res['open_counts']
    out = [f"**Verdict: {res['verdict']}** - {res['verdict_reason']}", '',
           f"Guide compliance (weighted): **{sc}** · Coverage: **{res['coverage'] * 100:.0f}%** "
           f"({res['assessed']}/{res['applicable']} applicable rules verified) · Stage: {stage}", '',
           f"Open findings: S1 {oc['S1']} · S2 {oc['S2']} · S3 {oc['S3']} · S4 {oc['S4']}", '',
           '| Phase | Score | Verified | Fails |', '|---|---|---|---|']
    for ph, d in res['by_phase'].items():
        s = f"{d['got'] / d['w'] * 100:.0f}%" if d['w'] else 'n/a'
        out.append(f"| {ph} | {s} | {d['assessed']}/{d['applicable']} | {d['fail']} |")
    out += ['', '| Rule | Title | Sev | W | Status | Evidence | Findings |', '|---|---|---|---|---|---|---|']
    mark = {'pass': 'PASS', 'partial': 'PARTIAL', 'fail': 'FAIL', 'na': 'n/a', 'unverified': 'unverified',
            'waived': 'waived'}
    for r in res['rows']:
        ev = (r['evidence'] or '').replace('|', '/').replace('\n', ' ')
        out.append(f"| {r['id']} | {r['title']} | {r['sev']} | {r['w']:g} | {mark.get(r['status'], r['status'])} | "
                   f"{ev[:160]} | {', '.join(r['findings'])} |")
    if res['unknown_rule_ids']:
        out += ['', f"Unknown rule IDs in the assessment (typo?): {', '.join(res['unknown_rule_ids'])}"]
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rules', action='append', required=True, help='rule pack markdown (repeatable, precedence order)')
    ap.add_argument('--stage', choices=list(STAGES), default=None)
    ap.add_argument('--phases', help='comma list overriding --stage')
    ap.add_argument('--template', action='store_true', help='print an assessment skeleton')
    ap.add_argument('--assessment', help='assessment JSON to score')
    ap.add_argument('--json', help='write the score result as JSON here')
    a = ap.parse_args(argv)
    rules, order = load_rules(a.rules)
    if not rules:
        sys.exit('no rules found: check the rule header format (#### ID — Title + `meta` line)')
    assessment = None
    if a.assessment:
        with open(a.assessment, encoding='utf-8') as fh:
            assessment = json.load(fh)
    stage = a.stage or (assessment or {}).get('stage') or 'release'
    phases = [p.strip() for p in a.phases.split(',')] if a.phases else STAGES.get(stage)
    if a.template:
        print(json.dumps(template(rules, order, phases, stage), indent=2))
        return
    if not assessment:
        sys.exit('give --assessment (or --template)')
    res = score(rules, order, phases, assessment)
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(res, fh, indent=2)
    print(to_markdown(res, stage))


if __name__ == '__main__':
    main()
