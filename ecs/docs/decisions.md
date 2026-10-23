# ECS template decisions

## Start with fixed profiles

| Composition | Benefits | Costs and limits |
| --- | --- | --- |
| Fixed Rolling, Blue/Green or Canary | Small predictable graph; shared native stage templates; one service/artifact selection in Dev | Three lifecycle files must stay aligned; one strategy throughout each pipeline |
| Strategy variables | One parent; choose a strategy per environment; service propagation from Dev | More conditional forward/CV/rollback branches; infrastructure and manifests must match the chosen strategy |
| Stage inserts | Independently select a pinned stage template in each deployment slot | Consumer controls inserted stages; repeated service/artifact inputs; arbitrary empty/skipped/altered stages need composition policy |

All approaches share mandatory approvals before Staging and Prod. Approvers are bound during registration, never exposed as runtime inputs. Approval rejection or timeout follows `AllErrors → Abort`; there is no skip, auto-approval or mark-success override. Native success conditions stop normal progression after unsuccessful deployments or approvals. Fixed/variable Staging and Prod also check actual preceding stage IDs and approval success. The insert container uses native success-only progression and fixed approval stages; it does not assume that insertion slot names are executable aggregate stage-status expressions.

The public approver-group placeholder must be replaced with a real authorized group before registration. Template and pipeline edit rights must remain controlled. Parent composition does not govern arbitrary future consumer-authored insert content: restricting slot count, stage types, skip/failure overrides, target environments, service and immutable artifact consistency would need policy against actual Harness payloads. No new policy system is implemented here.

## Native deployment and verification

The strategy stages reuse native ECS operations and `StageRollback`, with no setup retries that could capture a failed attempt as the rollback baseline. Canary cleanup deletes the failed temporary canary; Rolling rollback runs when full promotion was attempted. Blue/Green uses native create, swap and rollback, with `doNotDownsizeOldService: false` so the old service is retained at zero tasks rather than left running indefinitely.

Native Canary is `EcsCanaryDeploy → Verify → EcsCanaryDelete → EcsRollingDeploy`. It differs from weighted Blue/Green traffic shifting. Candidate access, compatible service manifests and pre-existing routing remain prerequisites; changing a strategy value does not create them.

All Verify steps use HIGH sensitivity, 15 minutes and a 2-hour timeout, with the Default monitored service. Rolling verification follows Rolling deployment; Canary and Bluegreen verification precede final promotion/swap. The variable stage selects the matching Verify mode and native recovery branch. No manual success or manual-intervention override masks a verification failure.

Current native Verify may skip when matching monitoring configuration is missing. Removing the old status-shell helper deliberately avoids claiming that CV success is enforced when analysis never ran. Runtime validation must inspect actual CV analysis and health-source data. `failOnNoAnalysis` from newer AIVerify configuration is not evidence of support in this Verify step and is not added.

## Service and resource inputs

Fixed and variable parents use the documented `service.useFromStage.stage: Dev` shape in Staging and Prod. Harness expansion preserves propagation, and runtime-input generation asks for service/artifact only in Dev. Expanded YAML may retain the stage template's service placeholders alongside `useFromStage`; absence of lower-environment service prompts confirms authoring acceptance, not runtime artifact or manifest behavior.

Environment, infrastructure definitions, service overrides and strategy-specific routing remain per-environment inputs. The stage-insert alternative repeats the service/artifact selection per slot. Deploy the same immutable release across slots and verify service/manifest compatibility separately. Source examples contain no customer service, environment, connector or workspace bindings.

## Canonical source and registration

The library has four Stage Templates (`ecs_rolling_stage`, `ecs_canary_stage`, `ecs_blue_green_stage`, `ecs_variable_strategy_stage`) and five Pipeline Templates (`ecs_rolling_delivery`, `ecs_blue_green_delivery`, `ecs_canary_delivery`, `ecs_variable_delivery`, `ecs_stage_insert_delivery`), all version `0.1.0`. The separate draft source tree and generic require-success helper are superseded. Existing unused draft registrations remain in the sandbox; consumers now reference canonical templates.

Register stages first, then parent pipelines, then consumer pipelines, injecting destination scope and an approved group. Registrations used INLINE storage. Published releases should receive new versions rather than silently changing behavior; these are sandbox candidates, not an immutability or runtime validation claim.

## Service onboarding for developer-managed IaCM

Future onboarding should map infrastructure/workspace outputs → Harness service, environment, infrastructure and service-specific overrides → monitored service and health-source queries → deployment and CV validation. Record artifact identity, compatible task/service manifests, routing, metrics/log dimensions and baseline availability before executing a deployment test.

Terraform onboarding code is proposed work. Customer application/IaCM code has not been copied into this public library. The known provider 0.47.2 CloudWatch omission means query outputs and API-payload generation alone must not be described as managed health-source CRUD. Establish supported ownership and create/update/delete behavior before claiming an automated monitoring lifecycle.
