# ECS template decisions and approach comparison

This collection separates deployment behavior from the platform release lifecycle and leaves functional tests to application developers. It preserves three composition options for testing rather than inventing a new pipeline generator. The fixed pipelines are the simplest baseline; stage inserts provide the independent template selection needed by the Backstage design, with more governance work. Variables retain the existing conditional strategy implementation as a comparison.

These are local candidate templates. File organization and offline checks do not establish that Harness accepts every mapping or that ECS deployment succeeds.

## Ownership and reuse

| Component | Decision | Reason |
| --- | --- | --- |
| Step templates | Share the status guard used by pipelines and verification checks | One implementation rejects missing and non-success statuses consistently |
| Step groups | None added | There is no separate reusable multi-step unit that needs another template; local documentation also prohibits inserts inside step-group templates |
| Deployment stages | Separate Rolling, native Canary and Blue/Green | Deployment order, verification mode, promotion and rollback belong together |
| Variable strategy stage | Retain one additional stage with mutually exclusive branches | This represents the requested variable-driven alternative; it is not a fourth deployment strategy |
| Pipeline templates | Own Dev → Staging → approval → Prod → result | Application consumers cannot edit the linked platform lifecycle outside declared inputs/inserts |
| Functional tests | Expose application and live validation inserts; leave examples empty | The application team knows what validates its service |
| Service and targets | Retain Harness service/environment inputs | Avoid coupling artifact schema to one example service or introducing a custom configuration language |
| Strategy variables | Place three selectors in the variable pipeline's inputs | Backstage can set one value per environment; the parent maps each to the stage variable |

These choices follow the local [template guidelines](../../../docs/developer-hub/docs/platform/templates/templates-best-practices.md), [stage-template documentation](../../../docs/developer-hub/docs/platform/templates/add-a-stage-template.md) and [step-group documentation](../../../docs/developer-hub/docs/platform/templates/create-a-stepgroup-template.md). The decision to avoid additional wrappers is specific to this collection, not a Harness restriction.

## Three ways to compose delivery

| Approach | Advantages | Disadvantages | Backstage output |
| --- | --- | --- | --- |
| Stage inserts | Select and version a different approved deployment-stage template for each environment; add deployment types without adding branches to one stage | More YAML in the consumer; stage count/type/target restrictions need OPA; repeat release inputs across slots; insert status expressions and referenced stages containing test inserts need account validation | Parent container reference plus one approved stage reference/version and its inputs in each slot |
| Three fixed pipelines | Simple selection; predictable execution graph; independent strategy stages; native service propagation across environments | Three lifecycle files need synchronized changes; one strategy per pipeline; mixed strategies need another profile or inserts | One pipeline reference for Rolling, Blue/Green or Canary, plus service/targets/test inputs |
| Variables | One lifecycle template; one strategy selector per environment; native service propagation; close to the existing working authoring model | Conditional graph and rollback predicates are harder to reason about; deployment logic is also represented in the strategy-specific stages; a strategy change still requires compatible infrastructure and manifests | One pipeline reference, three strategy values, service/targets/test inputs |

**Recommendation for evaluation:** start with a fixed pipeline to establish deployment and rollback behavior. Then test the same stage through an insert. Prefer inserts if independently selecting stage templates is a firm product requirement. Prefer fixed pipelines if three homogeneous profiles are enough. Retain variables where runtime strategy selection is valuable and the team accepts maintaining the conditional stage.

All three approaches keep the platform lifecycle versioned. All require control of who can edit templates/policies and how developer pipelines reference the approved parent. None makes arbitrary developer-authored insert content safe by itself.

## What was reused and changed

The primary source is [ECS-Example](../../../ECS-Example/.harness/experian/README.md), not the older customer example that labels weighted Blue/Green traffic shifting as Canary.

