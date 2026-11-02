---
tags: [electronic-design-reviewer]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, WebSearch, WebFetch]
---

hey! I'm about to send my little sensor node to JLCPCB for assembly (first board I've ever ordered). It runs off USB 5V, has an ATtiny1616, a SHTC3 humidity sensor, an MCP3421 ADC for a thermocouple-ish thing later, and a 5V relay that will switch a small pump. I exported the netlist from KiCad 8. Can you review it before I order? I'm pretty new so please explain stuff.

Input files: sensor_node.net
