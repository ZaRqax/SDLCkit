# Contributing to SDLCkit

Keep the universal core independent of language, issue tracker, git host, model and harness. Preserve target conventions and user-owned files. Put stack-specific conventions in optional profiles and keep reusable legacy skills/entrypoints compatible.

| Change | Canonical location | Validation |
|---|---|---|
| Universal contract | `AGENTS.md` | neutrality and scoped-policy checks |
| Roles and skills | `roles/*.md`, `skills/` | regenerate Claude bridges and legacy snapshots |
| Workflow | `config/workflows/*.yaml` | DAG/role/condition validation and runtime tests |
| Configuration/policy | `sdlc/config.py`, `sdlc/policy.py`, schemas | invalid/unsafe inputs and precedence tests |
| Harness/onboarding | `sdlc` discovery/installer/harness modules | deterministic preview/install/uninstall and native adapter tests |
| Sources/delivery | integrations/delivery modules and contracts | fake process transport, provenance, authorization and reconciliation tests |
| Runtime/watchers | runtime modules | isolation, lease/retry/cancellation and opt-in audit tests |

Read existing code before editing and verify APIs against installed tool versions/official documentation. Never hand-edit generated role bridges, pi snapshots or target codegen. Never commit credentials, local override values or private work artifacts. All shipped code and instructions are English; translated docs have explicit language suffixes.

Before a local commit run:

```bash
python3 scripts/render-role-bridges.py
python3 agents-config/pi/port-agents.py
bash scripts/check-kit.sh
python3 -m unittest discover -s tests -v
```

A PR description should state the concrete resulting behavior, ordered material changes and actual validation/limitations. Use the repository's branch/commit conventions; no Jira key, develop base or publication ceremony is universal. Keep plugin identifiers and documented shell/porter contracts stable unless a tested migration is provided in `docs/compatibility.md`. Do not push, publish, merge or change external issues without authorization.