| New file or group | Source and intentional changes |
| --- | --- |
| `stages/rolling.yaml`, `canary.yaml`, `blue-green.yaml` | Extracted the matching native steps from [ECS_multistage v2](../../../ECS-Example/.harness/templates/ECS_multistage/v2.yaml); removed strategy conditions from single-strategy forward steps; kept strategy-appropriate rollback |
| `stages/variable-strategy.yaml` | Retained the v2 branches and rollback predicates; renamed the application hook consistently and added the live hook; removed the unused test-specific `canaryHealthUrl` variable |
| `pipelines/rolling.yaml`, `blue-green.yaml`, `canary.yaml`, `variables.yaml` | Reused [the v2 lifecycle](../../../ECS-Example/.harness/templates/experian_ecs_multistrategy_delivery/v2.yaml); fixed stages reference the respective new templates; variable selectors are declared by the parent |
| `pipelines/stage-inserts.yaml` | Reused [the insert lifecycle](../../../ECS-Example/.harness/templates/experian_ecs_stage_insert_delivery/v1.yaml); removed temporary approval/result skips and retained the three insert slots |
| `steps-and-step-groups/require-success.yaml` | Extracted the repeated lifecycle status check into one step; added an expected count so missing values cannot disappear unnoticed; final lifecycle checks include the actual approval-step result |
| All stage verification | Removed the source's manual-intervention override so failure uses `StageRollback`; added an explicit Verify-success guard |
| All consumers | New linked examples with empty application/live functional-test lists; no temporary `condition: 'false'` or skipped environment stages |

The additional verification guard addresses an observed source limitation: the recorded Dev run succeeded while CV was skipped for invalid/missing monitoring configuration. Local [verification documentation](../../../docs/developer-hub/docs/continuous-delivery/verify/configure-cv/verify-deployments.md) also says missing matching monitored services can cause Verify to skip. This collection chooses to require actual verification success. Therefore, configuring a monitored service and health source is a prerequisite for deployment testing.

The variable strategy guard selects the matching Verify result using a Harness expression. Its expression resolution is part of the Harness testing phase, not something the offline Python check can prove.

## Deployment behavior

| Strategy | Forward flow | Failure behavior |
| --- | --- | --- |
| Rolling | Rolling deploy → application insert → Rolling verification → verification guard → live insert | Native Rolling rollback |
| Native Canary | Canary deploy → application insert → Canary verification → verification guard → delete canary → full Rolling deploy → live insert | Delete a failed canary before full rollout; use Rolling rollback after full rollout is attempted |
| Blue/Green | Create candidate → application insert → Bluegreen verification → verification guard → swap target groups → live insert | Native Blue/Green rollback; keep the old service during the swap for rollback |

The [local ECS deployment guide](../../../docs/developer-hub/docs/continuous-delivery/deploy-srv-diff-platforms/aws/ecs/ecs-deployment-tutorial.md) documents native Canary as a temporary canary followed by a full Rolling deployment. This is distinct from weighted traffic shifting. It also documents Blue/Green listener/target-group requirements and warns that retries on setup steps can capture the failed state as the next rollback baseline. The templates use stage rollback, with no automatic retry around ECS deployment steps.

Application test inserts contain no implementation. For Canary, a developer must arrange a route or another valid way to inspect the temporary canary; a live-service URL alone does not prove the canary is healthy. For Blue/Green, candidate checks must reach the candidate listener before swapping. Networking, manifests and IAM remain prerequisites in the existing service/infrastructure resources; changing a strategy variable does not provision them.

## Governance boundaries

The parent fixes approval settings and lifecycle guards, and each stage fixes success-only execution and `StageRollback`. Developer consumers supply service/target inputs and test inserts. There are no advanced-setting overrides exposed by these candidate stage templates.

The [insert documentation](../../../docs/developer-hub/docs/platform/templates/inject-step-stage-templates.md) describes inserts as normal stage/step extension points. Empty inserts are allowed. It documents the `PIE_FLEXIBLE_TEMPLATES` and `PIE_FLEXIBLE_TEMPLATES_PHASE2` flags, no service/environment/infrastructure propagation across separate inserts, and a nested-insert limitation.

