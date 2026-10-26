# Research notes: JBL Bar 3.1 firmware V49

The technical details behind the patch, and what the research found along the way. Start with the [README](README.md),
and read its warnings and disclaimer before flashing anything.

Every address below can be checked against the original firmware with the tools in `tools/` (see
[Checking these notes yourself](#checking-these-notes-yourself)). Addresses are virtual addresses as the code sees them.
Offsets are into part 0 unless stated otherwise. "Function `X`" means the function whose entry is at `X`.

Two conventions used throughout:

- **`mute(ticks, source)`** is the bar's mute timer (setter at `0x88028bb0`). *source* identifies the code path that asks
  for the mute, not an audio input: for example 8 = codec monitor (fix A), 9 = `NO DATA IN`, 4 = DSP set-up.
  Audio inputs are called "inputs" here.
- **gp+N** is a firmware variable at offset N from the MIPS global pointer `gp`. The offsets are given as the code uses
  them (`lbu v0, 0x328(gp)`); gp+N is a name for the variable, not an address.

## Contents

- [Container (.HUI)](#container-hui)
- [Part 0: scramble, header, checksums](#part-0-scramble-header-checksums)
- [The mute after a signal change](#the-mute-after-a-signal-change)
- [How long a tick is](#how-long-a-tick-is)
- [The patch (fix A)](#the-patch-fix-a)
- [Verification](#verification)
- [Part 2: the DSP flash image](#part-2-the-dsp-flash-image)
- [Fix B: the DSP silence threshold](#fix-b-the-dsp-silence-threshold)
- [Fix C: ignore the silence report](#fix-c-ignore-the-silence-report)
- [The updater](#the-updater)
- [Hardware](#hardware)
- [The source side](#the-source-side)
- [Firmware of other JBL models](#firmware-of-other-jbl-models)
- [Not verified](#not-verified)
- [Checking these notes yourself](#checking-these-notes-yourself)
- [Sources](#sources)

## Container (.HUI)

`firmware/original/JBLBAR3_1.HUI`, unpacked with `tools/hui.py unpack`:

| Part | Type | Size | Content |
|---|---|---|---|
| 0 | 0 | 0x10fc00 | main program for the Sunplus SPHE8202 (MIPS32 LE), scrambled; includes the updater |
| 1 | 1 | 0x127400 | Bluetooth module OTA image (`OTA`, `2.010.18`, `282A_DVB`), not opened |
| 2 | 3 | 0x27a4c | image of the Cirrus DSP's SPI flash (chip IDs `0x495303`, `0x497003`, ...), see [Part 2](#part-2-the-dsp-flash-image) |
| 3 | 7 | 0x46000 | `SIMG`, SiI9777 HDMI chip firmware |
| 4, 5 | 5, 6 | 0x2000 | two small 8051 programs (header `a5 fa 1f 02`), probably the wireless subwoofer link |

The file header carries the model, `3.1`, at 0x20. Container checksums:

- **Per part:** the u32 LE word sum of the part plus the value stored in its table row is 0.
- **Whole file:** the u32 at 0x14 makes the word sum of the whole file 0 (computed with that slot zeroed).

`tools/hui.py check` verifies both, and `tools/hui.py repack` recomputes them.

## Part 0: scramble, header, checksums

**Scramble:** `plain[i] = raw[i] ^ 0xa5 ^ (i & 0x54)`, where `i` is the offset in the part. The same operation scrambles
again. Part 0 carries the "mode 3" marker `f5f5f5f5` of Sunplus' STK tool at +0x70 (see
[hd-audio-rush-sphe8202r](https://github.com/ArthurKoba/hd-audio-rush-sphe8202r)); the formula itself was worked out from
the data.

**Layout of the unscrambled part 0** (loaded at `0x88006000`):

| Offsets | Content |
|---|---|
| 0x0 to 0x20 | header, not scrambled |
| up to ~0x48000 | code |
| ~0x47000 to 0x50000 | strings |
| from 0x5012c | raw-DEFLATE modules (`zlib.decompressobj(-15)`), each followed by its CRC32 and size (u32 LE) |

The modules mostly follow each other with padding to 4 bytes, but the chain has gaps of unknown data;
`tools/mips.py modules` scans across them and lists the modules whose trailer matches. Most are not MIPS code (probably
microcode and tables). Two are:

| Offset | Size | Loads at | Content |
|---|---|---|---|
| 0xd94a7 | 0x3adc0 | `0x8001cc00` | the resident RTOS |
| 0x1045d8 | 0x147c0 | `0x80093000` | app start-up, periodic callbacks and the [updater](#the-updater) |

The load addresses were found by lining up `jal` targets with function prologues.

**Header and checksums:**

| Offset | Value | Meaning |
|---|---|---|
| +0x04 | `0xe42d` | build date as a Modified Julian Date (days since 1858-11-17): 58413 = 2018-10-22, the file's date |
| +0x08 | `0a 1e 12` | build time 18:30:10 (bytes 2, 1, 0 = hours, minutes, seconds) |
| +0x0c | `0x10fb80` | part size − 0x80 |
| +0x10 | `0xbd159039` | **outer checksum:** u32 sum of the 16-bit LE words of the **scrambled** bytes from +0x80 to the end |
| +0xa0 and +0xc0 | `0x5a815fca` (twice) | **inner checksum:** the same sum over the **unscrambled** bytes from +0xd0 to +0x80 + length |
| +0xc4 | `0x10f8ac` | that length (so the inner sum runs to 0x10f92c) |

The checksum algorithm (u32 sum of 16-bit LE words, an odd last byte ignored) is the one of the Sunplus STK format; the
offsets where this firmware stores the sums differ from the 8203R example in that repository. The rules also hold for a
second official firmware, the JBL Bar 2.1 V48
([`JBL_BAR_2_1_USB_V48_1.zip`](https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw67f81517/pdfs/JBL_BAR_2_1_USB_V48_1.zip)):

- the same container and scramble;
- both checksums match by the same rules (its length is odd; the last byte is not summed);
- its date field is 0xe3e9 = 2018-08-15, the timestamp of the .HUI in its ZIP.

Part 0's own start-up code (`0x880062a0`) never reads this header. Whatever checks it (the boot ROM or a loader) is not
in the update file.

## The mute after a signal change

The codec monitor (function `0x8802b5a0`) calls `mute(60, source 8)` in three places:

| Instruction | When |
|---|---|
| `0x8802b67c` | codec loses lock: log `codec:unlock,mute on` |
| `0x8802b90c` | codec reports digital silence: function `0x8802b344` logs `No Digital Signal Input` and clears gp+0x349, then this site runs if flag gp+0x328 is set |
| `0x8802ba38` | log `Codec detect signal is diffierent` (sic) |

Each is `addiu a0, zero, 0x3c`. The same function also calls `mute(0, source 8)` at `0x8802b94c` and `0x8802b978`.

How `mute(timeout, src)` at `0x88028bb0` works:

- **Counter:** a 16-bit counter at gp+0x329 (`sh`/`lhu`). For every source except 12, the setter at `0x88028b40` runs only
  if `current < new`, so a mute is only ever extended. Source 12 overwrites the counter (`0x88028c2c`).
- **Timeout 0** means "mute until something unmutes explicitly"; it can clear the counter.
- **Countdown:** `0x88028b58` decrements the counter. When it reaches 0, it posts message 0x60002, which unmutes and fades
  the volume back in (`0x8802866c`).

Stock timeouts at the `mute()` call sites:

- 0 (until explicit unmute)
- 1 (source 13, `0x880290c0` and `0x8802910c`)
- 20 (source 13, `0x8802b8cc`: when the signal returns after digital silence, while the first mute is still running)
- 35 to 100 (source 4)
- 50, 250, 300, 1000

The DSP's silence report starts a second, longer chain; see [Fix B](#fix-b-the-dsp-silence-threshold) and
[Fix C](#fix-c-ignore-the-silence-report).

## How long a tick is

**One tick is 10 ms.** Every step below is in the firmware code. The register meanings come from Sunplus' SDK.

1. **Timer init** at `0x880076d8`. The register block is `0xbffe8000` (`regs0` in the SDK; its first register,
   [regmap_8202.h L25](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/regmap_8202.h#L25),
   is commented with that address).
   - `0x8088` is written to offset 0x8c, `stc_divisor`, the system time clock (STC; the SDK sets it up for 90 kHz) ([L62](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/regmap_8202.h#L62)).
   - `0x383` (899) is written to offset 0x98, `rtc_divisor`: RTC = STC / 900 = 100 Hz ([L65](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/regmap_8202.h#L65)).
     The SDK does the same in `init_timer()` ([reset.c L547-L555](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/system/reset.c#L547-L555)).
   - `0x68b3` is written to offset 0xa0, `timer0_ctrl` ([L67](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/regmap_8202.h#L67)).
     With the bit definitions ([L973-L998](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/regmap_8202.h#L973-L998)),
     that is source STC (bit 14), run (bit 13) and go (bit 11), with count `0xb3`: an interrupt every 180 STC counts, i.e. **every 2 ms**.
     For comparison, the SDK's own `TIMER_CONFIG_10ms` is `STC | (900-1)`.
2. **Interrupt:** the dispatcher in part 0 tests bit 0x1000 of the interrupt status at `0x88006910`. That is timer0
   ([intdef.h L39](https://github.com/WGWG58/SPHE8202L/blob/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010/h/intdef.h#L39)).
   It then loads `0x800277fc` into `k1` (`0x88006ad0`) and calls it (`jalr $k1` at `0x88007014`).
3. **OS tick:** `0x800277fc` increments gp+0x5a7 and calls the soft-timer service `0x80028bb0` (from `0x80027824`).
   - That service walks a 10-entry table at `0x80017000`. Each entry is {callback, arg, count, reload}.
   - It decrements each count and calls the callback when the count reaches 0, then reloads it.
   - Not to be confused with `mute()` at `0x88028bb0` in part 0: same low address bits, different image.
4. **Registration:** at start-up, `0x80095198` calls `0x80028c48(&handle, count, reload, callback)` three times:
   - callback `0x800950cc` with period 1;
   - callback **`0x800950f4` with period 5** (count `a1` = 5 at `0x800951f8`, reload `a2` = 5 at `0x800951f0`);
   - callback `0x80095134` with period 50.
5. **Countdown:** callback `0x800950f4` calls `jal 0x88028b58`, the mute countdown, at `0x8009510c`.

So the countdown runs every 5 × 2 ms = **10 ms**. 60 ticks = 0.6 s, 10 ticks = 0.1 s.

Cross-checks:

- **JBL's own figure:** JBL support promised that the V49 update would shorten lock-on "to less than .6 seconds"
  ([Reddit](https://www.reddit.com/r/appletv/comments/9cwz0b/audio_cuts_out_after_short_period_of_silence/)). 60 ticks is
  consistent with that.
- **Other timers fit:** the separate app timer API `0x80022f88` counts in 100 ms units. "BT is reconnect after 100ms" passes
  1 (`0x8800d324`), and "BT into pairing mode after 1s" passes 10 (`0x880226bc`).

Limits:

- **Not measured on the device.** The 90 kHz STC rate comes from the SDK. This board's STC divisor is `0x88`, while the SDK
  uses `150-1`, so the absolute rate depends on the board clock.
- **The 10 ms holds anyway,** as long as the RTC is meant to run at 100 Hz: timer0 and the RTC both derive from the STC
  (STC/180 and STC/900), so one tick is exactly one RTC period.
- **Precision:** the first countdown can come up to one tick after the mute starts, so N ticks last between (N−1)×10 and
  N×10 ms. Interrupt and message latency only add to that.

## The patch (fix A)

`tools/patch.py` sets the three immediates to `TICKS` (10, or the value given on the command line).

The change alters both 16-bit sums of part 0, so the script rewrites a few characters of the debug text
`codec:unlock,mute on`, picked so that both sums come out unchanged. Replacements are printable characters without `%`
or `\`:

1. First it tries 2 letters at even and 2 at odd offsets (meet in the middle). This finds the 10-tick solution.
2. Otherwise it tracks every reachable pair of sum changes over all 20 characters, with the fewest rewrites per pair.

Every value from 1 to 63 builds, with and without fix C. Above 63 there is no solution: the needed sum changes cannot
be reached with printable characters, so `patch.py` refuses those values.

- **Outer sum:** unchanged, so the part 0 header stays byte-identical.
- **Inner sum:** unchanged, so both stored copies stay correct.

`hui.repack` then fixes the container checksums. For 10 ticks the text becomes `-ode/:uolock,mute on` (3 characters
change), and 8 bytes of the file change. With 60 ticks, the output is identical to the original.

> [!WARNING]
> Only flash a `.HUI` whose SHA-256 matches [SHA256SUMS](SHA256SUMS), or one you built yourself with `tools/patch.py`.

## Verification

For fixes A and C, on the files in this repository:

**Files:**

- The ZIP is byte-identical to JBL's download (SHA-256 `a0b98984…3e96dd`). Its `.HUI` is identical to
  `firmware/original/JBLBAR3_1.HUI`.
- Changed bytes: part 0's table checksum, the three immediates and the log text, and for `fix-A+C` also the branch at
  `0x880275a4`. Nothing else changed: not the header, not
  the DEFLATE modules (so their CRC32s still match), not parts 1 to 5. The file checksum at 0x14 stays the same because
  the part checksum absorbs the change.
- `tools/selftest.py` rebuilds the five builds listed in the README's [Choosing the fixes](README.md#choosing-the-fixes)
  and the stock build against known hashes, and checks that bad input is refused. Each check was shown to fail when the
  code it covers is deliberately broken (23 such changes, all caught).

**Safety of the code change:**

- **Delay slots:** two of the patched instructions (`0x8802b67c`, `0x8802ba38`) sit in branch delay slots, so they also
  run when the branch is taken. On those taken paths `a0` is not used: the next callees (`0x8802b4c4`, `0x88023b18`)
  ignore it. The third (`0x8802b90c`) is on the straight path that goes on to call `mute()`.
- **The rewritten log text** has one reference: it is loaded at `0x8802b694` and passed as the printf format at
  `0x8802b698`. No `lui`/`addiu` pair in part 0's code points into it, and the new text contains no `%`.
- **No side effects on other mutes:** `mute()` only extends the counter for source 8, so the shorter value cannot cut short
  a longer mute from another source.

**On the device** (one unit, Chromecast through the TV over HDMI ARC):

- The update was accepted and the soundbar works.
- Pause/resume still clicks. The stock firmware clicks too, only later and less noticeably.
- Fix A + C (10 and 20 ticks): sound is back at once after a pause and the display no longer shows "PCM"; the
  20-tick build pops much less. Details and what is still unchecked: README,
  [Experience so far](README.md#experience-so-far).

## Part 2: the DSP flash image

Part 2 is a byte-for-byte image of the DSP's own SPI flash: flash address = offset in part 2. Words are big-endian. The
DSP boots from that flash by itself; the main program never sends it code.

| Offset | Content |
|---|---|
| 0x00000 to 0x0296c | boot program |
| 0x0296c to 0x10000 | zero padding |
| 0x10000 | configuration database: magic `aa4b73e1`, end offset `0x27a48`, table pointers |
| 0x10074 | name `3121`; the main program reads 2 bytes at 0x10076 at start-up (`0x88025174`, called from `0x80095b98`) |
| 0x10088 to 0x1072c | 5 INIT configuration blocks, table at 0x1072c |
| 0x1076c to 0x1fbac | decoder programs and their configuration blocks, table at 0x1fbac |
| 0x1fbac to 0x27a4c | further tables and coefficient sets; trailing magic `aa4b73e1` at 0x27a48 |

- **Programs** consist of records `[header, count, count words]` and end with `ffffffff` plus a checksum word. The u32 sum
  of all words from the start through the checksum is 0. This holds for exactly 9 programs (at 0x0, 0x1076c, 0x11ca0,
  0x1248c, 0x12c5c, 0x131e8, 0x14d50, 0x14dec, 0x1ddf0).
- **Configuration blocks** are `[n, n words of command/value pairs]`. No checksum was found for them: no 32-bit sum, XOR or
  CRC32 of a block or of the whole database occurs in part 2 (16-bit values only at chance level).
- **Boot:** `0x88025d58` tries up to twice. Each try (`0x88025b44`) pulses the DSP reset and waits for the message
  `ef000020 00000001`, which the Cirrus guide calls "Flash image verified". It prints `DSP Boot Succeed` or
  `DSP Boot failed`; the callers (`0x88026b78`, `0x88026bac`) ignore the result. The DSP is reset this way at input and
  stream changes.

## Fix B: the DSP silence threshold

**The chain fix B is meant to remove:**

1. During PCM playback, after `PCM_AUTODETECT_SILENCE_THRESHOLD` samples of digital silence, the DSP sends autodetect code
   `0x0020`, "Silent Input Data (Out of Application Sync)" (Cirrus guide, Table 7-1). V49 sets the threshold to 48,000.
   The UM6 guide counts left + right samples (its default 0x17700 = 96,000 "allows for 1sec" at 48 kHz), which makes
   48,000 half a second; the older AN123 calls 48,000 "1 Second at 48 KHz". So it is 0.5 or 1 s.
2. The autodetect handler (function `0x88027410`) sends code `0x00` to `NO DATA IN` at `0x8802749c` on purpose
   (`beqz` at `0x8802748c`); codes without a case of their own end up there too: `0x20` through the `bne` at
   `0x880275a4` (fix C), `0x40` through the one at `0x88027578`.
   `NO DATA IN` clears the stream type (`0x88029cec(0)`) and calls `mute(0, source 9)`. On HDMI inputs that is a hard
   mute; on the others the volume ramps to 0. `mute(0, 9)` is also called at `0x880231dc` and `0x88027c58`.
3. The stream-change handler (function `0x88027ab4`) then clears its stream cache. When sound returns, the DSP is set up
   again: the set-up first mutes for 55 ticks (`0x88029a10`, source 4), state 7 waits 30 ticks (`0x88029ab4`), and the
   stream-done mute is lip-sync/10 + 5 ticks (`0x880297e8`), or lip-sync/10 + 50 ticks on HDMI inputs (`0x88029824`).
   The display shows "PCM" again.

**The change:** the value after each `81000008` command (DSP OS module, index 8: write command `0x8100HHHH 0xhhhhhhhh`,
guide §7.6.2) is rewritten. There are exactly 8, all in configuration blocks:

| Value word at (part 2) | Block |
|---|---|
| 0x10148, 0x103c0 | INIT 2, INIT 0 |
| 0x11ab0, 0x11b6c | decoder 1 (PCM), configurations 0 and 1 |
| 0x11f84, 0x12100, 0x1227c, 0x123f8 | decoder 2 (Dolby Digital), configurations 0 to 3 |

All 8 change, because every block writes the setting again when it loads. Each sits in the same run of OS writes
(`81000002`, `03`, `05`, `06`, `08`, `0a`, `0b`). Only the container checksums change on top. `patch.py` refuses to run
unless `81000008` occurs exactly at these 8 places with the stock value.

**Threshold 0: tested, no audio.** The Cirrus System Designer's Guide (DS810UM6, §7.6.2, Table 7-7, p. 7-17) says:
"Number of samples (Left+Right) of silence upon which the DSP will declare Silence while having detected and currently
playing PCM (Autodetect is enabled). [...] This is a value that should be set to non-zero if the input source is a CD,
but set to zero at all other times in order to prevent audio popping noise." On the Bar 3.1, 0 made the bar show "PCM"
and play nothing. The most likely reading: with 0 the DSP declares silence at once, and the main program's `NO DATA IN`
mute (step 2) never ends. Flashing fix A again restored the sound.

**What the threshold does,** from Cirrus' older AN123 (CS492X family, the same variable name and the same `0x0020`
message): "if the silence is more than PCM_Autodetect_Silence_Threshold [...] the CS492X jumps to a Silent Input Data
state, and the output is muted [...] waiting to autodetect the input once non-silent data appears." It is only a
comparison with a sample count. AN123 also says the host should take no action on that message; JBL's firmware mutes.

**Large values.** No document gives a range, a "disable" value or special values. The table only says "Bit [31:0]", and
index 0x0008 is marked runtime-writable for DSP A. If the DSP compares the value as a signed number, anything from
0x80000000 up would be negative, so `patch.py` accepts 1 to `0x7fffffff` (about 6 to 12 hours of silence at 48 kHz).
Every Cirrus DSP image that could be checked ships 48,000:

| Product | Firmware | `81000008` values |
|---|---|---|
| JBL Bar 3.1 | V49 | `0xbb80` × 8 |
| JBL Bar 2.1 | V48 | `0xbb80` × 8, at the same offsets |
| JBL Bar 5.1 | 17.07 (`unify.bin`) | `0xbb80` × 2 |

So no shipped product shows that a large value works. Untested on hardware.

**What else depends on the silence report** (main program, RTOS and app module searched):

| What | Depends on silence? |
|---|---|
| Auto standby (`0x8802a198`, about 10 min: period 2 × 100 ms at `0x8802a238`, count 3000 at `0x8802a284`) | no: codec lock and signal flags, input GPIOs, HDMI +5 V |
| Codec lock/unlock mute (fix A) | no: codec registers |
| "DSP dead" watchdog (`0x8802983c`) | no: DSP tick and HDMI clock |
| Flag `0x80017f98`, which blocks timed unmutes | set only on the `mute(0, 9)` path; cleared when a new stream type arrives (`0x88027dd0`) |
| Display "PCM"/"DOLBY" | shown again on each re-detection |

**Open questions:** what the DSP sends when the input clock stops completely (in every case the codec monitor also sees
the unlock and mutes for the fix A time); whether a PCM → Dolby/DTS switch without a pause is still detected with a large
threshold (the bar resets the DSP on format changes reported by the codec, so it probably is); whether there is audible
hiss during long silences on HDMI inputs.

## Fix C: ignore the silence report

Fix C leaves the DSP alone and changes what the main program does with code `0x20` (step 2 of the chain above).

**The dispatch.** The autodetect handler (function `0x88027410`) reads the code into `s0` and narrows it down with
`slti` comparisons. Codes `0x0e` to `0x20` reach `0x88027564`, where `0x15` has its own case. `0x16` to `0x20` then
branch to `0x880275a4` (`beqz` at `0x8802756c`), with `v0 = 0x16` set in its delay slot (`0x88027570`):

| Address | Stock | Fix C |
|---|---|---|
| `0x880275a4` | `bne s0, v0, 0x8802749c` (`0x1602ffbd`): anything but `0x16` → `NO DATA IN` | `bne s0, v0, 0x88027430` (`0x1602ffa2`): anything but `0x16` → return |

- `0x16` (Dolby TrueHD in Table 7-1 of the Cirrus guide) still falls through to its case at `0x880275ac`.
- `0x17` to `0x20` now return without doing anything. Of these, Table 7-1 documents only `0x1c` (AAC, which the bar has
  no decoder for) and `0x20` (Silent Input Data).
- `0x88027430` is the handler's own epilogue (`lw ra`, `lw s0`, `jr ra`, `addiu sp, sp, 0x18`), where the other
  cases end too (for example `j 0x88027430` at `0x88027524`). The stack frame is the same at both places: `sp` changes
  only at `0x88027410` and `0x8802743c`.
- Code `0x00` still goes to `NO DATA IN` (`beqz` at `0x8802748c`), and so does every code that reaches it through
  another branch (for example `0x88027578`, `0x8802768c`, `0x880277a8`) or falls through from `0x88027494` (codes 2 to
  `0x0a`).

**What it gains.** On `0x20`, the bar no longer calls `0x88029cec(0)` and `mute(0, source 9)`, so the stream type
(`0x80017fa0`) keeps its value and flag `0x80017f98` is not set. The DSP still detects the silence and sends the report
(the threshold is unchanged); it picks up the input again by itself when sound returns. When it reports the stream
again, the stream-change handler compares the new type with its cache (`0x88027b9c`, `beq` at `0x88027bac` to
`0x88027e84`), finds it unchanged and skips the set-up of step 3 (0.55 s or more). That path was not traced to its end
in the code, but the first tests on one unit (fix A + C, Chromecast) match it: sound is back at once after a pause,
and the display no longer shows "PCM".

**What still sets the DSP up again.** The full set-up is DSP state 1 (`HH:AUDIO_FRAME_CHG_PREPROCESS`, `0x880299b0`:
the 55-tick mute, then state 2). State 2 (`0x88029488`, jump table at `0x88051334`) boots the DSP for the S/PDIF or
HDMI input (`0x88026b78`, `0x88026bac`) and resets both the stream type (`0x88029f98`) and the cache (`0x88026e6c`) to
`0xff`, so the next report is always treated as new. State 1 is set through `0x88029434(2, 1)` from:

| Caller | When |
|---|---|
| `0x8802378c`, `0x88023998` | input switch: functions `0x880236b0` and `0x880238a4` write the new input to `0x80017e10`; the first is called from the key handler (`0x88022e2c`, `sorce switch in`) |
| `0x88027e4c` | stream-change handler: a stream type that differs from the cache (PCM ↔ Dolby/DTS) |
| `0x8802b958` | codec monitor: if the DSP state machine is idle (state 0, read by `0x8802830c`) and the current input (`0x80017e10`) is not input 1, it calls `mute(0, 8)` and starts a set-up; the trigger was not traced further |
| `0x880273c0` | DSP API message handler (`stream_sample_rate`, `input_sample_rate` logs), under a condition not traced |

None of them goes through `0x880275a4`, so fix C leaves them as they are. Only the DSP's own silence report no longer
starts a set-up.

**Risks** (not checked yet):

- The DSP itself mutes its output in the Silent Input Data state (AN123) and detects the input again. If it also reloads
  its configuration, settings the main program sent (volume, EQ, sound mode) might be lost until the next input change.
- If the DSP reports a pulled cable or a source that was switched off as `0x20` and the codec does not see it, the bar
  no longer mutes for it. When the input clock stops, the codec monitor sees the unlock and mutes anyway (fix A path).
- AAC (`0x1c`) no longer mutes. Unknown codes `0x17` to `0x1f` are ignored instead of muting.
- Like fix A, fix C changes part 0, which holds the updater. A part 0 that does not start cannot be fixed with a USB
  stick. The changed branch only matters when the DSP sends one of these codes.

`patch.py` checks the stock word at `0x880275a4` on every build and refuses to run if it differs. The checksums
are kept as for fix A, for both changes together in one pass. With 60 ticks the text becomes `ea}sc:unlock,mute on`
(9 bytes of the file change); with 10 ticks, `}ode}:un}o}k~mute on` (11 bytes); with 20 ticks (the prebuilt
`fix-A+C`), `so}e{:unlock~mute on` (10 bytes).

## The updater

The updater is in the app module (`0x80093000`), not in the readable part of part 0, which is why a string search of
part 0 alone finds nothing.

- **Entry:** the RTOS (`0x8003272c`) scans the USB stick in update mode (`UPDATE MODE`); `0x800a23a4` looks for
  `JBLBAR3_1.HUI` (string at `0x800a1f00`).
- **Checks** (function `0x800a3240`): the model at file offset 0x20 must be `3.1`, otherwise `rom bin error`. Each part's
  checksum is verified (`upgrade_HUI_checksum`, `0x800a2f54`) by reading the whole part before anything is erased. No
  version comparison was found.
- **What it writes:** `upg_mask_flag` gets a bit for every part in the table, so every part is written on every update.
  The parts are processed from the last one down to part 0, so the DSP flash is written before the main program.
- **DSP flash** (`Upgrade DSP Flash!`, function `0x800a2db8`): the main program drives the DSP's flash chip itself over a
  software SPI (`0x88024850` to `0x88025174`). It writes a marker at flash address 0xfffff (`0x800a3174`), erases blocks
  0 to 14 (15 × 64 KB, 0x00000 to 0xeffff; `0x88024d6c(0xd8, 0, 14)` at `0x800a2e5c`, end index inclusive) and programs
  the part page by page, with no read-back.
- **Interrupted update:** after a reset the marker is erased, but the update does not resume. The DSP is then without
  firmware (no sound) until the next update.
- **Display texts:** `FAIL`, `DONE` and `ERROR` (`0x800a214c`, `0x800a2154`, `0x800a215c`), chosen in `0x800a2e80`.

Not traced: where Volume Down + Power sets the update mode.

## Hardware

Taken from firmware strings and the service manuals of sibling models; not confirmed by opening a Bar 3.1.

| Part | Chip | Evidence |
|---|---|---|
| Main processor | Sunplus SPHE8202 | string `8202VG 1.0.0` |
| Codec / S/PDIF receiver | Cirrus CS42528 | `x_Cs42528_Init` |
| HDMI | SiI9777 | `Sii9777...` functions, part 3 |
| Bluetooth module | made by TCL | `TCLBT`, `TCLRCP` |
| DSP | Cirrus CS4953x4 or CS4970x4 | chip IDs in part 2 |
| DSP flash | 1 MB SPI flash | the flash driver refuses addresses above 0xfffff (`0x88024e40`, `Addr overtop`) |

From the datasheets:

- **CS42528** ([DS586F2](https://statics.cirrus.com/pubs/proDatasheet/CS42528_F2.pdf)):
  - It specifies no lock time. Non-audio data "originating from AC-3 or MPEG encoders" passes through like PCM: "It is up
    to the user to mute the outputs as required" (§9.3.1).
  - It has its own silence detection: a "Digital Silence" flag after 1548 consecutive zeros (§6.9.1), and an automatic
    mute of its own DAC outputs after 8192 samples of static 0 or −1 (AMUTE, §6.11.3). Whether the bar uses those DACs
    or the flag for muting was not traced; either way, keep-alive signals have to be noise, not digital zeros.
- **Cirrus DSP guide:** "In the event of an input stream change affecting the clocks, Cirrus Logic recommends holding the
  [...] DSP in Reset until the clocks are stable" (§6.1.2.1).
- **What that means for 10 ticks:** a Dolby frame lasts 32 ms at 48 kHz, so 0.1 s is short for PCM ↔ Dolby/DTS switches.

**Recovery** from an unusable soundbar is untested on the Bar 3.1. There are two known routes:

- The Sunplus UART boot mode: hold `VFD_CLK` low at power-up, with UART1 on `V_H_SYNC`/`V_V_SYNC` at 3.3 V
  ([hd-audio-rush-sphe8202r](https://github.com/ArthurKoba/hd-audio-rush-sphe8202r), `docs/hardware.md`, for an 8203R
  board).
- Reprogramming the SPI flash directly with a programmer.

Both are far easier with a flash dump made before flashing anything. A bad DSP configuration does not need either: the
updater lives in part 0, and a USB update rewrites the DSP flash (tested once, after fix B with threshold 0).

## The source side

What the source does matters as much as the bar:

- **TV set to PCM output:** removes format changes, not silence. The author's TV already outputs PCM with 0 delay.
- **Chromecast / Android TV:** Android's AudioFlinger puts the output into standby after 3 s with nothing playing
  (AOSP default `kDefaultStandbyTimeInNsecs = seconds(3)`, property `ro.audio.flinger_standbytime_ms`;
  [AOSP change](https://gerrit.omnirom.org/plugins/gitiles/android_frameworks_av/+/d58c4738dcbd235e073af8b6e2e83952237d5962%5E%21)).
  The stream then stops, which the bar sees as a codec unlock (fix A territory). It cannot be changed without root. The
  "Surround sound: Manual" setting ([Google](https://support.google.com/chromecast/answer/10110321)) only changes which
  formats are offered, so stereo and menu sounds stay PCM.
- **Keep-alive signals:** Kodi's "Keep audio device alive" ([Kodi wiki](https://kodi.wiki/view/Settings/System/Audio);
  mixed results in the [Kodi forum](https://forum.kodi.tv/printthread.php?tid=205205) and
  [OSMC forum](https://discourse.osmc.tv/t/sound-delay-after-pause/75112)) and
  [Sound Keeper](https://veg.by/en/projects/soundkeeper/) on Windows
  ([discussion](https://www.elevenforum.com/t/fixing-delay-when-starting-audio-over-hdmi.8715/)). They help only with
  non-zero noise: digital zeros trigger the DSP threshold and the CS42528's silence detection all the same. No such app
  was found for Android TV.

## Firmware of other JBL models

None of it can be used on the Bar 3.1, and none of it may be flashed on it.

- **Bar 9.1:** the update 22.01.31.80 lists "Sometimes there was a 0.5sec audio drop during ARC streaming with PCM format,
  now improved!" ([release notes](https://support.jbl.com/howto/bar-9-1-software-update-release-notes-us/000016600.html);
  download link in [this PDF](https://www.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dwce241e44/pdfs/Firmware%20Update%20JBL%20Bar%209.1%20TWS%20version%2022.01.31.80.pdf)).
  The Bar 9.1 runs Linux on a MediaTek 8531 (firmware `JBL_BAR_9_1.bin`, UBI images); 21.13.11.80, from before the fix,
  was looked at. Nothing carries over to the Sunplus/Cirrus platform.
- **Bar 2.1 (V48):** same container, scramble and checksum rules, and the same DSP configuration layout and threshold.
  Different hardware. Used only for comparison.
- **Bar 5.1 (17.07):** a different update format (`unify.bin`), same Cirrus DSP family and threshold.
- **Bar Studio and others:** different hardware and firmware.

## Not verified

Claims that rest on a single source or on reading the code, not on a test:

- The JBL support quote and the user reports come from the cited threads; they were not re-checked for this release.
- "Hergestellt von 2018 bis 2020" was read on JBL's support page by hand; the page blocks scripted access.
- The Bar 2.1 and Bar 5.1 service manuals (manualslib) were not re-read for the hardware table.
- The Bar 9.1 version attribution comes from search results of JBL's release-notes page, which blocks scripted access.
- Which inputs auto standby watches, the hard mute on HDMI inputs, and the "DSP dead" watchdog: read from the code, not
  traced in every detail.
- Where the debug text is printed (the printf at `0x800a69a0` was not followed).
- Fix B with a non-zero threshold: never run on a soundbar. Fix C: tested on one unit, together with fix A at 10 and 20
  ticks.
- Fix C: the stream-change handler's cache path after a silence report that the bar ignored (the test matches it), and
  whether the DSP keeps its configuration through the Silent Input Data state (not checked on the device yet).

## Checking these notes yourself

```sh
uv run tools/selftest.py                                      # builds and refusals, a few seconds
uv run tools/hui.py check firmware/original/JBLBAR3_1.HUI     # container checksums
uv run tools/mips.py find "codec:unlock,mute on"              # the log text and its only reference
uv run tools/mips.py dis 0x8802b678 3                         # a patch site (in the original)
uv run tools/mips.py dis 0x880076d8 10                        # timer init
uv run tools/mips.py dis 0x88006904 6                         # interrupt dispatch (timer0 = bit 0x1000)
uv run tools/mips.py dis 0x88006ad0 3                         # loads the OS tick 0x800277fc
uv run tools/mips.py dis 0x800277fc 12                        # OS tick -> soft-timer service
uv run tools/mips.py dis 0x80028bb0 30                        # soft-timer service
uv run tools/mips.py dis 0x80095198 40                        # registrations: periods 1, 5, 50
uv run tools/mips.py dis 0x800950f4 8                         # calls the mute countdown 0x88028b58
uv run tools/mips.py dis 0x88028b40 30                        # mute counter setter and countdown
uv run tools/mips.py dis 0x8802748c 1                         # autodetect: code 0 -> NO DATA IN
uv run tools/mips.py dis 0x88027564 4                         # autodetect: 0x16..0x20 -> 0x880275a4
uv run tools/mips.py dis 0x880275a4 3                         # autodetect: 0x17..0x20 -> NO DATA IN (fix C changes it)
uv run tools/mips.py dis 0x88027430 4                         # autodetect: the handler's return (fix C target)
uv run tools/mips.py dis 0x88029488 34                        # DSP state 2: input set-up, resets stream type and cache
uv run tools/mips.py dis 0x800a2e50 5                         # updater: erase of the DSP flash
uv run tools/mips.py modules                                  # DEFLATE modules whose CRC32 matches
```

To check a patched file against the original: `cmp -l firmware/original/JBLBAR3_1.HUI
firmware/patched/fix-A/JBLBAR3_1.HUI` lists the 8 changed bytes (10 for `fix-A+C`).
`uv run tools/patch.py firmware/original/JBLBAR3_1.HUI build/fix-A/JBLBAR3_1.HUI` rebuilds the fix A file, and the same
with `20 --ignore-silence` the fix A + C file; each must be byte-identical.

## Sources

Firmware and JBL:

- JBL Bar 3.1 V49 firmware: <https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dwb28afc8e/pdfs/JBL_BAR_3_1_USB_V49.zip>
- JBL Bar 2.1 V48 firmware: <https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw67f81517/pdfs/JBL_BAR_2_1_USB_V48_1.zip>
- JBL Bar 5.1 17.07 firmware: <https://harman.widen.net/content/snlwipexqe/original/Firmware_update-JBL_Bar_5.1_Version_17.07.zip?u=nbo9ks&download=true>
- JBL Bar 9.1 release notes: <https://support.jbl.com/howto/bar-9-1-software-update-release-notes-us/000016600.html>
- JBL Bar 2.1 service manual: <https://www.manualslib.com/manual/2996357/Harman-Jbl-Bar-2-1.html>
- JBL Bar 5.1 service manual: <https://www.manualslib.com/manual/2554069/Harman-Jbl-Bar-5-1.html?page=11>
- JBL support's 0.6 s statement: <https://www.reddit.com/r/appletv/comments/9cwz0b/audio_cuts_out_after_short_period_of_silence/>

Sunplus:

- STK container format, UART boot mode (reverse-engineered): <https://github.com/ArthurKoba/hd-audio-rush-sphe8202r>
- SPHE8202L SDK, at commit `78143e6`: <https://github.com/WGWG58/SPHE8202L/tree/78143e63d9b66b0ba1c5c83dd1cc13c2f173a010>

Cirrus Logic:

- CS4953x4/CS4970x4 System Designer's Guide, DS810UM6 (Table 7-1 autodetect messages, §7.6.2 OS module, §6.1.2.1): <https://statics.cirrus.com/pubs/manual/CS4953x4_4970x4_System_Designers_Guide_UM6.pdf>
- AN123, Stereo PCM Application User's Guide for the CS492X Family (silence threshold behaviour): <https://pdf.datasheet.live/de5f16cf/cirrus.com/AN123.html>
- CS42528 datasheet, DS586F2: <https://statics.cirrus.com/pubs/proDatasheet/CS42528_F2.pdf>

Source side:

- AOSP AudioFlinger standby time: <https://gerrit.omnirom.org/plugins/gitiles/android_frameworks_av/+/d58c4738dcbd235e073af8b6e2e83952237d5962%5E%21>
- Chromecast surround sound settings: <https://support.google.com/chromecast/answer/10110321>
- Kodi audio settings: <https://kodi.wiki/view/Settings/System/Audio>
- Sound Keeper: <https://veg.by/en/projects/soundkeeper/>
