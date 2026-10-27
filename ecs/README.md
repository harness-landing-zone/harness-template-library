# ECS delivery templates

A Harness template library for deploying Amazon ECS services through Dev → Staging → Prod with mandatory approvals, Continuous Verification (CV) and native rollback. The platform team owns the templates; application teams consume them from their own Git repositories.

**Recommendation:** use the opinionated templates (fixed profile, or strategy variables) by default, and stage inserts only by exception. [Choosing a template model](docs/choosing-a-template.md) explains why, compares the models, and covers operating at scale, the Git workflow, RBAC and OPA.

## Contents

| Folder | Owner | What it holds |
| --- | --- | --- |
| [stages/](stages/) | Platform | Stage templates: native ECS deployment, Verify and rollback for one strategy |
| [pipelines/](pipelines/) | Platform | Pipeline templates: Dev → Approve Staging → Staging → Approve Prod → Prod |
| [policies/](policies/) | Security | OPA policies that keep consumers on the governed templates |
| [examples/](examples/) | Application team | Consumer pipelines, input sets and overrides as they would sit in an application repo |

### Templates

| Template | Identifier | Kind |
| --- | --- | --- |
| [Rolling stage](stages/rolling_v1.yaml) | `ecs_rolling_stage` | Stage |
| [Canary stage](stages/canary_v1.yaml) | `ecs_canary_stage` | Stage |
| [Blue/Green stage](stages/blue-green_v1.yaml) | `ecs_blue_green_stage` | Stage |
| [Variable strategy stage](stages/variable-strategy_v1.yaml) | `ecs_variable_strategy_stage` | Stage |
| [Rolling delivery](pipelines/rolling_v1.yaml) | `ecs_rolling_delivery` | Pipeline, fixed profile |
| [Canary delivery](pipelines/canary_v1.yaml) | `ecs_canary_delivery` | Pipeline, fixed profile |
| [Blue/Green delivery](pipelines/blue-green_v1.yaml) | `ecs_blue_green_delivery` | Pipeline, fixed profile |
| [Variable delivery](pipelines/variables_v1.yaml) | `ecs_variable_delivery` | Pipeline, strategy per environment |
| [Stage insert delivery](pipelines/stage-inserts_v1.yaml) | `ecs_stage_insert_delivery` | Pipeline, developer-filled slots |

All templates are version `0.1.0`. Each version is its own file (`*_v1.yaml`); a new version is a new file, and a released file is never edited.

### Examples

The examples use the Harness Git Experience layout (`.harness/orgs/<org>/projects/<project>/pipelines/...`). With a Git webhook configured, Harness can import files in this layout automatically. Replace `ORG_ID`, `PROJECT_ID`, `my_ecs_service`, the environment/infrastructure identifiers and the `<...>` placeholders with your own values.

| Combination | Consumer pipeline | Input set |
| --- | --- | --- |
| Rolling everywhere | [ecs_rolling.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling/input_sets/environments.yaml) |
| Canary everywhere | [ecs_canary.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_canary.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_canary/input_sets/environments.yaml) |
| Blue/Green everywhere | [ecs_blue_green.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_blue_green.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_blue_green/input_sets/environments.yaml) |
| Rolling → Canary → Blue/Green by variable | [ecs_variable_strategy.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy/input_sets/environments.yaml) |
| Rolling → Canary → Blue/Green by stage insert | [ecs_stage_inserts.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_stage_inserts.yaml) | Bindings live in the pipeline file, which the team owns in this model |

In the fixed and variable models, the pipeline file is little more than a template reference. The team's day-to-day changes go into the input set. The artifact tag is left as a runtime input, so a trigger or the person running the pipeline supplies it.

Blue/Green routing (load balancer, live and candidate listener and rule ARNs) is not an input. The stage templates read it as service variables, `<+serviceVariables.loadBalancer>`, `prodListenerArn`, `prodListenerRuleArn`, `candidateListenerArn` and `candidateListenerRuleArn`, from a service-specific environment override. See the [Prod override example](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_ecs_service/overrides.yaml); add one per environment that runs Blue/Green. The Blue/Green example also runs a candidate health check in the test slot, which reads `<+serviceVariables.candidateHealthUrl>` from the same override.

## What every pipeline enforces

- **Approvals before Staging and Prod.** Each needs one approver from the release group, the person who ran the pipeline cannot approve, and a rejection or timeout aborts the run. Approvers are fixed in the template and are never runtime inputs.
- **No stage-only runs.** Stage-only execution is disabled, so nobody can run Prod on its own.
- **No later environment after a failure.** In the fixed and variable models, Staging and Prod run only if every earlier stage and approval succeeded.
- **One release promoted across environments.** In the fixed and variable models, the service and artifact are chosen once in Dev; Staging and Prod reuse them (`useFromStage: Dev`).

## What the stage templates do

| Strategy | Forward flow | Verify mode |
| --- | --- | --- |
| Rolling | Rolling deploy → Verify → developer tests | `Rolling` |
| Canary | Canary deploy → Verify → developer tests → delete canary → full Rolling deploy | `Canary` |
| Blue/Green | Create candidate → Verify → developer tests → swap target groups | `Bluegreen` |

- **Verify:** uses the Default monitored service, HIGH sensitivity, a 15-minute analysis window and a 2-hour timeout.
- **Failure:** any failure rolls back the stage. No step can be ignored or marked as successful.
- **Developer tests:** every stage has an optional `Developer_Functional_Test` step insert after Verify. The team adds its tests in the consumer pipeline file; an empty slot is skipped, and a failing test rolls the stage back before traffic moves. See [Developer functional tests](docs/choosing-a-template.md#developer-functional-tests).
- **Canary:** this is Harness native ECS Canary, a temporary canary service followed by a Rolling promotion. It is not weighted traffic shifting.
- **Blue/Green:** the swap scales the old service to zero but keeps its definition, so rollback still works.

## Before first use

1. **Register the templates.** Register the stage templates first, then the pipeline templates. The examples assume account scope (`account.` prefix); use `org.` for org scope. Store the templates as Remote (Git) templates in this repository.
2. **Set the approver group.** Replace `account.<APPROVED_RELEASE_GROUP>` in [pipelines/](pipelines/) with your release approver user group.
3. **Prepare monitoring.** For each service, configure a monitored service and health source that match the environment. Verify can be skipped when no monitoring is configured, so a green stage alone does not prove analysis ran.
4. **Enable feature flags.** Ask Harness Support for `PIE_FLEXIBLE_TEMPLATES` and `PIE_FLEXIBLE_TEMPLATES_PHASE2`. Every stage template's test slot is an insert block, which needs them.
5. **Prepare AWS.** Compatible task and service definitions, load balancer listeners and rules (Blue/Green), and IAM must already exist. The templates do not create them.
6. **Add routing overrides.** For each service and environment that runs Blue/Green, add the five routing variables as a service-specific environment override. If an IaCM workspace in the same project manages the load balancer, the values can reference its outputs, for example `<+workspace.<workspace_id>.prod_listener_arn>`.
7. **Apply governance.** Put the RBAC roles and the [policies](policies/) in place before giving teams access, and especially before enabling stage inserts.
