# Choosing a template model

This library offers three ways to consume the ECS templates. This guide compares them, explains how each one works when pipelines live in Git, and lists the RBAC and OPA controls each one needs so that application teams work only with their inputs (or their insert slots) and never change the governed template.

Statements about Harness behaviour link to the Harness Developer Hub page they come from.

## At a glance

| | Fixed profile | Strategy variables | Stage inserts |
| --- | --- | --- | --- |
| Pipeline template | `ecs_rolling_delivery`, `ecs_canary_delivery`, `ecs_blue_green_delivery` | `ecs_variable_delivery` | `ecs_stage_insert_delivery` |
| Strategy | One for all environments | Chosen per environment from `rolling`, `canary`, `blue-green` | Chosen per slot by picking a stage template |
| What the team edits | Input set only | Input set; strategy values via reviewed change | The pipeline file: the whole content of each slot |
| Same release promoted across environments | Yes | Yes | No, service chosen again in each slot |
| Developer Harness permission | Execute + input sets | Execute + input sets | Pipeline Create/Edit as well |
| Extra feature flags | None | None | `PIE_FLEXIBLE_TEMPLATES`, `PIE_FLEXIBLE_TEMPLATES_PHASE2` |
| Governance effort | Low | Low | High |
| Recommended for | Most services | Teams that need a different strategy in Prod | Teams with a reviewed need to add their own stages |

## Fixed profile

The consumer pipeline is a template reference plus runtime inputs ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling.yaml)). The team sets the service, environments and infrastructure in an input set ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling/input_sets/environments.yaml)).

**Pros**

- **Nothing to change but inputs.** No steps, stages, failure strategies or conditions are exposed. The templates define no `allowedOverrides`, so callers cannot override advanced settings either. An absent `allowedOverrides` "means nothing can be overridden" ([template overrides](https://developer.harness.io/docs/platform/templates/template-overrides)).
- **One release promoted.** The service and artifact are selected once in Dev, and Staging and Prod reuse them with `useFromStage`.
- **Smallest graph.** The pipeline is the easiest to read in execution and the easiest for approvers to review.
- **Least access.** Developers need no pipeline edit permission.

**Cons**

- **One strategy per pipeline.** Changing strategy means pointing the pipeline at a different template.
- **Three parents to maintain.** The three pipeline templates must be kept aligned when the platform changes the flow.

## Strategy variables

One parent template whose stage selects Rolling, Canary or Blue/Green from a variable per environment ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy.yaml)).

**Pros**

- **One governed graph, mixed strategies.** For example, Rolling in Dev and Blue/Green in Prod, still with one template to govern.
- **Limited choice.** The developer still edits values only, and only from the allowed list.
- **One release promoted.** Same as the fixed profile.

**Cons**

- **More conditional logic.** The stage template carries conditional forward, Verify and rollback branches, which makes executions harder to read.
- **Blue/Green inputs everywhere.** The routing inputs are part of every stage, even where the strategy is not Blue/Green.
- **No infrastructure behind the choice.** Picking `blue-green` does not create listeners or target groups; the infrastructure must already match.

## Stage inserts

The parent fixes the approvals and their order; each environment is an `insert` slot (`stages: <+input>`) that the team fills with a stage of its choice ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_stage_inserts.yaml)). See [insert blocks](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates).

**Pros**

- **Most flexibility.** A different stage template per environment, or additional stages such as tests or migrations next to the deployment.
- **Fixed gates.** The approvals and their position cannot be moved by the team.

**Cons**

- **Developers need pipeline edit permission.** Pipeline Create/Edit is required to provide insert content.
- **A slot can hold almost anything.** Harness accepts CI, CD, Custom and Approval stages in a slot, with their own failure strategies and conditional execution, and an empty slot simply runs nothing. Without policy, a team could leave Dev empty, put a shell stage in Prod, ignore failures, or target a production environment from the Dev slot. Approvers then approve whatever the slot contained.
- **No release propagation.** Service, environment and infrastructure propagate only inside one insert block, so each slot selects the service again and nothing guarantees the same artifact reaches Prod.
- **Behind feature flags.** Inserts need `PIE_FLEXIBLE_TEMPLATES` and `PIE_FLEXIBLE_TEMPLATES_PHASE2`, and recent release notes contain several insert-block fixes. Test them in a sandbox before relying on them.

**Do not roll out stage inserts without the OPA policies below set to Error and exit.**

## Recommendation

1. Default every service to a **fixed profile**.
2. Offer **strategy variables** where a team needs a different strategy per environment.
3. Allow **stage inserts** only for teams with a reviewed need, after the insert policies are enforced and tested.

