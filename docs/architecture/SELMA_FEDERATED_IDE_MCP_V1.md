# Selma federated IDE, MCP, and repository-vault architecture v1

Observed: 2026-09-22  
Canonical repository: `Spiritjcrow/Selma.0`  
Status: architecture/integration slice; no credential material is stored here.

## Goal

Give Selma one governed development fabric across ChatGPT/Codex, Android-native IDEs, local terminals, and repository providers without creating a second command executor or bypassing the Gate 1 permission/audit path.

The rule is **one control plane, many adapters**.

External systems may provide editing, build, repository, model, or deployment capabilities, but they do not grant Selma authority by themselves. Any effect that reaches device, filesystem mutation, network, process, notification, deployment, or repository write operations must remain scoped, revocable, auditable, and attributable to the authenticated user/provider session.

## Current repository material to preserve and port

The following branches contain useful work but are not current-main authority:

| Branch / PR | Useful material | Disposition |
|---|---|---|
| `codex/avatar-pack-verification-v1` / PR #21 | bounded signed avatar-pack reader and schema | retargeted to current `main`; validate before merge |
| `codex/avatar-state-controller-v1` / PR #22 | ordered avatar state/events, barge-in, kill switch | retargeted to current `main`; validate before merge |
| `codex/avatar-ed25519-verifier-v1` / PR #27 | production Ed25519 verification boundary | keep stacked on PR #21 until pack base is accepted |
| `selma-plugin-adapters-v1` | GitHub adapter and plugin-adapter registry concepts | port through Gate 1 network/process contracts; do not merge stale branch |
| `agent/selma0-android-native-port-v1` | Kotlin shell, loopback policy, foreground service, overlay, llama lifecycle | port bounded pieces onto current Android-native tree |
| `selma-data-compiler-v1` | catalog, provenance, merge, delegation, policy, sandbox, Forge concepts | port after constraining effects to the existing control plane |

## Federated development surfaces

### ChatGPT and Codex

OpenAI's plugin architecture can package skills, MCP servers, and optional lifecycle hooks. Codex also exposes IDE and CLI surfaces, and the CLI can connect to local or remote MCP servers.

Use this layer for:
- repository-scoped inspection and editing;
- repeatable Selma build/review skills;
- MCP connections to external repository and development systems;
- human-visible diffs, tests, and audit evidence.

Do not use plugin installation as blanket permission. Provider authentication and Selma's own capability policy remain separate gates.

### Android Studio

Android Studio Agent Mode supports multi-file agent work and remote MCP servers. Current Android Studio documentation includes GitLab as a remote MCP example and supports project-level agent permissions and sandboxing.

Android Studio can also use a local model provider such as Ollama or LM Studio. This aligns with Selma's offline-first path: a local tool-capable model can assist with code while repository and device actions remain governed separately.

Use Android Studio as the primary **real Android-native execution surface** for:
- Gradle and Android SDK builds;
- Kotlin/Compose implementation;
- emulator/device testing;
- logcat, runtime permissions, packaging, and APK evidence;
- MCP-backed repository operations when the provider is authenticated.

### JetBrains / Junie

Junie has first-class Android development support in Android Studio and IntelliJ IDEA with Android tooling. It can work through the IDE, emulator/connected device, and MCP servers.

Treat Junie as an optional IDE agent, not as Selma's governance kernel. Any generated changes must land in the same branch/review/evidence workflow.

### GitLab

GitLab now provides:
- a beta OpenAI integration for ChatGPT and Codex;
- a remote GitLab MCP server;
- repository/project/merge-request/pipeline tools through MCP;
- a free Web IDE for browser editing;
- paid Workspaces for full remote runtime environments;
- GitLab Duo Agent Platform for broader agentic SDLC orchestration.

The GitLab Web IDE is useful for multi-file repository editing but does **not** provide a native runtime for compilation/tests. Android builds therefore require CI runners, a local/remote Android toolchain, or a full workspace/runner environment.

GitLab is the preferred secondary repository/provider target for Selma because it can expose the repository through both Codex and Android Studio using the same MCP boundary.

### Codeberg / Forgejo

