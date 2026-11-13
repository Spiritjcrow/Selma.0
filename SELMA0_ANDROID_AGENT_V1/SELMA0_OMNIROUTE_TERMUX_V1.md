# Selma.0 OmniRoute Gateway (optional, Android/Termux)

**Scope:** An opt-in local transport to an external routing gateway. It does not modify
Selma's permission engine, command execution, memories, or default offline model.
Do not describe this as a verified physical-device installation or verified online fallback.

## Install

Run from the checked-out Selma.0 repository **inside the Termux app**:

```sh
bash SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh install
bash SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh start
```

The gateway dashboard is `http://127.0.0.1:20128`. The wrapper sets loopback
binding and runs in the foreground. Change the dashboard's initial password during
onboarding, connect **only permitted providers**, then generate an Endpoint API key.
Never commit credentials. The gateway may communicate with cloud models, even
though its API address is local. Free tiers are not guaranteed.

Open another Termux session and use the previously installed Selma Android agent:

```sh
read -rs -p 'OmniRoute endpoint key: ' OMNIROUTE_API_KEY
echo
export OMNIROUTE_API_KEY
# Optional: point to a free-only custom combo you configured in dashboard.
# export SELMA0_OMNIROUTE_MODEL_V1='your-free-only-combo'
bash "$HOME/SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh" status
bash "$HOME/SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh" run-selma
```

`run-selma` attempts Selma's existing `127.0.0.1:8080/v1` local model FIRST,
then calls OmniRoute only after local failure. Default gateway model is
`auto/subscription`, which is intended to exclude usage-based billable fallbacks.
If a true free-only route is required, configure and test a provider combo explicitly.
An endpoint/API key and at least one eligible provider are required; none is
created automatically. The ordinary offline startup remains unchanged.

## Codex CLI (optional)

Codex must be installed separately on the **same host where its command runs**.
For a Codex on a PC, install/configure OmniRoute there or use its documented secure
remote endpoint; Android's `127.0.0.1` is not the PC's loopback interface.

```sh
bash "$HOME/SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh" codex-preview
bash "$HOME/SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh" codex
```

The Codex **CLI**, not the Codex desktop GUI, is the verified launcher target.
Different providers implement different APIs; gateway presence does not establish
Codex Responses API compatibility for every model.

## Verification

```sh
python -m unittest SELMA0_ANDROID_AGENT_V1.tests.test_omniroute_opt_in_v1 -v
bash -n SELMA0_ANDROID_AGENT_V1/selma0_omniroute_termux_android_v1.sh
```

Portable tests mock the model endpoint; they cannot verify Android native dependency
builds, user login, provider access, third-party model availability, or a Codex run.
Do not expose port 20128 to public networks or automate provider account logins.
