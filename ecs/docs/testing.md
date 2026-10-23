# ECS candidate validation

## Completed authoring checks

All four canonical Stage Templates and five parent Pipeline Templates saved as valid INLINE entities at `0.1.0`. Five comparison consumers were migrated to canonical references without replacing their pipeline IDs. A separate Dev-only Rolling consumer was migrated while preserving its existing service, environment, infrastructure and fixed image-tag binding.

Harness MCP readback, resolved YAML and runtime-input generation confirmed:

- The five parents expand as Dev → Approve Staging → Staging → Approve Prod → Prod, with stage-only execution disabled.
- Both approvals require one authorized non-executor approver, keep their group binding fixed in the parent, and use Abort for errors.
- Fixed and variable deployment success predicates survive template expansion.
- Native CV order, modes, timing and rollback remain present; insert children retain native success-only execution without assumed slot-status expressions.
- Fixed/variable consumers request service inputs only in Dev and retain `useFromStage: Dev` later. Insert consumers retain separate service inputs per slot.
- The Dev-only consumer is valid and has no runtime inputs.

These are composition/acceptance checks. No pipeline, approval, deployment, CV analysis, AWS change or Terraform apply was executed during consolidation.

## Local checks

From the repository root:

```sh
python3 ecs/check.py
```

The checker uses installed PyYAML, validates canonical references/contracts and exercises strategy/CV-failure/rollback predicates. For MCP evidence captured as a JSON array containing each consumer's `saved`, `resolved` and `inputs` response objects:

```sh
python3 ecs/check.py /path/to/evidence.json
```

No evidence file with sandbox resource bindings is stored in the public library. Scope and approver bindings are injected when registering templates. Do not treat YAML validation or a passing predicate check as proof that expressions, IAM, ECS, monitoring queries or approval behavior work at runtime.

## Runtime validation still required

Before an explicitly authorized deployment test, bind the service/artifact, environment, infrastructure and manifest overrides; configure the matching monitored service and health source; confirm query results and an appropriate baseline. Inspect actual CV analysis rather than accepting a skipped Verify as health evidence. Native Verify here has no proven missing-analysis failure setting.

Then validate successful deployment/analysis and deliberately exercise deployment/CV failure, native recovery, approval rejection and approval timeout. Confirm no later environment deploys after an unsuccessful gate. Verify actual service/artifact/manifest propagation across environments, candidate access for Canary/Blue/Green, and Blue/Green rollback after old-service scale-down. General developer stage-insert use also needs policy tests for empty slots, skipped or altered stages, targets and release consistency. These runtime and governance checks remain unperformed.
