---
tags: [electronic-design-reviewer]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, WebSearch, WebFetch]
---

quick one: for a ~1 second power-on delay on my 5V board I put a 100k resistor and a 10uF 0603 X5R 6.3V ceramic on the EN pin of my LDO (it's an AP2112K). my friend says ceramics are totally fine for this. is that ok or should i change it?
