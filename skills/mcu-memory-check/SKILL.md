---
name: mcu-memory-check
description: Memory-aware review for microcontroller firmware (ESP32, ESP8266, STM32, nRF, RP2040, AVR; PlatformIO, Arduino, ESP-IDF, Zephyr). Use before adding or changing firmware logic, libraries, buffers, queues, TLS/HTTPS, BLE/Wi-Fi features or build flags, and before flashing or OTA-uploading a build. It checks that static RAM, peak heap and stack still fit with margin, so a feature that compiles doesn't fail at runtime from memory exhaustion.
---

# Microcontroller memory check

Firmware that compiles and links can still fail in the field. The usual cause is **peak heap**: the moment when the most expensive operations overlap (a TLS handshake while BLE scans and Wi-Fi buffers fill). The linker's "RAM 37%" line says nothing about it. Errors then surface as something unrelated: certificate "verification failed", DNS failures, `HTTP -1`, resets.

Run this check whenever a change adds or moves memory, and **before every flash or OTA upload of a changed build**.

## 1. Know the budget before changing anything

Find the project's recorded budget (its `CLAUDE.md`, README or memory). If none exists, measure it and record it (step 4). You need these numbers:

- **Static RAM**: `.data` + `.bss` from the build output, or `nm -S --size-sort firmware.elf` for the biggest symbols. On most MCUs static RAM and heap share one pool: **every byte of static is a byte less heap**.
- **Steady-state free heap** after every subsystem has started (Wi-Fi, BLE, mDNS, OTA, NTP).
- **Peak usage of the heaviest operation**, and the lowest free heap during it.
- **Free stack** in the tasks that do heavy work (`uxTaskGetStackHighWaterMark`).

## 2. Review the change for memory cost

For each item, estimate the bytes involved and say when they're held:

- **New statics**: arrays, ring buffers, `String`/`std::string` globals, lookup tables. Is `const` data in flash (`const`, `PROGMEM`, `static const`) and not copied into RAM?
- **Struct layout of anything stored N times**: queues, caches. Use the smallest exact type: 6 bytes for a MAC, not an 18-char string; `int16` tenths when the sensor's resolution is 0.1, not `float`. Mind padding. Bytes × capacity is the real cost.
- **Heap during the peak**: what is alive at the same moment? Body strings, JSON documents, by-value copies (`POST(String)` copies), parsed certificates, library buffers. Free or shrink them before the heavy call, not after.
- **Libraries and features**: new libraries, background services (mDNS, web servers), extra BLE roles or connections, more TLS roots. Check what each allocates at init and keeps.
- **TLS specifically**: mbedTLS typically holds two ~16 KB record buffers plus the parsed chain. Each pinned root is parsed on every handshake, and RSA-4096 or P-384 verification needs extra transient heap. Pin the minimum, measured set.
- **Concurrency**: radios and callbacks that allocate while the heavy operation runs (BLE scan callbacks, Wi-Fi RX buffers). Pause them around the peak if they can lose a few seconds.
- **Fragmentation**: many small, varied allocations in a loop, and growing `String`s. Prefer fixed buffers and reuse.
- **Growth over time**: maps keyed by device or MAC that never shrink, logs kept in RAM, TIME_WAIT sockets, leaks per iteration.

## 3. Measure with the right API

- On ESP32, `ESP.getFreeHeap()` / `getMaxAllocHeap()` **overstate** usable heap by ~13 KB, because they count IRAM. Use `heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)`, `heap_caps_get_largest_free_block(...)` and `heap_caps_get_minimum_free_size(...)`.
- The heap minimum since boot only ever falls. To get one operation's own low point, sample free heap every tick from a short-lived high-priority task during that operation.
- `heap_caps_register_failed_alloc_callback` names the exact size and caps of a failed allocation. Record into a fixed array inside the callback; never allocate there.
- Measure the real configuration with every subsystem running, not a stripped test build. Run the heavy operation several times, since later runs are worse once the heap fragments.
- With no serial port, serve the probe log over a TCP port or include it in an upload.
- Remove probes before committing, or keep only cheap, permanent diagnostics. A failed operation should print free and largest heap, so the next failure explains itself.

## 4. Decide and record

- **Margin rule**: the lowest free heap during the peak should stay at **about 10 KB or more**, or 15% of the heap, whichever is larger. Stack high-water marks should stay at 1 KB or more. Below that, the change doesn't ship until room is made.
- **Making room, cheapest first**: pack stored structs, shrink by-value copies, trim library features with build flags, pause concurrent allocators, drop optional services. Shrink queue capacity or remove features only with the owner's OK; say what is lost (offline buffering time, a convenience).
- Record the new budget in the project (static RAM, steady-state heap, peak low point, date measured), so the next change starts from real numbers.
- In the change summary, state the measured before/after figures. Never write "should fit".

## Report format

End the check with a short table: static RAM before/after, steady-state free heap, peak low point (operation name), stack high water, and a pass/fail against the margin rule. Then list what was done to make room, if anything.
