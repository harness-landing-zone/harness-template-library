# ECS delivery template collection

This folder organizes the existing ECS work into reusable platform templates and developer pipeline examples. It contains all three composition approaches for comparison. The templates are local candidates for Harness testing; they have not been published or deployed.

Platform stages own deployment, Continuous Verification and rollback. Pipeline templates own the release lifecycle. Developers supply the application functional tests. **Those test inserts are intentionally empty in every example.**

## Files

| Folder | Contents |
| --- | --- |
| `stages/` | Rolling, native Canary and Blue/Green stages, plus the existing variable-driven strategy approach |
| `pipelines/` | Stage-insert container, three fixed strategy pipelines, and the variable-driven pipeline |
| `steps-and-step-groups/` | One shared `require-success.yaml` step for lifecycle and verification checks; no step group is needed |
| `example/` | Five developer-facing pipeline YAML files, with configurable targets and empty functional tests |
| `docs/` | [Decisions and comparison](docs/decisions.md) and [Harness testing guide](docs/testing.md) |
| `check.py` | Offline YAML, reference, strategy/rollback and real Bash guard checks |

## Release lifecycle

All five pipeline templates use:

```text
Dev → Staging → check lower environments → production approval → Prod → release result
```

Stage-only execution is disabled. Approval requires a different executor and one approver from `account.developer_leads` or `account.platform_team`, retaining the source project's groups. A failed lower-environment guard or approval aborts the pipeline. The final guard requires successful Dev, Staging, approval stage, approval step and Prod statuses.

The insert container exposes the three deployment slots. It does not natively constrain their stage count, templates, targets or service/artifact consistency. See the required OPA rules and unresolved insert-expression test in [the decisions](docs/decisions.md#governance-boundaries).

## Choose an approach

| Approach | Platform pipeline template | Developer example |
| --- | --- | --- |
| Select a stage template for each environment | [Stage inserts](pipelines/stage-inserts.yaml) | [BG in all three inserts](example/stage-inserts.yaml) |
| Rolling throughout | [Rolling](pipelines/rolling.yaml) | [Rolling example](example/rolling.yaml) |
| Blue/Green throughout | [Blue/Green](pipelines/blue-green.yaml) | [Blue/Green example](example/blue-green.yaml) |
| Native Canary throughout | [Canary](pipelines/canary.yaml) | [Canary example](example/canary.yaml) |
| Select a strategy variable for each environment | [Variables](pipelines/variables.yaml) | [Variable example](example/variables.yaml) |

The examples use project-scoped references in `template_factory / Experian_Demo_Templates`. Every template has a distinct new `ecs_*` identifier and an explicit `0.1.0` version. These are proposed registrations, not references to already-published templates. Existing ECS-Example files and Harness registrations have not been changed.

## Inputs and developer tests

Select the service/artifact once in Dev for the fixed and variable approaches. Staging and Prod use native `useFromStage: Dev`. Select the environment and infrastructure separately for each stage. The stage-insert approach requires service/artifact inputs in each slot because service propagation across separate inserts is not supported.

Use one Harness Service per application, with its own artifacts and manifests. Bind environment-specific network, sizing and routing through service-specific overrides. The Blue/Green stage reads `loadBalancer`, `prodListenerArn`, `prodListenerRuleArn`, `candidateListenerArn` and `candidateListenerRuleArn` from service variables, matching the newer ECS-Example stage. Target infrastructure must already support the selected strategy.

Each stage provides:

- `Application_Validation`: after the initial deployment and before verification/promotion. For Canary or Blue/Green, developers must target the candidate.
- `Live_Validation`: after verification and the final deployment/promotion. Developers validate the resulting live deployment here.

Platform templates expose `steps: <+input>`; starter consumers supply `steps: []`. There are no example HTTP requests, success-only shell scripts or application test implementations. Empty inserts perform no tests and are not evidence of application acceptance. Developer tests should fail normally so the stage's `StageRollback` action can run.

Platform Continuous Verification is separate from functional testing. The Verify mode matches the strategy. Its following guard requires `SUCCEEDED`; missing monitoring configuration that causes Verify to skip must fail this candidate rather than silently continue.

## Validate locally

From the outer workspace folder:

```sh
python3 harness-templates/ecs/check.py
```

The check uses the already-installed PyYAML package. It does not contact Harness or AWS and does not implement application functional tests. It checks the empty starter examples, so fill developer tests in the application repository's consumer rather than treating these starter files as completed application pipelines.

Run the import, reconciliation and deployment checks in [the testing guide](docs/testing.md) before accepting any approach. Documentation decisions use only the supplied `docs/developer-hub` checkout, recorded at commit `da4ff07cd4` dated 29 September 2026.