Codeberg is a viable independent repository mirror/fallback. It supports Forgejo Actions with self-hosted runners and Woodpecker CI. Hosted CI has resource/onboarding limitations.

Use it as:
- a continuity mirror;
- an independent source-control vault;
- a self-hosted-runner target where Android/Linux build capacity is supplied by owned infrastructure.

Do not assume direct ChatGPT plugin availability for Codeberg/Forgejo.

## Repository-vault segmentation

Use provider groups/projects and Git permissions to keep domains isolated while preserving one Selma architecture:

- `selma/core`: platform-neutral contracts and governance;
- `selma/android-native`: Android application and device adapters;
- `selma/avatar`: renderer, rig binding, signed appearance packs, animation/audio sync;
- `selma/offline-ai`: llama.cpp/Ollama-compatible local inference adapters;
- `selma/memory-rag`: bounded memory, provenance, indexing, import/export;
- `selma/tools-forge`: compiler/Forge/Selmatizer and build tooling;
- `selma/integrations`: MCP/plugin/provider adapters;
- `selma/evidence`: test manifests, physical-device evidence, release attestations.

These are logical vault boundaries. They may initially remain directories in one repository and graduate to separate repositories only when independent permissions, release cadence, or storage requirements justify the split.

No vault should receive credentials in source control. Authentication remains in provider-native credential stores or user-approved local secret stores.

## Adapter contract

Every IDE/provider adapter should expose these facts before use:

1. provider and authenticated identity;
2. repository/project and exact branch/ref scope;
3. read/write capability set;
4. network requirement;
5. filesystem/process/device reach;
6. approval mode;
7. audit/provenance identifiers;
8. cancellation and kill-switch behavior;
9. degraded/offline behavior;
10. evidence source for any build/test/device claim.

Adapters must fail closed when scope, identity, or capability evidence is missing.

## ChatGPT plugin-directory findings

As of 2026-09-22, the current ChatGPT plugin directory available to this account did not expose direct plugins named GitLab, Android Studio, JetBrains, VS Code, Codeberg, Gitea, SourceHut, or Bitbucket.

Existing connected development-related plugins already cover GitHub, Replit, Lovable, Supabase, Vercel, Figma, OpenAI Developers, Superpowers, and Exa.

A separate authorized-machine bridge is useful for local IDE/toolchain access when no first-party ChatGPT connector exists. That bridge must remain device-scoped and disconnectable.

## Recommended execution order

1. Keep PR #21 and PR #22 based on current `main` and collect real CI evidence.
2. Preserve PR #27 as the stacked Ed25519 layer until PR #21 is accepted.
3. Port the stale plugin-adapter registry into a provider-neutral MCP adapter contract rather than GitHub-specific authority.
4. Port the Android-native Kotlin/overlay/foreground-service pieces onto current main and build them in Android Studio.
5. Establish GitLab as a secondary mirror/provider using provider-native authentication and MCP, without embedding tokens.
6. Add repository-vault manifests that declare path/project scope and capability policy.
7. Use local Ollama-compatible inference for offline IDE assistance where hardware allows, while keeping cloud agents optional.
8. Only after each slice has reproducible evidence, promote it into the canonical release path.

## Primary references

- OpenAI plugin architecture: https://developers.openai.com/plugins/concepts/plugins
- OpenAI Codex: https://openai.com/codex/
- Android Studio MCP: https://developer.android.com/studio/gemini/add-mcp-server
- Android Studio agent permissions: https://developer.android.com/studio/gemini/permissions
- Android Studio local models: https://developer.android.com/studio/gemini/use-a-local-model
- Junie Android development: https://junie.jetbrains.com/docs/android-development-with-junie.html
- GitLab OpenAI integration: https://docs.gitlab.com/integration/openai/
- GitLab MCP server: https://docs.gitlab.com/user/model_context_protocol/mcp_server/
- GitLab MCP tools: https://docs.gitlab.com/user/model_context_protocol/mcp_server_tools/
- GitLab remote development: https://docs.gitlab.com/user/project/remote_development/
- Codeberg CI: https://docs.codeberg.org/ci/
