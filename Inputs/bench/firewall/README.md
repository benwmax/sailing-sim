# Windows Firewall prompts on the PC, Nov 24 2026

**Short answer:**
- Development packages always listen on **TCP 1985**, Unreal's trace control port. Windows asks about that port once
  for every new exe path. Shipping packages open no ports, so they never prompt.
- I found no launch argument or ini setting in this engine build that stops the listener.
- I wrote `allow-firewall.ps1` and committed it to a local branch, not pushed. No rule has been added, and nothing that
  already existed was changed.

## 1. Existing rules (read only)

`rules.csv` lists every rule whose program path mentions SailingSim, UnrealEditor or Unreal. No rule mentions
ReadyAbout.

- **89 programs and 178 rules.** Each program has a TCP rule and a UDP rule. Every rule is Inbound, Allow, Enabled,
  and has the Windows default name ("SailingSim", "UnrealEditor", ...). Those are the rules Windows makes when someone
  clicks Allow on the prompt.
- **83 of the programs are the game exe of a package**, `...\SailingSim\Binaries\Win64\SailingSim.exe`:
  - 76 are under `D:\dev\ss-fix\Packaged\...`, one per Dev package folder I made for the benches;
  - the rest are under `D:\dev\ss2`, `ss3`, `ss5`, `ss6`, `D:\dev\sailing-sim` and two older `C:\dev` checkouts.
- **The other programs:** `UnrealEditor.exe`, `UnrealEditor-Cmd.exe`, `UnrealInsights.exe`, `UnrealPak.exe` and
  `UnrealTraceServer.exe`.
- **Profile:** all rules are **Public**, except `D:\dev\ss5`'s pair (Private and Public).
- **This PC's Ethernet ("Network 2") is on the Public profile.** That's why the prompts made Public rules.
  **A Private-only rule would not apply on this network.**
- **No Shipping exe has a rule.**

## 2. What opens the socket

`probe-status.txt` has the full results. Each package was launched with a normal Ultra 1080p 20 s bench, and the
launcher's and game's own PIDs were listed at 15 s and 30 s. Bean's Saved was held aside and restored (7B5CA7BE).

| Run | Listening |
|---|---|
| Dev `Windows-pr825-bcb91c2b` | **TCP 0.0.0.0:1985** (log: "LogTrace: Display: Control listening on port 1985"); no UDP |
| Dev + `-UDPMESSAGING_TRANSPORT_ENABLE=false` | TCP 0.0.0.0:1985 |
| Dev + `-notracethreading -notraceserver` | TCP 0.0.0.0:1985 |
| Shipping `Shipping-76a41ea4` (`-SailingShippingSmoke`) | **nothing** (the game ran its bench; no TCP listener, no UDP endpoint) |

- **UdpMessaging is not the cause.** The plugin is mounted, but in a game it only starts with `-Messaging` or the
  project setting `EnabledByDefault`, and the project sets neither. No UDP endpoint was open in any run.
- **Port 1985 is TraceLog's control listener** (engine `TraceLog/Private/Trace/Control.cpp`). It opens on
  `0.0.0.0:1985`, or a random port from 32768 upward if 1985 is taken, whenever the trace worker updates. It is compiled
  in wherever full trace is on (`TRACE_PRIVATE_ALLOW_TCP_CONTROL`), which includes Development and Test, but not
  Shipping.

## 3. A no-firewall fix

**There isn't one at runtime in this engine build:**
- `Control.cpp` reads no command-line switch;
- `-UDPMESSAGING_TRANSPORT_ENABLE=false`, `-notracethreading` and `-notraceserver` all left the listener open.

The only off switch I know of is compile-time: `UE_TRACE_ALLOW_TCP_CONTROL=0`. On the launcher (installed) engine the
engine modules come prebuilt, so I don't expect a game target can change it. I haven't tried; it would be a `.cs`
build-rules change, which needs Bean's approval anyway.

So there is **no bench or run arg to add**, and I made no change to the scripts' default args.

Nothing actually needs inbound 1985: Insights works from `-tracefile`. **Answering the prompt with Cancel is harmless.**
The game runs the same with the port blocked.

## 4. The script (not run)

`allow-firewall.patch` holds the script. It's commit bb0014a7 on the local branch `pc/allow-firewall` in
`D:\dev\ss-fix-wt\fw`, made from origin/main 6630fe1e. It isn't pushed.

```
scripts\windows\allow-firewall.ps1 <game exe or package folder> [-Profile Private|Public|Domain|Any] [-WhatIf]
```

- **Exe:** it takes the game exe, or finds it in a package folder. It refuses the top-level launcher, which never
  listens.
- **Shipping:** it skips Shipping builds.
- **Existing rules:** it skips an exe that already has an enabled inbound allow rule of any profile.
- **New rule:** otherwise it adds one rule, **"ReadyAbout dev &lt;package folder&gt;"**, Inbound, Allow, for that
  program, with Profile **Private** by default as asked.
- **Elevation:** it stops with a message if the prompt isn't elevated.

`-WhatIf` checks on this PC:
- `Windows-pr825-bcb91c2b`: skipped, since it already has Windows's Public rules.
- `Shipping-76a41ea4`: skipped as Shipping.
- The launcher exe: refused.

Limits:
- **On this network a Private rule does nothing.** The connection is Public, so the rule needs `-Profile Public`, or
  the network set to Private (Bean's setting).
- **Windows rules can't use wildcards in program paths.** Every new package folder is a new path, and the benches make
  a new folder per build, so each one would need its own run of the script. That's one elevated step per package,
  versus one prompt per package now.

**This session is not elevated.** `IsInRole(Administrator)` is False, so it can't add rules.
