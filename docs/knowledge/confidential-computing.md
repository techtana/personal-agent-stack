# Confidential computing: how a cloud VM can process data its provider cannot read

Related: [Privacy for LLM systems](privacy-for-llm-systems.md) (what counts as sensitive and where the privacy
boundary sits).

Status note, as of 2026-11-01: Plan A, which uses confidential VMs, is **a plan, not a build**. Nothing here has been
run on a cloud account. The only runtime on the owner's machine is the local one (Plan B); the build is private-only
with `external.enabled: false`.

## What this is and why the project needs it

A cloud company that rents you a virtual machine normally can look inside it: the host software controls the machine's
memory. For a personal agent that holds chats, files and keys, that means trusting the cloud company's staff and
systems. Confidential computing changes the arrangement: the processor encrypts the VM's memory with a key the host
cannot reach, and the VM can prove, to a party you choose, that it is running the software you expect before that
party hands over any secret. The project wants this so that the agent stack can run in the cloud, available when the
owner's home machine is off, without the cloud provider being able to read prompts, answers or files. Plan A is built
on that idea. Plan B avoids the cloud for the model and does not need it.

## The ideas, built up from zero

### Data at rest, in transit, in use

Data has three states. **At rest** means stored on a disk. **In transit** means moving over a network. **In use** means
loaded into memory and being computed on. Picture a document: in a filing cabinet (rest), in an armoured van (transit),
or open on a desk while someone reads it (in use).

Disk encryption and TLS cover the first two for years. Neither covers the third. To compute on data, a processor needs
it in plain form in memory. That is the gap.

### Why encryption at rest is not enough

If a cloud VM's disk is encrypted but the key sits in the cloud company's key service, the company can decrypt it. Even
if the owner holds the key, the VM must use it, so the key and the plain data sit in memory while the VM runs. The host
operating system and hypervisor (the software that shares one physical machine among VMs) can read that memory. A bank
vault protects the cash; when the teller counts it at the counter, the vault is not helping.

Where the analogy stops: a human teller can be watched. A hypervisor reading memory leaves no sign inside the VM.

### Trusted execution environments

A **trusted execution environment** (TEE) is a part of a computer that is shielded from the rest, including from the
software that manages the machine. Think of a notary's room with a locked door: the building owner can own the walls
and the lease, but cannot enter. In a **confidential VM** the whole VM is the shielded room. The CPU encrypts the VM's
memory as it leaves the chip, with a key the CPU generates and keeps itself, so the host sees only scrambled bytes.

### AMD SEV-SNP and Intel TDX in plain words

These are the two CPU designs the plan uses. (This section is general background; the plans do not explain them, and
no external source for the description is recorded in the repo.)

- **AMD SEV-SNP** (Secure Encrypted Virtualization with Secure Nested Paging). The CPU encrypts each VM's memory with a
  per-VM key. "Secure nested paging" adds integrity: the host cannot silently swap, replay or remap a VM's memory pages
  to trick it. A small security processor on the chip manages keys and signs reports about the VM.
- **Intel TDX** (Trust Domain Extensions). Intel's equivalent: a VM becomes a "trust domain" with encrypted memory,
  managed by a signed software module running in a protected mode of the CPU.

The plans use SEV-SNP on the always-on main VM (Google Cloud N2D machines) and Intel TDX on the CPU model server
(C3 machines). Source: [PLAN-A section 2-3](../plans/PLAN-A-CLOUD-LED.md). These are different vendors with different
designs, but the user-facing promise is the same: the host cannot read the VM's memory.

### Remote attestation

Encrypted memory does not help if you cannot tell whether you are talking to a real shielded VM. **Remote attestation**
is how a VM proves that it is one. The pieces:

- **Measurement:** a hash (a fingerprint of a file; any change alters it) of what the VM booted: firmware, boot loader,
  kernel and, depending on the setup, more. The hardware records it as the VM starts.
- **Attestation report:** a document that holds the measurements and a nonce (a one-time value from the verifier, to
  stop replay), signed by a key rooted in the CPU vendor.
