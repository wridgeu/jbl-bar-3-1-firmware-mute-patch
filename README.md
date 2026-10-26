<h1 align="center">JBL Bar 3.1 (2018–2020)</h1>

<p align="center">
  3.1-channel 4K Ultra HD soundbar with wireless subwoofer<br>
  <b>Unofficial firmware patch for the audio cut-out after silence</b>
</p>

An unofficial patch for the [**JBL Bar 3.1**](https://support.jbl.com/de/de/speakers/speakers-soundbars/JBL+BAR+3.1.html)
(2018 to 2020, the 3.1 with the wireless subwoofer) on firmware **V49**, the newest on JBL's download page. Not for any
other JBL model.

**The problem:** after a pause or a moment of digital silence, the bar mutes and needs from 0.6 s to over a second before
sound comes back, and the display shows "PCM" each time ([Why this exists](#why-this-exists)).

**The fix:** flash the prebuilt **A+C** build, `firmware/patched/fix-A+C/JBLBAR3_1.HUI`. On the test unit, sound now
comes back almost at once. It is experimental and has been tested on one unit only, so read the warnings below first.

- **Fix A** shortens the safety mute the bar adds whenever the incoming signal changes or stops: 0.6 s → 0.2 s in A+C
  (0.1 s in the fix-A-only build).
- **Fix B** makes the bar's sound processor (the DSP) wait longer before it reports silence. Experimental and not
  prebuilt.
- **Fix C** stops the bar from restarting the DSP after every pause, which is what took the longest and showed "PCM".

The repository also holds the official firmware (unmodified, with hashes), the scripts that build and check every
variant, and the research behind it ([NOTES.md](NOTES.md)). How the fixes work: [The three fixes](#the-three-fixes).

> [!CAUTION]
> **Flashing modified firmware can make your soundbar permanently unusable ("bricked").**
> This modification is unofficial and unsupported. Fix A and fix A + C have each been tested on **one** unit only, and
> fix B in its current form on **none**. JBL no longer supports the Bar 3.1, and the only known recovery methods for a
> soundbar that no longer starts require opening the case. **If you cannot afford to lose the soundbar, do not flash
> this.**

> [!WARNING]
> **Disclaimer: use entirely at your own risk.**
> - Everything in this repository (firmware, scripts, documentation) is provided **"as is", without warranty or guarantee
>   of any kind**: not that it works, not that it is safe, not that it is fit for any purpose.
> - The authors and contributors **accept no liability and no responsibility** for any damage or loss of any kind,
>   including a bricked or damaged soundbar, subwoofer, TV or other device, lost warranty, or any other direct or indirect
>   consequence of using this.
> - The research is reverse engineering. It **may contain errors**, and most of it has not been checked on hardware.
> - **You** decide to flash it, and you are solely responsible for the result. Flashing almost certainly voids any
>   warranty that is left.
> - **Bar 3.1 only.** Do not use it on any other model (Bar 2.1, Bar 5.1, Bar Studio, ...), and do not flash firmware of
>   another model on the Bar 3.1; see [Firmware of other JBL models](#firmware-of-other-jbl-models).
> - **Keep the power on** during the update, which takes about 5 to 6 minutes.

> [!IMPORTANT]
> This project is not affiliated with or endorsed by JBL or Harman International. "JBL" is a trademark of Harman
> International Industries. The original firmware is Harman's copyrighted software, included unmodified so that the patch
> can be reproduced and verified. See [Legal](#legal).

## Contents

- [Quick start](#quick-start)
- [Experience so far](#experience-so-far)
- [Why this exists](#why-this-exists)
- [The three fixes](#the-three-fixes)
- [What is verified](#what-is-verified)
- [Repository layout](#repository-layout)
- [Installing](#installing)
- [Going back to the official firmware](#going-back-to-the-official-firmware)
- [Building it yourself](#building-it-yourself)
  - [Choosing the fixes](#choosing-the-fixes)
  - [Choosing the mute length](#choosing-the-mute-length)
  - [Tools](#tools)
- [Other things to try](#other-things-to-try)
- [Firmware of other JBL models](#firmware-of-other-jbl-models)
- [How it works](#how-it-works)
- [Sources](#sources)
- [Legal](#legal)

## Quick start

Read the warnings above first.

1. **Check that your bar runs V49.** On the remote, hold **DIM DISPLAY** for 3 to 4 s, then press **SOUND MODE**, then
   **NIGHT MODE** (from JBL's V49 instructions). The second number shown is the MCU version. If it is below 49, install
   the **official** V49 first.
2. **Pick a build.** Both files are named `JBLBAR3_1.HUI`, as the soundbar expects, so each has its own folder:

   | Build | File | What to expect |
   |---|---|---|
   | **Fix A (20 ticks) + C**, recommended | `firmware/patched/fix-A+C/JBLBAR3_1.HUI` | sound back almost at once after a pause, pops about as mild as with the stock firmware; experimental, tested on one unit |
   | **Fix A** | `firmware/patched/fix-A/JBLBAR3_1.HUI` | the longest-tested build; sound back only a little sooner |

   To download a single file, open it on GitHub and choose **Download raw file**.
3. **Check its SHA-256** against the matching line in [SHA256SUMS](SHA256SUMS): `Get-FileHash .\JBLBAR3_1.HUI` in
   PowerShell, `sha256sum JBLBAR3_1.HUI` elsewhere, or `sha256sum -c SHA256SUMS` in a clone. Do not flash a file whose
   hash does not match.
4. **Flash it** from a USB stick as in [Installing](#installing) (AUX cable to the subwoofer, **VOLUME DOWN + POWER**,
   about 5 to 6 minutes; keep the power on).
5. **Test it** (pauses short and long, a switch to Dolby/DTS, standby). If anything is wrong, flash the other build or
   the original firmware ([Going back](#going-back-to-the-official-firmware)).

The 20-tick mute is what worked best on the test unit, not a rule: to try other values, see
[Choosing the mute length](#choosing-the-mute-length).

**Where to go next:** [Experience so far](#experience-so-far) for the test results,
[The three fixes](#the-three-fixes) for what each fix changes, [Building it yourself](#building-it-yourself) and
[Choosing the fixes](#choosing-the-fixes) for your own builds (including fix B), and [NOTES.md](NOTES.md) for the
research.

## Experience so far

One unit, Chromecast through the TV over HDMI ARC. No guarantee that yours behaves the same.

**Fix A (10 ticks):**

- **Nothing broke.** The update was accepted, and the soundbar has worked normally since.
- **The difference is noticeable, but small.** Sound comes back a little faster after a pause; for everyday use the gain
  is close to negligible.
- **Clicks on pause/resume remain.** The stock firmware clicks too, only later.

**Fix B with threshold 0** (the value Cirrus' guide recommends): the bar showed "PCM" but played **no audio at all**.
Flashing fix A again brought the sound back. 0 is therefore refused by `patch.py`; large thresholds are untested.

**Fix A + C:**

- **10 ticks** (`10 --ignore-silence`): **sound is back immediately after a pause**, and the display no longer shows
  "PCM" when it returns. A clear improvement over fix A alone. Slight pops remain; they come from fix A's shorter codec
  mute, not from fix C.
- **20 ticks** (`20 --ignore-silence`, the prebuilt `fix-A+C`): sound is back almost at once, and the pops are much
  milder, about as they were with the stock firmware. A good compromise; 30 ticks was not tried.
- Not checked yet, for either: volume/EQ after many pauses, PCM ↔ Dolby/DTS switches, standby, other inputs (see the
  checklist in [Choosing the fixes](#choosing-the-fixes)).

## Why this exists

[**"Audio cuts out after short period of silence"**](https://www.reddit.com/r/appletv/comments/9cwz0b/audio_cuts_out_after_short_period_of_silence/)
(r/appletv, 2018) describes it well. An Apple TV feeds a Bar 3.1, and:

- menu click sounds are missing or start cut off;
- the first second of audio is lost when a video starts or resumes after a pause;
- the bar shows **"PCM"** each time sound returns, "10-20 times" while browsing the settings.

Other owners in the thread see the same over HDMI, ARC and optical, plus a **pop** every time. The patch was developed with a
Chromecast, which behaves the same way. JBL support's answer:

> "This unit is able to identify and lock onto a digital audio signal in less than a second. [...] sometimes when listening
> to music, this will result in the beginning of a music track not being heard. Or when scrolling through a menu on a TV or
> source component, the menu sounds may not come through. We have an update coming that will shorten the lock on time to
> less than .6 seconds."

V49's codec mute of 60 ticks of 10 ms (0.6 s) is consistent with that promise, although V49's release notes do not
mention it, and no older Bar 3.1 firmware was available to compare.

## The three fixes

Terms used below:

- **Codec:** the chip that receives the digital audio and tells the main program when the signal locks, changes or
  goes silent.
- **DSP:** the Cirrus sound processor that decodes PCM, Dolby and DTS. It has its own flash chip.
- **Tick:** 10 ms, the unit of the bar's mute timer. 60 ticks = 0.6 s.
- **Part 0 / part 2:** the main program and the DSP's flash image inside the `.HUI` update file.

Sound is lost after a pause in two ways:

1. **DSP re-setup after silence.** After 48,000 samples of digital silence (about 0.5 to 1 s at 48 kHz), the DSP reports
   "silent input". The bar then mutes and forgets the stream. When sound returns, it sets the DSP up again from scratch:
   a 0.55 s mute (which covers a 0.3 s wait), then a further mute of at least 50 ms (at least 0.5 s on HDMI inputs).
   That is when the display shows "PCM".
2. **Codec mute.** Whenever the audio codec loses lock, reports digital silence or sees a different format, the bar
   mutes for 60 ticks (0.6 s).

Fix A shortens the codec mute. Fixes B and C both go after the DSP re-setup, at different ends: B keeps the DSP from
sending the "silent input" report, C makes the bar ignore it.

| | Fix A: codec mute | Fix B: DSP silence threshold | Fix C: ignore the silence report |
|---|---|---|---|
| Changes | 3 mute timeouts: 60 → 10 ticks (20 in A+C) | 8 DSP settings: 48,000 → `0x7fffffff` | 1 branch |
| Effect | codec mute 0.1 s (0.2 s) instead of 0.6 s | DSP should practically never report silence | DSP re-setup skipped |
| Status | ✅ tested, 1 unit | ❌ 0: no audio · ⚠️ others untested | ⚠️ tested, 1 unit, with A |
| Part changed | part 0 (main program) | part 2 (DSP flash) | part 0 (main program) |
| Prebuilt file | `fix-A/`, and in `fix-A+C/` | none | in `fix-A+C/` |
| In `patch.py` | on by default (ticks argument) | `--silence N` | `--ignore-silence` |

The three are independent: each can be built alone or with the others (see [Choosing the fixes](#choosing-the-fixes)).
If the source stops sending altogether (a Chromecast does after 3 s of silence, see
[Other things to try](#other-things-to-try)), the codec loses lock, which fix A shortens. B and C are aimed at pauses in
which the source keeps sending digital silence; whether they also help when it stops is not known.

**Fix A** sets the three timeouts in the codec monitor:

| Instruction | When |
|---|---|
| `0x8802b67c` | codec loses lock |
| `0x8802b90c` | codec reports digital silence (`No Digital Signal Input`) |
| `0x8802ba38` | codec reports a different signal format |

To keep the checksums valid, a debug log message changes from `codec:unlock,mute on` to `-ode/:uolock,mute on`. Other
mutes (input switching, power-up), the fade-in and all other parts stay as they are.

**Fix B** changes `PCM_AUTODETECT_SILENCE_THRESHOLD` of the Cirrus DSP: the number of silent samples after which the DSP
declares silence while playing PCM. What is known:

- ✅ The 8 values sit in configuration blocks that no checksum covers; the DSP programs and their checksums are not touched.
  The updater checks only the container checksums, which `patch.py` recomputes.
- ✅ Nothing else in the main program depends on the silence report. **Auto standby** uses the codec lock, the input
  GPIOs and HDMI +5 V, so the bar still goes to standby when the source is off.
- ✅ A bad value is recoverable: fix B leaves the main program and the updater alone, and flashing fix A again after the
  failed test with 0 restored the sound.
- ❌ **0 means "declare silence at once"**, not "off", despite Cirrus' guide recommending 0 for non-CD sources. Tested: no
  audio. No document defines a value that turns detection off.
- ⚠️ `0x7fffffff` (about 6 to 12 hours of silence) is the largest value that is safe if the DSP compares it as a signed
  number. Every Cirrus image checked (Bar 2.1, Bar 3.1, Bar 5.1) ships 48,000, so no product shows that a large value
  works.
- ⚠️ Possible side effects: faint hiss during long silences on HDMI inputs, where the bar used to mute the amplifier; a
  switch from PCM to Dolby/DTS without a pause might not be detected.

**Fix C** changes one branch in the DSP message handler of the main program. In the stock firmware, the "silent input"
report (code `0x20`) has no case of its own and ends up at `NO DATA IN` (the firmware's "no data" routine, named after
its debug message): mute, and forget the stream type. Fix C sends it to the handler's return instead, so the report is
ignored. What is known:

- ✅ Exactly one instruction changes (`0x880275a4`). As for fix A, the debug text changes to keep the image checksums,
  and part 0's container checksum is recomputed.
- ✅ Only codes `0x17` to `0x20` are affected. Besides `0x20`, the only documented one is `0x1c` (AAC, which the bar
  does not decode); it is now ignored too, instead of muting. Code `0x00` ("no data") and every other code behave as
  before.
- ✅ Auto standby and the codec mute (fix A) do not depend on the report: they use the codec and the inputs, not the DSP.
- ⚠️ What happens during a pause (partly traced in the code; the tests on one unit match):
  1. The DSP still detects silence at the stock threshold and still sends the report. Detection is neither off nor
     delayed.
  2. The bar ignores the report: no mute, and it keeps the stream type ("PCM").
  3. The DSP picks up the input again by itself when sound returns. The bar sees the same stream type as before, so
     it skips the set-up: no 0.55 s mute and no "PCM" on the display.
- ✅ The full set-up still runs when something really changes, for example a source switch or a new stream type
  (PCM ↔ Dolby/DTS). None of the paths that start it goes through the changed branch.
- ⚠️ Possible side effect: if the DSP loads its configuration again on its own, volume or EQ settings might be lost
  until the next input change.
- ⚠️ Fix C changes part 0, like fix A: if it went wrong badly enough to stop the bar from starting, the updater would be
  gone with it. Fix A shows that a part 0 change that keeps its checksums is accepted and boots. The changed branch only
  matters when the DSP sends one of those codes.

> [!NOTE]
> **Clicks.** The codec mute hides clicks while the audio chain re-syncs, so a shorter mute makes them easier to hear.
> To mute longer, build another value (see [Choosing the mute length](#choosing-the-mute-length)).

## What is verified

| Claim | Status |
|---|---|
| The ZIP in `firmware/original/` is byte-identical to JBL's download | ✅ SHA-256 |
| `fix-A` passes all container checksums | ✅ |
| `fix-A` keeps both checksums of the main program image | ✅ |
| The same two checks for `fix-A+C`, whose only further changes are the fix C branch and a different debug text | ✅ |
| The checksum and header rules also hold for a second official firmware (Bar 2.1 V48) | ✅ |
| `fix-A`: only the 3 timeouts, the debug text and part 0's checksum in the container table differ; the compressed modules, the other parts and the part 0 header are byte-identical | ✅ |
| Fix A: the changed instructions are safe on every code path | ✅ disassembly |
| One tick is 10 ms (2 ms timer interrupt, countdown on every 5th) | ✅ traced in the code ([NOTES](NOTES.md#how-long-a-tick-is)), not measured |
| The soundbar accepts both patched files and works | ✅ 1 unit, Chromecast through the TV over HDMI ARC |
| The updater checks the model ("3.1") and the part checksums, and writes every part | ✅ disassembly ([NOTES](NOTES.md#the-updater)), not fully traced |
| Flashing again restores a broken DSP configuration | ✅ 1 unit (fix A over fix B with threshold 0) |
| Fix B: no checksum covers the changed values, and nothing else in the main program depends on them | ✅ analysis ([NOTES](NOTES.md#fix-b-the-dsp-silence-threshold)) |
| Fix B with threshold 0 | ❌ no audio |
| Fix B with a large threshold | ⚠️ not tested |
| Fix C: the changed branch is taken only by codes `0x17` to `0x20`, and its new target is the handler's normal return, with the same stack frame | ✅ disassembly ([NOTES](NOTES.md#fix-c-ignore-the-silence-report)) |
| Fix C: a real change (source switch, new stream type) still starts the full DSP set-up | ✅ disassembly ([NOTES](NOTES.md#fix-c-ignore-the-silence-report)) |
| Fix C on a soundbar | ✅ tested on one unit, with A at 10 and 20 ticks: sound back at once or almost at once, no "PCM" · ⚠️ side effects not checked yet |
| Dolby, DTS, other sample rates, optical, Bluetooth | ⚠️ not systematically tested |
| Subwoofer link, long-term use | ⚠️ not tested |
| Flashing the official file again restores stock firmware | ⚠️ likely (same updater path as above), not tested |

The key addresses in this README and in [NOTES.md](NOTES.md) can be checked against the original firmware with one
command each. See [Checking these notes yourself](NOTES.md#checking-these-notes-yourself).

## Repository layout

```
firmware/
  original/                   official JBL files, unmodified
    JBL_BAR_3_1_USB_V49.zip     as downloaded from JBL
    JBLBAR3_1.HUI               extracted from the ZIP
    JBL Bar 3.1 Upgrade instructions ENGLISH V49.pdf
  patched/                    named JBLBAR3_1.HUI, the way the soundbar expects, one folder per build
    fix-A/JBLBAR3_1.HUI         fix A (10 ticks)
    fix-A+C/JBLBAR3_1.HUI       fix A (20 ticks) + fix C, recommended
tools/
  hui.py                      check / unpack / repack the .HUI container
  patch.py                    builds the patched firmware from the original (fix A, optionally fixes B and C)
  selftest.py                 checks patch.py and hui.py against known outputs and bad input
  mips.py                     research helpers: find strings, disassemble, list modules
NOTES.md                      research notes with addresses, evidence and sources
SHA256SUMS                    hashes of all firmware files
pyproject.toml, uv.lock       Python project for uv (dev only: capstone for mips.py, ruff for linting)
```

| File | SHA-256 |
|---|---|
| `firmware/original/JBL_BAR_3_1_USB_V49.zip` | `a0b9898421ecdb408af6f5eaf1ff663c32edd45fa6f99d09603626583f3e96dd` |
| `firmware/original/JBLBAR3_1.HUI` | `d5d014f18cfb17a4e4f65179cd14d024c7462f7a7c6fd78f65aaf704287bcaa6` |
| `firmware/original/JBL Bar 3.1 Upgrade instructions ENGLISH V49.pdf` | `23e887b609af4cb7f3b23c8b0aa565ad5e2d0bd5b267ccc0ac436feab19ab5c8` |
| `firmware/patched/fix-A/JBLBAR3_1.HUI` | `9238994226eb5a4d9bdd22d066f8ea17885997f3700eefd0899ac661ca06f395` |
| `firmware/patched/fix-A+C/JBLBAR3_1.HUI` | `b1cd6ca6b6b5e45038644bd93e9dc391db372340941f3ac0bdcc3a8799ffc808` |

Check them with `sha256sum -c SHA256SUMS` or, in PowerShell, `Get-FileHash <file>`. **Do not flash a file whose hash does
not match.**

## Installing

These are JBL's steps from the [V49 instructions](firmware/original/JBL%20Bar%203.1%20Upgrade%20instructions%20ENGLISH%20V49.pdf),
with the patched file:

1. Copy **only** the file you picked (`firmware/patched/fix-A+C/JBLBAR3_1.HUI`, `fix-A/JBLBAR3_1.HUI` or your own build)
   into the root folder of a USB stick (FAT32 is the safe choice). The name must be exactly `JBLBAR3_1.HUI`: the updater
   looks for nothing else.
2. Turn the soundbar **off**.
3. Connect an AUX cable from the bar's **AUX** port to the subwoofer's **SW Upgrade** port. The subwoofer is updated over
   it; this patch leaves its firmware unchanged.
4. Plug in the stick and turn the bar **on**.
5. Hold **VOLUME DOWN + POWER** on the bar for 5 to 6 seconds.
6. The display shows `UPDATE MODE`, then `WAIT` for 5 to 6 minutes. **Do not touch anything.**
7. `DONE` appears and the bar restarts (`ON`). Remove the cable and the stick.

On `FAIL` or `ERROR`, check the stick (file name, nothing else on it) and the cable, then try again. Owners of the
similar Bar 5.1 report that some USB sticks don't work ([unixgr](https://www.unixgr.com/jbl-5-1-soundbar-firmware-upgrade/)).

## Going back to the official firmware

Repeat the steps with `firmware/original/JBLBAR3_1.HUI`. The updater has no version check and writes every part of the
file, the DSP flash included. Flashing fix A over a failed fix B test restored the sound, so the original should restore
everything too; that exact step has not been tested.

> [!CAUTION]
> **If the soundbar does not start after an update,** there is no official recovery. Two known routes, both untested on
> the Bar 3.1 and both requiring an open case:
> - the Sunplus UART boot mode ([hd-audio-rush-sphe8202r](https://github.com/ArthurKoba/hd-audio-rush-sphe8202r));
> - reprogramming the SPI flash chip with a programmer (e.g. a CH341).
>
> Both are far easier with a **dump of the flash chip made before** flashing anything.

## Building it yourself

With [uv](https://docs.astral.sh/uv/), which installs Python and the dependencies by itself:

```sh
git clone https://github.com/wridgeu/jbl-bar-3-1-firmware-mute-patch
cd jbl-bar-3-1-firmware-mute-patch
uv run tools/patch.py firmware/original/JBLBAR3_1.HUI build/fix-A+C/JBLBAR3_1.HUI 20 --ignore-silence  # = fix-A+C
uv run tools/patch.py firmware/original/JBLBAR3_1.HUI build/fix-A/JBLBAR3_1.HUI                        # = fix-A
uv run tools/hui.py check build/fix-A+C/JBLBAR3_1.HUI                                                  # must print OK
uv run tools/hui.py check build/fix-A/JBLBAR3_1.HUI                                                    # must print OK
sha256sum build/fix-*/JBLBAR3_1.HUI                                                                    # = SHA256SUMS
uv run tools/selftest.py                                                                               # all builds
uv run ruff check                                                                                      # lint
```

How to check a file before you flash it:

- **`hui.py check`** verifies the container checksums, the same ones the soundbar's updater checks before it writes
  anything. It prints `OK`, or the name of each part whose checksum is wrong. `patch.py` already runs this check before
  it writes its output; run it again on the copy on your USB stick to catch a bad copy.
- **SHA-256:** a build with the arguments of a published file must have the same hash as that file in
  [SHA256SUMS](SHA256SUMS). For any other value only `hui.py check` applies.

Builds go to `build/`, which git ignores; lint settings are in `pyproject.toml`. With Python 3.11 or newer, the same
works with `python` instead of `uv run`: `patch.py`, `hui.py` and `selftest.py` need only the standard library.

- **Reproducible:** the build gives the same bytes every time. With the defaults (fix A, 10 ticks), the result is
  identical to `firmware/patched/fix-A/JBLBAR3_1.HUI`; with `20 --ignore-silence`, to
  `firmware/patched/fix-A+C/JBLBAR3_1.HUI`. So you can check the published files without trusting them.
- **Stock build:** with 60 ticks and no other option (or `--silence 0xbb80`, the stock value), the result is
  identical to the original.
- **Refusals:** `patch.py` runs only on the original V49 file (it checks the SHA-256), so not on an already patched
  file. It refuses tick values outside 1 to 63 and `--silence 0`, stops if a checksum does not come out right, and warns
  if the output is not named `JBLBAR3_1.HUI`.
- **Self-test:** `selftest.py` rebuilds the five builds in [Choosing the fixes](#choosing-the-fixes) and the stock
  build against known hashes, and feeds the tools bad input. It takes a few seconds.

### Choosing the fixes

> [!WARNING]
> **Fixes B and C are experimental, and so is the recommended A+C build.** Fix B's first and only hardware test, with
> threshold 0, ended with no audio until fix A was flashed again; large thresholds have never run on a soundbar. Fix C
> has been tested on one unit, together with fix A. Only try them if you are ready to re-flash.

Pick by how much risk you accept. The arguments go after the output file. The tick value controls fix A (60 is stock, so
it turns fix A off), `--silence` fix B, and `--ignore-silence` fix C:

| Build | Arguments | Risk |
|---|---|---|
| Fix A only | none | tested on one unit; same as `firmware/patched/fix-A/` |
| Fix B only | `60 --silence 0x7fffffff` | **untested**; touches only the DSP configuration |
| Fix C only | `60 --ignore-silence` | **untested** alone; touches the main program |
| Fix A + B | `10 --silence 0x7fffffff` | **untested** |
| Fix A + C (recommended) | `20 --ignore-silence` | tested on one unit: sound back almost at once, mild pops; side effects not checked yet; same as `firmware/patched/fix-A+C/` |

B and C go after the same report, so start with one of them. Both can be combined
(`10 --silence 0x7fffffff --ignore-silence`), but a test would then not tell you which one helped.

Instead of the arguments, you can set `TICKS`, `SILENCE` and `IGNORE_SILENCE` at the top of
[`tools/patch.py`](tools/patch.py). `--silence` takes 1 to `0x7fffffff`; 0 is refused. A smaller value, such as
`--silence 480000` (5 to 10 s of silence), is a more cautious first test.

If you try fix B or C, test it right after flashing, and keep a stick with fix A or the original file at hand:

- pause/resume, shortly and for longer than 3 s;
- after a pause: are volume, EQ and sound mode still as before?
- switching between PCM and Dolby/DTS (apps, trailers);
- each input you use: HDMI, ARC, optical, Bluetooth;
- pull the cable or turn the source off while playing: the bar should go quiet, not hum or hiss;
- leave the source off: the bar should still go to standby after about 10 minutes;
- listen for hiss during long silences.

If anything is wrong (no sound, sound only on some streams, constant dropouts), flash fix A or the original file.

### Choosing the mute length

The codec mute (fix A) is counted in **ticks of 10 ms**. Any value from 1 to 63 builds; above 63 the debug text cannot
keep the checksums.

| Ticks | Mute | |
|---|---|---|
| 60 | 0.6 s | stock (output identical to the original file) |
| 30 | 0.3 s | |
| **20** | **0.2 s** | **with fix C: the prebuilt `fix-A+C`**, tested on one unit; 20 is also what stock uses for a second mute on the same path |
| **10** | **0.1 s** | **the prebuilt `fix-A`**, tested on one unit; with fix C also tested, but with slight pops |
| 5 | 0.05 s | about 1.5 Dolby frames (32 ms each): expect more clicks on format changes |
| 1 | up to 0.01 s | minimum (see below for 0) |

Shorter means sound returns sooner, with more audible clicks, especially when switching between PCM, Dolby and DTS.
Longer means fewer clicks, but more of each sound's start is cut off.

**With fix C, use a longer mute.** Fix C takes care of the pause itself, so fix A's mute then matters mainly for the
clicks. On the test unit, A + C at 10 ticks brought sound back at once but with slight pops; at 20 ticks (the prebuilt
`fix-A+C`) the pops were much milder and sound still came back almost at once. That is a recommendation, not a rule:
your source, TV and ears may prefer another value. Build and try a few yourself, for example `15 --ignore-silence` or
`30 --ignore-silence`, and keep the one you like best.

> [!NOTE]
> **Why not 0?** In the firmware, a mute of 0 ticks means "stay muted until something explicitly unmutes", so the bar
> would most likely go silent after the first dropout. `patch.py` refuses it.
>
> **Why not just 1?** It builds, but it removes only this one delay. The codec still has to lock again, other mutes on the
> same path stay (20 ticks), and after silence the DSP set-up adds 0.55 s or more (see
> [The three fixes](#the-three-fixes)). Expect little gain over 10 and more clicks.

To use another value, pass it after the output file
(`uv run tools/patch.py firmware/original/JBLBAR3_1.HUI build/test/JBLBAR3_1.HUI 30 --ignore-silence`); some values take
a few seconds. Check the result with `hui.py check`, flash it as in [Installing](#installing), and test pause/resume,
the start of a video, PCM ↔ Dolby/DTS switches and menu sounds. Only 10 (with and without fix C) and 20 (with fix C)
have run on a soundbar; any other value gives a file with a different hash that **nobody has tested**, although its
checksums are kept the same way.

> [!WARNING]
> Change only these settings. `hui.py check` covers only the container checksums. `patch.py` also checks the image
> checksums, but neither can tell whether other changes are sound. A file that passes every check can still fail to boot.

### Tools

| Command (`uv run ...`) | What it does |
|---|---|
| `tools/hui.py check <file.HUI>` | verifies the container checksums |
| `tools/hui.py unpack <file.HUI> <dir>` | writes each part to `<dir>/part<i>_type<t>.bin` |
| `tools/hui.py repack <file.HUI> <dir> <new.HUI>` | puts edited parts back and recomputes the container checksums |
| `tools/patch.py <original.HUI> <out.HUI> [ticks] [--silence N] [--ignore-silence]` | builds the patched firmware |
| `tools/selftest.py` | checks `patch.py` and `hui.py` |
| `tools/mips.py find <text>` | finds a string in the main program and the functions that use it |
| `tools/mips.py dis <address> [count]` | disassembles the main program or one of its two code modules |
| `tools/mips.py modules` | lists the compressed modules whose CRC32 matches |

`mips.py` needs capstone. `uv run` installs it; without uv, run `pip install capstone==5.0.9`.

## Other things to try

Before (or instead of) flashing anything:

- **Set the TV's digital audio output to PCM.** Format changes between PCM and Dolby/DTS then stop, and with them the
  re-detection after each change. In the author's setup the TV already outputs PCM with 0 delay, and the cut-outs still
  happen, because the remaining cause is silence, not format changes.
- **Optical instead of HDMI/ARC** goes through the same codec and DSP. It skips the hard mute and the longer wait that
  only HDMI inputs get, but the silence detection is the same.
- **Keep the source from going silent.** On a PC, tools that keep the audio device open (Kodi's
  ["Keep audio device alive"](https://kodi.wiki/view/Settings/System/Audio),
  [Sound Keeper](https://veg.by/en/projects/soundkeeper/) on Windows) can help, but only if they send a very quiet noise
  signal: digital zeros still count as silence. Android-based sources such as the Chromecast put their audio output into
  standby after 3 s of silence ([AOSP default](https://gerrit.omnirom.org/plugins/gitiles/android_frameworks_av/+/d58c4738dcbd235e073af8b6e2e83952237d5962%5E%21)),
  which cannot be changed without root.

## Firmware of other JBL models

> [!CAUTION]
> Never flash firmware of another model on the Bar 3.1, and do not try to carry fixes over from it.

- **Bar 9.1:** its update 22.01.31.80 lists "Sometimes there was a 0.5sec audio drop during ARC streaming with PCM format,
  now improved!" ([release notes](https://support.jbl.com/howto/bar-9-1-software-update-release-notes-us/000016600.html)).
  The Bar 9.1 is a completely different platform (MediaTek, Linux), so nothing of that update can be used here.
- **Bar 2.1:** same container format, processor family and DSP configuration, but different hardware. Its V48 firmware
  was used only for comparison.
- **Bar 5.1, Bar Studio and others:** different hardware and firmware.

## How it works

A summary. The addresses, evidence and the commands to check them are in [NOTES.md](NOTES.md).

- **`.HUI` container.** Six parts, each with a 32-bit checksum, plus one checksum for the whole file. Part 0 is the main
  program for the **Sunplus SPHE8202** (MIPS), including the updater. Part 2 is an image of the DSP's own flash chip. The
  others hold the Bluetooth and HDMI firmware and two small programs, probably for the subwoofer link.
- **Part 0** is XOR-scrambled, with the same "mode 3" as Sunplus' own STK tool. It starts with readable code and data,
  followed by compressed (raw DEFLATE) modules. Its header fields, in V49:

  | Field | Value | Meaning |
  |---|---|---|
  | +0x04 | `0xe42d` | build date as a Modified Julian Date (days since 17 Nov 1858): 58413 = **22 Oct 2018** |
  | +0x08 | `0a 1e 12` | build time **18:30:10** (seconds, minutes, hours) |
  | +0x0c | `0x10fb80` | length of the image after the 0x80-byte header |
  | +0x10 | `0xbd159039` | outer checksum: sum of the 16-bit words of the **scrambled** image, from +0x80 to the end |
  | +0xa0, +0xc0 | `0x5a815fca` | inner checksum (stored twice): the same sum over the **unscrambled** image, from +0xd0 to +0x80 + length |

  The Bar 2.1 V48 firmware has the same fields. Its date field, `0xe3e9`, is 15 Aug 2018: the timestamp of the .HUI in
  its ZIP.
- **The tick.**
  - A hardware timer interrupts every 2 ms.
  - The RTOS soft-timer service runs on every interrupt and calls the mute countdown every 5th time.
  - So one tick is 10 ms. The timer registers are decoded with Sunplus' public SDK.
- **Fix A** changes three `addiu a0, zero, 60` instructions to `addiu a0, zero, 10`. It then picks new characters for the
  debug text so that both image checksums stay exactly the same, which keeps the header byte-identical. Finally, it
  recomputes the container checksums.
- **Fix B** rewrites the value after each of the 8 `81000008` commands (DSP OS module, index 8) in part 2 and recomputes
  the container checksums.
- **Fix C** changes the target of one `bne` in the DSP message handler from `NO DATA IN` to the handler's return, then
  keeps the image checksums the same way as fix A and recomputes the container checksums.

## Sources

Firmware:

- JBL Bar 3.1 support page: <https://support.jbl.com/de/de/speakers/speakers-soundbars/JBL+BAR+3.1.html>
- JBL Bar 3.1 download page: <https://id.jbl.com/en/soundbars/JBL+BAR+3.1.html>
- V49 firmware (`firmware/original/`): <https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dwb28afc8e/pdfs/JBL_BAR_3_1_USB_V49.zip>
- Bar 2.1 V48 firmware (same format, used for comparison): <https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw67f81517/pdfs/JBL_BAR_2_1_USB_V48_1.zip>

Sunplus:

- Container format, checksums, UART boot mode (reverse-engineered STK tool): <https://github.com/ArthurKoba/hd-audio-rush-sphe8202r>
- SPHE8202L SDK (timer registers and interrupt bits), pinned to commit `78143e6`: <https://github.com/WGWG58/SPHE8202L/tree/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010>

Chips and service manuals:

- JBL Bar 2.1 service manual (sister model, update procedure): <https://www.manualslib.com/manual/2996357/Harman-Jbl-Bar-2-1.html>
- JBL Bar 5.1 service manual (CS42528, SiI9777): <https://www.manualslib.com/manual/2554069/Harman-Jbl-Bar-5-1.html?page=11>
- Cirrus Logic CS42528 datasheet: <https://statics.cirrus.com/pubs/proDatasheet/CS42528_F2.pdf>
- Cirrus Logic CS4953x4/CS4970x4 System Designer's Guide (silence threshold: §7.6.2): <https://statics.cirrus.com/pubs/manual/CS4953x4_4970x4_System_Designers_Guide_UM6.pdf>
- Cirrus Logic AN123, Stereo PCM application for the CS492X (what the silence threshold does): <https://pdf.datasheet.live/de5f16cf/cirrus.com/AN123.html>

User reports:

- r/appletv, "Audio cuts out after short period of silence", with JBL's 0.6 s statement: <https://www.reddit.com/r/appletv/comments/9cwz0b/audio_cuts_out_after_short_period_of_silence/>
- HiFiVision review (lock-on delay): <https://www.hifivision.com/threads/jbl-bar-3-1-soundbar-review.74970/>
- BT Community, "sound cuts out when there is a period of silence": <https://community.bt.com/t5/Home-setup-Wi-Fi-network/JBL-SOUNDBAR-SOUND-CUTS-OUT-WHEN-THERE-IS-A-PERIOD-OF-SILENCE/td-p/1996115/page/3>
- Update troubleshooting for the Bar 5.1 (USB sticks, AUX cable): <https://www.unixgr.com/jbl-5-1-soundbar-firmware-upgrade/>
- SPI flash recovery on a related model (Bar 2.1 Deep Bass): <https://www.elektroda.pl/rtvforum/topic4179915.html>

## Legal

- **Original firmware:** the files in `firmware/original/` are © Harman International Industries and redistributed
  unmodified. They are publicly available from JBL at the URLs above.
- **Patched firmware:** the files in `firmware/patched/` are modified versions of the original.
- **Removal:** if you are a rights holder and want a file removed, please open an issue.
- **Authorship:** the scripts in `tools/` and the documentation are the work of this project's authors.
- **No warranty:** THIS SOFTWARE AND FIRMWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO
  EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, INCLUDING DAMAGE TO YOUR DEVICE, ARISING FROM
  ITS USE.
