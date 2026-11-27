# Selma° Home 0.4.0

Rootless native Home launcher for Android 10+ (min API 29, target 35). Android runs the kernel, drivers, radio, permission manager and app lifecycle throughout.

## Install or switch back

Open the preview APK in Android's file manager and approve installation. Launch Selma° Home normally first. Use Start to launch apps or Studio. Open Control Panel and tap Default Home app and select Selma to use it as Home. Select the previous launcher in the same chooser to revert. Android Settings > Apps > Default apps > Home app is the independent recovery route (OEM wording varies).

## Local intelligence and updates

Both model and tokenizer are bundled. The CPU decoder runs karpathy/tinyllamas stories260K, a 260K-parameter English story-completion model. The last prompt and result persist locally. Start keeps recent launches and manually pinned apps. Clearing app data clears both.

Import compatible model accepts a legacy llama2.c checkpoint with the same 64-dimensional, five-layer, 8-head/4-KV-head architecture, 512-token vocabulary, tied weights and identical tokenizer. The importer checks size, layout and numerical bounds, then runs local generation before selecting it. Restore previous model reverses the last upgrade. Model imports and app ordering do not retrain weights. Executable upgrades use owner-signed APKs.

## MCP

Tap Start MCP. Use the endpoint and bearer credential shown with a native local MCP client supporting Streamable HTTP. Use POST, JSON-RPC 2.0, protocol version 2025-06-18, with no Origin header. The endpoint offers initialize, ping, tools/list and tools/call with story_complete and a string prompt. Use split screen or a background client so Home stays visible. Leaving Home stops the server and invalidates the token. Network permission enables the localhost socket.

## Phone-only build

Save SelmaHome-0.4.0-source.zip in Downloads. In native Termux paste the following command and approve shared-storage access if requested. The first build retrieves dependencies and verifies the platform jar. Model assets are included.

```bash
(pkg install -y unzip && { [ -L "$HOME/storage/downloads" ] || termux-setup-storage; } && for i in $(seq 1 90); do [ -r "$HOME/storage/downloads/SelmaHome-0.4.0-source.zip" ] && break; sleep 1; done && dir=$(mktemp -d "$HOME/selma-build.XXXXXX") && unzip -q "$HOME/storage/downloads/SelmaHome-0.4.0-source.zip" -d "$dir" && bash "$dir/build-phone.sh")
```

Output is Downloads/SelmaHome-owner.apk. Preserve the private signing directory at ~/.local/share/selma-home/signing for future updates. The preview and owner edition use different package IDs and can coexist.

## Verification

Verified Android SDK Platform 35 compilation, DEX packaging, APK Signature Scheme v3, manifest, archive integrity and model digests. JVM inference for “Once upon a time” matched the upstream llama2.c greedy decoder over 36 generated tokens. Exercised MCP authentication, initialization, discovery, tool inference and unknown-method handling over a loopback socket. Checkpoint staging rejected truncation and accepted the full file. Tests are in `tests/Probe.java`. `build-host.sh` produces the canonical owner APK when given Android SDK Platform 35, Android Build Tools 35 and owner signing variables. Handset install, Home recovery, Android persistence, model rollback UI, Termux build and sustained use remain unverified.

Model: https://huggingface.co/karpathy/tinyllamas/tree/main/stories260K

Reference implementation: https://github.com/karpathy/llama2.c

## Desktop and Workbench

Start opens pinned tools, recent launches, search and All apps. Long-press an installed app to pin it or inspect its Android app info. Drag a Selma window by its title. The title bar and overflow menu provide minimize, maximize, restore, close and left/right snap. External apps use Android's task manager. The taskbar star opens live Creative Mode. Tap effects cover the activity surface. Separate Android dialogs and external apps own their input.

Workbench creates an independent Python inventory project inside a folder approved in Android's picker. The files are read back after creation. Run its check.sh in a Python 3.9+ environment. Choose project folder separately to authorize read-only reviews. The reviewer inventories source/build/workflow files and reports TODO, FIXME and saved focus-keyword matches. The daily job runs when Android schedules it. Review status and reports are available through Refresh run report. This release does not submit applications or perform contract work on LinkedIn.

The desktop opens with a solid slate background and shortcuts for Applications, Workbench, MCP tools and Studio. The screensaver is black. Creative Mode supports a personal still image.

The Termux build installs the reversible lunar theme. Open a new Bash session to see the prompt. To restore your prior palette and remove the prompt hook, run:

`bash "$HOME/.local/share/selma-lunar/theme.sh" remove`

On-device animation, installation, storage providers and scheduled runs still require handset validation.

Version 0.3 adds review_run, review_status and review_report to the local MCP server. Each accepts an empty arguments object. Select the source folder in Workbench before requesting a run. The report contains the latest completed scan.