If the goal is "developers only work in their insert stages", the fixed and variable models give a stronger version of it: developers only work in their input set.

## Working from Git

The library and the consumers live in different repositories:

| Repository | Contains | Who merges |
| --- | --- | --- |
| Template library (this repo) | `stages/`, `pipelines/` as Remote templates | Platform team |
| Application repo | `.harness/orgs/<org>/projects/<project>/pipelines/<pipeline>.yaml` and `.../pipelines/<pipeline>/input_sets/*.yaml` | Application team, with platform review of pipeline files |

How it behaves:

- **Templates resolve from the default branch.** When a remote template lives in a different repository from the pipeline, the template must be in that repository's default branch ([remote pipeline templates](https://developer.harness.io/docs/platform/templates/create-a-remote-pipeline-template)). Merging to the library's default branch is therefore a release. Publish behaviour changes as a new version label rather than editing `0.1.0` in place.
- **Pin versions.** Consumers reference `versionLabel: 0.1.0`. Move teams to a new version through a pull request rather than "Always use Stable", which pushes a change to every pipeline at once ([best practices](https://developer.harness.io/docs/platform/templates/templates-best-practices)).
- **Autocreation needs a webhook.** Files under `.harness/` in the default branch can be created in Harness automatically when a Git Experience webhook is registered ([autocreation](https://developer.harness.io/docs/platform/git-experience/autocreation-of-entities)). Otherwise import them once from the UI.
- **Input sets sit next to the pipeline.** Each input set names its pipeline with `pipeline.identifier` ([pipeline repo](https://developer.harness.io/docs/platform/git-experience/manage-a-harness-pipeline-repo-using-git-experience)).
- **Triggers are not in Git.** Triggers are stored in Harness, not Git. Create them in Harness and point them at the input set.

**Git changes bypass Harness RBAC.** A commit to `.harness/` changes the pipeline without Harness checking pipeline edit permission. Protect the files in Git and in Harness:

- **Branch protection and code owners.** In application repos, require platform review for `.harness/**/pipelines/*.yaml`; leave `input_sets/` to the team. Protect this library's default branch the same way.
- **OPA on Git commits.** Enable `PIPE_OPA_GITX_ENFORCEMENT` and `PIPE_ENABLE_OPA_GOVERNANCE_FOR_AUTO_CREATION`. Harness then evaluates On Save policies on commits made directly in Git and blocks execution when the latest commit fails ([enforce on Git entities](https://developer.harness.io/docs/platform/governance/policy-as-code/enforce-policies-on-git-backed-entities)).
- **On Run as a backstop.** Keep On Run policies enforced as well.

## Where "developers can't modify the template" comes from

RBAC on templates protects the template itself. It does not protect the consumer pipeline: with pipeline edit, a user can choose **Remove template** or **Change template** in Pipeline Studio ([use a template](https://developer.harness.io/docs/platform/templates/use-a-template)) and edit a plain pipeline. RBAC cannot express "edit, but keep the template link", so OPA and Git review have to.

| Risk | Fixed / variables | Inserts | Control |
| --- | --- | --- | --- |
| Edit the template | Blocked | Blocked | RBAC on templates + library branch protection |
| Copy the template into an unlinked pipeline | Blocked | Blocked | RBAC: no `core_template_copy` |
| Remove or change the template link | Blocked without pipeline edit; possible through Git | Possible | OPA policy 1 + code owners |
| Arbitrary slot content | n/a | Possible | OPA policies 2, 3, 5, 6 |
| Remove or weaken an approval | Only by unlinking | Only by unlinking | OPA policy 4 |
| Approve one's own release | Blocked for the person who ran it | Same | Approver group excludes developers who author changes |
| Change the policies | Blocked | Blocked | RBAC: no governance permissions for developers |

## RBAC

Permission identifiers come from the [permissions reference](https://developer.harness.io/docs/platform/role-based-access-control/permissions-reference). Bind roles through resource groups at the scope where the templates live.

| Role | Grant | Do not grant |
| --- | --- | --- |
| **Template owner** (platform; ideally a service account driven by library CI) | `core_template_view/create/edit/delete/access` | Pipeline execute in application projects |
| **Policy admin** (security) | `core_governancePolicy_*`, `core_governancePolicySets_*` | Template edit |
| **Release approver** (the group that replaces `<APPROVED_RELEASE_GROUP>`) | Pipeline view; membership of the approver user group | Pipeline or template edit; developers who author changes |
| **Developer, fixed/variable** | `core_pipeline_view/execute`, `core_inputset_view/edit`, `core_template_view/access`; `view` + `access` on services, environments, connectors and secrets | `core_pipeline_create/edit/delete`; `core_template_copy/create/edit/delete`; edit on environments, connectors and secrets |
| **Developer, inserts** | The above plus `core_pipeline_create/edit` | Same as above; only safe with the OPA policies enforced |
| **Pipeline creator** (service account used by IDP or Terraform) | `core_pipeline_create/edit`, `core_template_access` | Execute, template edit |

Further controls:

- **Production environments.** Use [ABAC](https://developer.harness.io/docs/platform/role-based-access-control/attribute-based-access-control) to split environment permissions by type (Production / Pre-Production). Decide deliberately who holds `core_environment_access` on Production: if developers trigger the whole pipeline they are likely to need it, and Prod is then protected by the approval and OPA rather than RBAC. Confirm in a sandbox how environment access is checked for the user who runs the pipeline.
- **Platform-created pipelines.** In the fixed and variable models, let the platform create consumer pipelines with the pipeline-creator account, so developers never need pipeline edit.

## OPA policies

Policies are Rego, grouped into policy sets per entity and event ([governance overview](https://developer.harness.io/docs/platform/governance/policy-as-code/harness-governance-overview)). Pipelines are evaluated On Save, On Run (after preflight) and, behind `PIPE_IS_PRE_STEP_OPA_POLICY_EVALUATION_ENABLED`, On Step Start. Templates are evaluated On Save only, and existing templates are not re-evaluated when a policy is added ([templates](https://developer.harness.io/docs/platform/governance/policy-as-code/policy-as-code-for-templates)).

Put the pipeline policies in sets with **Error and exit** on both On Save and On Run.

> **Check the payload before enforcing.** OPA receives "an expanded version of the pipeline YAML" and expressions are not resolved. The Harness samples read `stage.template.templateRef`, so stage template references are present. The payload shape of `pipeline.template` and of `insert` blocks is not documented. In the policy editor, test each policy against a real pipeline of each model, adjust the paths, and run in Warn mode first. These policies have not yet been evaluated against a Harness payload.

Shared definitions, included in each pipeline policy:

```rego
package pipeline

approved_parents := {"account.ecs_rolling_delivery", "account.ecs_canary_delivery", "account.ecs_blue_green_delivery", "account.ecs_variable_delivery", "account.ecs_stage_insert_delivery"}
approved_stage_templates := {"account.ecs_rolling_stage", "account.ecs_canary_stage", "account.ecs_blue_green_stage", "account.ecs_variable_strategy_stage"}
approved_versions := {"0.1.0"}

# [slot, stage] for top-level stages (slot "") and stages inside insert slots.
stages[[slot, s]] {
  s := input.pipeline.stages[_].stage
  slot := ""
}
stages[[slot, s]] {
  ins := input.pipeline.stages[_].insert
  s := ins.stages[_].stage
  slot := ins.identifier
}
```

Stage template references inside the expanded parent may appear without the `account.` prefix; include both forms if that is what the payload shows.

### 1. Pipeline uses an approved parent and version (all models)

```rego
deny[msg] {
  not input.pipeline.template.templateRef
  msg := "Pipelines must be created from an approved pipeline template"
}

deny[msg] {
  ref := input.pipeline.template.templateRef
  not approved_parents[ref]
  msg := sprintf("Pipeline template '%s' is not approved", [ref])
}

deny[msg] {
  v := input.pipeline.template.versionLabel
  not approved_versions[v]
  msg := sprintf("Pipeline template version '%s' is not approved", [v])
}
```

If the expanded payload does not keep `pipeline.template`, rely on policies 2 and 4. Together they reject any pipeline without the governed shape.

### 2. Every deployment stage uses an approved stage template (all models)

```rego
deny[msg] {
  [_, s] := stages[_]
  s.type == "Deployment"
  not s.template
  msg := sprintf("Deployment stage '%s' must use an approved stage template", [s.identifier])
}

deny[msg] {
  [_, s] := stages[_]
  ref := s.template.templateRef
  not approved_stage_templates[ref]
  msg := sprintf("Stage '%s' uses unapproved template '%s'", [s.identifier, ref])
}

deny[msg] {
  [_, s] := stages[_]
  s.template
  not approved_versions[s.template.versionLabel]
  msg := sprintf("Stage '%s' uses template version '%s'", [s.identifier, s.template.versionLabel])
}
```

### 3. Insert slots hold exactly one templated stage (inserts)

Loosen this if you decide to allow, for example, a test stage before the deployment.

```rego
slots := {"Dev", "Staging", "Prod"}

deny[msg] {
  ins := input.pipeline.stages[_].insert
  slots[ins.identifier]
  count(object.get(ins, "stages", [])) != 1
  msg := sprintf("Insert slot '%s' must contain exactly one deployment stage", [ins.identifier])
}

deny[msg] {
  [slot, s] := stages[_]
  slots[slot]
  not s.template
  msg := sprintf("Stage '%s' in slot '%s' must use an approved stage template", [s.identifier, slot])
}
```

### 4. Approval gates are intact (all models)

```rego
approval_group := "account.<APPROVED_RELEASE_GROUP>"  # set to your approver group

deny[msg] {
  gate := {"Approve_Staging", "Approve_Prod"}[_]
  not gate_ok(gate)
  msg := sprintf("Approval stage '%s' is missing or has been altered", [gate])
}

gate_ok(id) {
  s := input.pipeline.stages[_].stage
  s.identifier == id
  step := s.spec.execution.steps[_].step
  step.type == "HarnessApproval"
  step.spec.approvers.disallowPipelineExecutor == true
  step.spec.approvers.minimumCount >= 1
  step.spec.approvers.userGroups[_] == approval_group
}
```

### 5. No failure masking (all models)

The stage templates only use stage rollback and abort. This keeps it that way in insert content and future versions.

```rego
forbidden_actions := {"Ignore", "MarkAsSuccess", "ManualIntervention"}

deny[msg] {
  walk(input.pipeline, [path, node])
  forbidden_actions[node.action.type]
  msg := sprintf("Failure action '%s' is not allowed (at %v)", [node.action.type, path])
}
```

### 6. Environment matches the slot (On Run; inserts and variables)

Runtime inputs are known only at run time, so evaluate this On Run. Identify production environments by your naming convention or an allowlist.

```rego
prod_envs := {"prod"}

deny[msg] {
  [slot, s] := stages[_]
  slot != ""
  slot != "Prod"
  prod_envs[s.spec.environment.environmentRef]
  msg := sprintf("Slot '%s' may not deploy to production environment '%s'", [slot, s.spec.environment.environmentRef])
}
```

For fixed and variable pipelines, apply the same rule to top-level stages using `s.identifier` (`Dev`, `Staging`) instead of `slot`.

### 7. Template saves keep the guarantees (template entity, On Save)

```rego
package template

deny[msg] {
  count(object.get(input.template, "allowedOverrides", [])) > 0
  msg := "Governed templates must not allow caller overrides"
}

deny[msg] {
  input.template.type == "Pipeline"
  input.template.spec.allowStageExecutions != false
  msg := "Pipeline templates must disable stage-only execution"
}

deny[msg] {
  input.template.type == "Pipeline"
  step := input.template.spec.stages[_].stage.spec.execution.steps[_].step
  step.type == "HarnessApproval"
  step.spec.approvers.disallowPipelineExecutor != true
  msg := sprintf("Approval '%s' must disallow the person who ran the pipeline", [step.identifier])
}
```

With `PIE_USE_OPTIMISED_TEMPLATE_RESOLUTION`, the payload also carries `storeType`, so you can require Remote templates.

## Rollout checklist

1. Register the templates as Remote from this repository and set the approver group.
2. Create the roles and resource groups. Confirm a developer cannot edit, copy or delete templates.
3. Add code owners and branch protection to the library and to application repos.
4. Create the policy sets in Warn mode, run each example, and fix payload paths until only intended violations remain. Then switch to Error and exit.
5. Run negative tests as a developer. Each of these must be blocked:
   - removing the template link
   - committing a changed pipeline straight to Git
   - leaving a slot empty
   - adding a shell stage to Prod
   - adding an `Ignore` failure strategy
   - targeting Prod from Dev
   - approving their own run
6. Only then enable `PIE_FLEXIBLE_TEMPLATES` for the teams that need inserts.

## Validation still required in your account

These templates have been saved and expanded in a Harness sandbox. No deployment, CV analysis or approval has been executed. Before production use:

- **Happy path.** Run a successful deployment and confirm CV analysis actually ran.
- **Failure paths.** Force a deployment failure and a CV failure, then reject an approval and let one time out. Confirm rollback, and confirm no later environment deploys.
- **Promotion and recovery.** Confirm the same artifact reaches Prod, that Canary and Blue/Green candidates are reachable, and that Blue/Green rolls back after the old service is scaled down.