- **Verifier:** the party that checks the signature chain and compares the measurements with **reference values** it
  holds for the images the owner built. In Plan A the verifier is the Attestation Service of **Trustee**, running on
  hardware the owner controls. Source: PLAN-A section 1.

```
 VM (boot)            Key broker (Trustee, on owned hardware)
   |  1. boot, CPU records measurements
   |  2. ---- attestation report (signed by CPU) ---->
   |                       3. verify signature chain
   |                       4. compare with reference values
   |  5. <---- disk key, only if everything matches ----
   |  6. unlock disk, start services
```

**What a report proves:** this VM runs on genuine hardware of the stated type, with the stated firmware and boot
measurements, and its memory is protected from the host. **What it does not prove:** that the software is free of bugs
or that a running service has not since been tricked; that the CPU vendor is trustworthy; or that side-channel attacks
(learning secrets from timing or power) are impossible. A passport proves who issued it and what it states; it does
not prove the holder will behave.

### Key brokers and keys held outside the provider

A **key broker** holds secrets and releases them only to a verified VM. The project uses **Trustee**, which has a Key
Broker Service (KBS) and an Attestation Service. In Plan A the disks (data, model weights) are encrypted with LUKS
inside the VM, and the LUKS key is a Trustee resource. Backups are encrypted by restic before upload and their key is
also a Trustee resource, with a copy sealed offline. App secrets live on the encrypted disk or as Trustee resources,
not in Google Secret Manager. The effect: a disk snapshot or backup taken through the cloud provider's own tools is
unreadable without the broker. Source: PLAN-A section 1, acceptance test 5.