For this collection, enforce the following with platform-controlled policy before allowing general developer use:

- Require the approved parent template reference/version; do not activate governance solely from removable tags.
- For the stage-insert option, require exactly one approved templated Deployment stage in each Dev/Staging/Prod slot. Reject empty slots, inline stages, extra/parallel/repeated stages and unapproved versions.
- Bind each slot to its allowed environment and infrastructure. A stage or insert called `Dev` is not proof that it targets a Dev environment.
- Require the same approved service and immutable release across the three inserts. The lifecycle guard checks statuses, not artifact identity.
- Restrict test steps' failure/skip behavior if successful functional validation becomes mandatory. Empty functional inserts are deliberately allowed in these starter examples.
- Protect template/policy edits with RBAC. Keep the fixed profile stages and variable values within the approved catalog as well.

No Rego is fabricated here against an assumed payload. Capture the actual expanded Harness policy input first. The [governance overview](../../../docs/developer-hub/docs/platform/governance/policy-as-code/harness-governance-overview.md) says references are expanded but JEXL expressions and variables are not generally resolved for OPA. On Save and On Run policies with Error and Exit, literal target references where practical, and testing actual runtime inputs are needed.

Direct Git commits need their own coverage. The [Git-backed enforcement guide](../../../docs/developer-hub/docs/platform/governance/policy-as-code/enforce-policies-on-git-backed-entities.md) requires a GitX webhook and the `PIPE_OPA_GITX_ENFORCEMENT` and `PIPE_ENABLE_OPA_GOVERNANCE_FOR_AUTO_CREATION` flags for pipeline/template On Save enforcement. This can block Harness execution; preventing an invalid merge also needs repository controls.

## Insert behavior still to verify

The insert container deliberately preserves the source expressions `<+pipeline.stages.Dev.status>`, `<+pipeline.stages.Staging.status>` and `<+pipeline.stages.Prod.status>`. They refer to the slot identifiers, while inserted deployment stages have distinct IDs such as `Dev_BG`. **The source record does not establish that these aggregate slot-status expressions work:** its successful deployment test skipped approval/result guards. Inspect Harness execution expressions and validate these references before using this container. An unresolved value is rejected by the shared guard; do not bypass it to make a test green.

The local documentation also says nested inserts are unsupported. The source example links a stage template containing step inserts from a stage insert. That exact composition was used in its sandbox, but it is not a blanket guarantee of support from the local documentation. Save, reconcile and execute this specific shape in the target account, including developer-populated hooks, before adopting it. The fixed pipelines avoid that particular composition question.

## Versioning and publication

New identifiers avoid silently replacing the live Experian templates. All links pin `0.1.0`; there are no stable/latest labels or unpinned template references. Protect published versions from in-place edits through the platform workflow and publish new versions for behavior/input changes. A version label by itself is not an immutability guarantee.

Import the shared step, then stages, then pipeline templates, and finally consumers. Use Harness reconciliation when the input contract changes. Do not delete required `templateInputs` to make Git YAML shorter. See the local [versioning guidance](../../../docs/developer-hub/docs/platform/templates/templates-best-practices.md) and [reconciliation documentation](../../../docs/developer-hub/docs/platform/templates/reconcile-pipeline-templates.md).

For fixed and variable pipelines, native service propagation avoids repeating release selection but is not a reason to use mutable artifact expressions. Select an immutable image release and a controlled manifest revision. Across inserts, repeat that same release explicitly and govern consistency.

The documentation baseline is the supplied `docs/developer-hub` checkout at `da4ff07cd4`, dated 29 September 2026. Existing source files were copied/adapted rather than moved or deleted, so the currently configured Git-backed examples continue to have their original paths.
