# Frame submission console validation

On 2026-11-24, the self-update example title `PPSA99782` validated the
frame-submission change on a PS5 running firmware 6.02. The exact source commit
was `ab33a18`, including the diagnostic frame capture added after the original
frame-submission commit `482bf82`.

The frozen candidate's `eboot.bin` SHA-256 was
`5c9143d35252fac405e090afe059a245ba7288c3f0ded096462d5ea93916ab62`.
The nine installed files matched the candidate after a 130-second settle check.
The title launched through the title-aware controller, ran through frame 120,
and wrote two 1920×1080 PPM captures synchronously from its CPU canvas:

| Frame | SHA-256 |
| --- | --- |
| 30 | `c841a54881d0603bf1ee19761c85213bc27f496271306c012114690e7818aa27` |
| 120 | `40cc78d48a394dd26b2c4c9e9e4f132ef1039e8c686e747a9cdf911859ce0c78` |

Both captures showed the self-update example screen and their rendered frame
counters. The app log reported both captures saved. The kernel log contained
the start and capture lines, and the newest console error record was unchanged
across the run. A title-aware close was followed by ShadowMount's game-stopped
and runtime-layers-released lines. FTP, klog, and elfldr remained reachable.

This confirms continued rendering and clean teardown in this one firmware 6.02
run. It does not exercise a forced transient `sceVideoOutSubmitFlip` refusal on
hardware; the host test covers that path with a controlled submission result.
Raw captures and logs are kept outside the Git repository in the local
protocol results folder.