The broker runs on owned hardware (SEKAIHOME or the admin's machine), reached over WireGuard. If it is offline when the
VM reboots, the admin unlocks the disk by hand. A second Trustee instance on the admin's machine is a listed mitigation.
Source: PLAN-A section 8-9.

### TLS ending inside the VM

Normally a cloud load balancer receives HTTPS, decrypts it and forwards plain traffic, so the provider sees the
content. Plan A has no Google load balancer: the TLS connection from the browser ends at Caddy inside the confidential
VM. The provider carries encrypted packets it cannot open. Where the analogy stops: the provider still sees that the
packets exist (below).

### Confidential GPUs and their cost

Language models run best on GPUs, so a CPU-only TEE would be slow. In general terms (not
checked for this project), NVIDIA's H100 has a confidential-computing mode that encrypts traffic between the CPU VM and the GPU and protects GPU memory. The plan lists it as an option on A3 machines,
off by default, at roughly $10 or more per hour while running. The CPU option (C3 with TDX and AMX) is roughly $0.4-1
per hour and is expected to run 4-9B quantised models at a speed that is **not yet measured**. Source: PLAN-A section 3.
These costs are rough and unverified in the plans; they must be confirmed in the pricing calculator during A-S0.

### Residual trust in CPU vendors

Confidential computing moves trust; it does not remove it. You stop trusting the cloud company's operators and start
trusting AMD or Intel (and NVIDIA for the GPU) to have built the hardware correctly, to keep their signing keys safe
and to patch flaws. The plan says so in the user guide: what remains trusted is the vendors' hardware roots of trust,
the measured guest firmware, and protection against side-channel attacks. Hardware vulnerabilities in confidential
computing are a named risk; the mitigations are firmware and image updates, measurements pinned by attestation, and
keeping special-category data on-prem if the owner wants (`special_categories_location: onprem`). Source: PLAN-A
sections 1 and 9.

### What the provider can still see

The provider can see that a VM exists, when it starts and stops, its machine type and size, how much network traffic it
sends and receives, and when (**metadata and traffic timing**). Our own reasoning, not
from the plan: from the pattern of requests it could guess when the owner is active, and it sees where the encrypted
traffic goes. It can also **stop, delete or throttle**
VMs: this is an **availability** risk, not a confidentiality one. Plan A keeps logs sent to Google free of prompts,
answers and file names, and turns the serial console off. Confidential VMs do not live-migrate, so host maintenance
reboots them and needs a disk unlock. Source: PLAN-A sections 1 and 9.

## Rules of thumb and typical numbers

All figures are from the plans and are rough. None has been measured on a cloud account.

| Item | Figure | Source |
|---|---|---|
| Idle floor, Plan A | about $70-85 a month (rough, unverified) | PLAN-A section 7 |
| Main VM (N2D, 2 vCPU, 8 GB), disk, IP, backups | about $65-80 a month | PLAN-A section 7 |
| CPU model server, running | about $0.4-1 per hour; stopped about $0 (disk about $5) | PLAN-A section 7 |
| GPU confidential server, running | about $10+ per hour | PLAN-A section 7 |
| Earlier non-confidential floor | about $30 | PLAN-A section 7 |
| Model server idle stop | 20 minutes | PLAN-A A-D8 |
| Start timeout (boot + attestation + unlock + model load) | 300 s configured; real cold start not measured | PLAN-A section 3, A-S0 |
| Restore drill target | under 1 hour | PLAN-A test 10 |
| Trustee verifiers | plain `snp` and `tdx` verifiers exist; `az_*` vTPM ones are Azure-only | SHARED-COMPONENTS V8 |

Rules of thumb:

1. Keep the verifier and key broker outside the machine being verified, on hardware you control.
2. Release keys only after attestation; never ship a key inside the image.
3. End TLS inside the VM.
4. Treat metadata as visible. Log no content.
5. Plan for reboot unlocks, since confidential VMs do not live-migrate.

## Common misconceptions and edge cases

- **"Encrypted at rest means private."** Only while the data is not being used.
- **"Confidential means the cloud provider is out of the picture."** The provider keeps control of availability,
  billing, networking and what it sees as metadata.
- **"Attestation proves the software is safe."** It proves what was loaded and where. A flaw in that software is still
  a flaw.
- **"The key broker could be in the cloud too."** Then it needs trusting. The plan keeps it on owned hardware, at the
  price of manual unlock when it is offline.
- **"Google Secret Manager is fine for app secrets."** It puts the keys in the provider's hands, which defeats the
  design. Plan A excludes it.
- **"A confidential GPU is a drop-in."** It costs about $10 an hour in the plans' estimate and is off by default.
- **"The vendors' systems are proven secure."** Hardware flaws exist and are a named risk in the plan; the plan does not
  claim immunity.
- **Edge cases:** a measurement mismatch after an image update will block the key until the reference values are
  updated (test 4 in the plan expects exactly this refusal, with an admin alert); the boot-time unlock client is not
  shipped (see What we found); maintenance reboots need the broker or the admin.

## How the project uses it

Status, as of 2026-11-01: **planned, not built.** The gate (S1-S3) and Plan A (A-S0 through A9) are unbuilt. The shipped
build is private-only with `external.enabled: false`. Plan A would be the way to keep the stack up when SEKAIHOME is
off; Plan B runs every tier locally and needs no confidential VM. `special_categories_location: any` is the default
(decision G5/A-D5).

Plan A work packages ([PLAN-A-CLOUD-LED.md](../plans/PLAN-A-CLOUD-LED.md)):

- **A0:** decisions and accounts. **A-S0:** a spike on VM types per region, attestation tooling, tokens per second for a
  9B model on C3 TDX, and cold start.
- **A2:** Terraform for the Confidential VMs, firewall, and a service account limited to starting and stopping model
  servers; no Secret Manager for app secrets.
- **A3:** Trustee on owned hardware, LUKS unlock at boot through a custom initramfs hook, restic backups with keys held
  as Trustee resources, a restore script. Fallback: Clevis + Tang with an admin unlock.
- **A4:** the confidential model server image (llama.cpp on CPU, vLLM on GPU) and the start-on-demand controller.
- **A5:** WireGuard link to SEKAIHOME. **A6:** the encrypted deferred queue. **A7:** installer. **A8:** staging tests.
  **A9:** user guide and admin runbook.
- Shared packages that touch this topic: S1-S4, S6, S8, S7 (Authentik inside the VM); see the companion note
  [Privacy for LLM systems](privacy-for-llm-systems.md).

Decisions and history: [../design/DECISIONS.md](../design/DECISIONS.md) (2026-10-26: Plan A keys and TLS stay outside
Google; GCP draft archived), [README of plans](../plans/README.md),
[SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md), [Plan B](../plans/PLAN-B-LOCAL-LED.md). Plan B uses a
confidential VM only as a fallback if identity cannot run on Windows (about $60 a month, rough).

The earlier Google Cloud draft ([archive](../archive/GCP-DESIGN-DRAFT-2026-10-26.md)) was dropped because its defaults
contradicted private first: Vertex AI and other APIs as default model hosts, a non-confidential VM and Cloud Run GPU,
Google Secret Manager, and the orchestrator. Its cost target (about $15-35 a month idle) was lower because it did not
use confidential machines; Plan A's floor is about double that of the earlier non-confidential design, because the
smallest confidential machine types are larger.

Simplified or deferred: the GPU option is off; the encrypted queue and the on-demand start controller are designs only;
the unlock client is custom work (see below); manual unlock is the fallback.

## What we found

Only one plan check touches this area; it was a documentation and source check, not a cloud run. Recorded in
[SHARED-COMPONENTS.md section 7](../plans/SHARED-COMPONENTS.md).

- **V8, partly (2026-10-26):** Trustee has plain `snp` and `tdx` verifiers; the `az_*` vTPM verifiers are Azure-only.
  No documented test on Google Cloud was found. No boot-time client ships: clevis-pin-trustee has no release, and the
  systemd-cryptsetup token integration is still a proposal. A-S0 must budget a custom initramfs hook (an attester plus
  a KBS fetch). Clevis + Tang remains the fallback, at the price of no attestation.
- **Not verified:** Confidential VM availability per region, CPU inference speed on C3 TDX, the cold-start time, all
  costs, and the attestation tooling per VM type. All are A-S0 work.

## Open questions

- Does Trustee's `snp` or `tdx` verifier work on Google Cloud Confidential VMs with their guest firmware? (V8)
- How slow is CPU inference on C3 with TDX for a 9B model, and is that usable daily? (A-S0)
- What is the cold start from stopped to first token (boot, attestation, unlock, model load)? (A-S0)
- Which regions offer the needed machine types? (A-D6)
- Can the owner accept manual unlock when SEKAIHOME is off at a reboot? (A-D3)
- Do the cost estimates hold? They are marked rough and unverified.
- Are the CPU vendors' known side-channel and firmware issues acceptable for special-category data, or should it stay
  on-prem (A-D5)? A decision for the owner.

## Sources and further reading

The plans record no URLs for AMD, Intel, NVIDIA, Google Cloud or Trustee documentation. This note does not supply any.
"URL not recorded" means a reader should look the item up by name.

| Title | Org | Year | Link | Good for |
|---|---|---|---|---|
| Plan A: cloud-led, private first | this repo | 2026 | [PLAN-A-CLOUD-LED.md](../plans/PLAN-A-CLOUD-LED.md) | the protection layers, topology, cost, risks |
| Shared components (principle 1, V8, S7) | this repo | 2026 | [SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md) | what "private" means; the Trustee check |
| Plans overview | this repo | 2026 | [README.md](../plans/README.md) | Plan A and Plan B compared |
| Archived Google Cloud draft | this repo | 2026 | [archive](../archive/GCP-DESIGN-DRAFT-2026-10-26.md) | the earlier, non-confidential design |
| Design decisions log | this repo | 2026 | [DECISIONS.md](../design/DECISIONS.md) | decisions on keys and TLS |
| Trustee, Clevis, Tang, restic, LUKS, WireGuard, AMD SEV-SNP, Intel TDX, NVIDIA H100 confidential computing, Google Cloud Confidential VM | various | - | URL not recorded | vendor documentation |

## Changes

- 2026-11-01: first version.
