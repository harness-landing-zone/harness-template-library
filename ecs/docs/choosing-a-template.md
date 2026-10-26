# Choosing a template model

This library offers three ways to consume the ECS templates. This guide recommends one, compares all three, and describes how to run them across a large organisation from Git with RBAC and OPA. Statements about Harness behaviour link to the Harness Developer Hub page they come from.

## Recommendation

**Use opinionated templates by default: a fixed profile, or strategy variables where a team needs a different strategy per environment. Allow stage inserts only by exception.**

- **Harness intends pipeline templates to be closed.** Harness's guidance is to provide all parameters in the pipeline template, and notes that you "cannot customize on top of a pipeline template" ([templates best practices](https://developer.harness.io/docs/platform/templates/templates-best-practices)). Harness standardised its own deployments on a single golden pipeline template ([CD pipeline modeling](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/cd-pipeline-modeling-overview)).
- **Developers only need inputs.** Harness recommends letting developers run pipelines with input sets kept in Git, without pipeline create/edit, so every change goes through a reviewed PR ([input sets at scale](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). The opinionated templates make that possible. Stage inserts do not, because filling a slot requires pipeline edit.
- **Inserts need extra governance.** With stage inserts, a team can put almost anything in a slot or unlink the template. OPA can reject slot contents and shape changes, though not unlinking itself, and it is extra machinery to build, test and run.

Opinionated templates only work at scale with a clear way to ask for changes. When a team needs something the templates do not offer, it raises a PR or request against this library, and the platform team ships it as a new template version. Without that route, teams fall back to copying templates.

## At a glance

| | Fixed profile | Strategy variables | Stage inserts |
| --- | --- | --- | --- |
| Pipeline template | `ecs_rolling_delivery`, `ecs_canary_delivery`, `ecs_blue_green_delivery` | `ecs_variable_delivery` | `ecs_stage_insert_delivery` |
| Strategy | One for all environments | Per environment, from `rolling`, `canary`, `blue-green` | Per slot, by choice of stage template |
| What the team changes | Input set | Input set; strategy values through a reviewed PR | The pipeline file: the whole content of each slot |
| Same release promoted across environments | Yes | Yes | Not guaranteed (see cons) |
| Developer Harness permission | Execute + input sets | Execute + input sets | Pipeline Create/Edit as well |
| Extra feature flags | None | None | `PIE_FLEXIBLE_TEMPLATES`, `PIE_FLEXIBLE_TEMPLATES_PHASE2` |
| Governance effort | Low | Low | High |
| Use for | Most services | A different strategy in Prod | A reviewed need to add own stages |

## The three models

### Fixed profile

The consumer pipeline is a template reference plus runtime inputs ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling.yaml)). Service, environments and infrastructure come from an input set ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling/input_sets/environments.yaml)).

**Pros**

- **Nothing to change but inputs.** No steps, stages, failure strategies or conditions are exposed. The templates define no `allowedOverrides`, which "means nothing can be overridden" ([template overrides](https://developer.harness.io/docs/platform/templates/template-overrides)).
- **One release promoted.** The service and artifact are chosen once in Dev; Staging and Prod reuse them through `useFromStage`.
- **Simplest to run and approve.** It has the smallest graph, the easiest executions to read and the clearest approvals.
- **Least access.** Developers need no pipeline edit permission.

**Cons**

- **One strategy per pipeline.** Changing strategy means referencing a different parent template.
- **Three parents to maintain.** The three pipeline templates must be kept aligned.

### Strategy variables

One parent whose stage selects Rolling, Canary or Blue/Green from a variable per environment ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy.yaml)).

**Pros**

- **One governed graph, mixed strategies.** For example, Rolling in Dev and Blue/Green in Prod.
- **Limited choice.** The choice is restricted to `allowedValues`; developers still edit values only.
- **One release promoted.** Same as the fixed profile.

**Cons**

- **Harder-to-read executions.** The stage template carries conditional deploy, Verify and rollback branches.
- **No infrastructure behind the choice.** Choosing `blue-green` does not create listeners or target groups; the infrastructure and the routing overrides must already exist.

### Stage inserts

The parent fixes the approvals and their order. Each environment is an `insert` slot (`stages: <+input>`) that the team fills ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_stage_inserts.yaml), [insert blocks](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates)).

**Pros**

- **Most flexibility.** A different stage template per environment, or extra stages such as tests or migrations.
- **Fixed approvals.** The approvals and their position stay fixed.

**Cons**

- **Developers need pipeline edit permission,** which also lets them remove the template link.
- **A slot can hold almost anything.** Harness accepts CI, CD, Custom and Approval stages with their own failure strategies and conditional execution, and an empty slot simply runs nothing. Approvers approve whatever the slot contained.
- **Release propagation is unproven.** Harness documents that service, environment and infrastructure propagate only inside one insert block. In a sandbox test, Harness did accept a Staging or Prod slot with `useFromStage` pointing at the stage in the Dev slot (`Dev_Rolling`), stopped asking for the service there, and kept `useFromStage` in the resolved YAML. That is authoring evidence only, against the documented limitation. Until a Dev → Staging run shows the Dev artifact deployed in Staging, treat each slot as selecting its own service. Because developers own the slots, nothing stops them from selecting a different service or artifact.
- **Behind feature flags.** Inserts need feature flags, and recent release notes contain several insert-block fixes.

**Enforce policies 1–6 before enabling stage inserts for any team.**

## Operating at scale

- **Scope.** Register the golden templates at **account** scope, so every org and project references the same version (`account.<identifier>`). Use **org** scope only for business-unit variants, and keep governed templates out of project scope. Account- and org-scoped templates cannot fix a service or environment; those stay inputs, which these templates already do ([manage templates](https://developer.harness.io/docs/platform/templates/templates-best-practices#manage-templates)).
- **Ownership.** One platform team owns this library, with a named owner per template. Changes arrive as PRs against the library, are reviewed by the owners, and ship as a new version label.
- **Version lifecycle.** Consumers pin a version label. Promote teams to a new version deliberately rather than with "Always use Stable", which pushes every change to every pipeline at once. Before retiring a version, check the [template usage dashboard](https://developer.harness.io/docs/platform/templates/view-template-usage-dashboard) for pipelines still on it. Harness audits changes to the stable version with a YAML diff ([templates](https://developer.harness.io/docs/platform/templates/template)).
- **Fewer inputs through overrides.** Values that depend only on where a service is deployed belong in overrides rather than runtime inputs ([input sets at scale](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). The Blue/Green routing ARNs are therefore service variables (`<+serviceVariables.loadBalancer>` and the rest) supplied by a service-specific environment override ([overrides](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2), [example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_ecs_service/overrides.yaml)). Ideally the infrastructure automation that creates the load balancer writes these overrides.
- **Input sets per team and environment.** Keep a small number of input sets per pipeline in Git, combined with overlays where needed. Release leads review changes by PR.
- **Platform-created pipelines.** An IDP workflow or Terraform, running as a pipeline-creator service account, creates each team's consumer pipeline. Developers never need pipeline edit.

## Working from Git

| Repository | Contains | Who merges |
| --- | --- | --- |
| Template library (this repo) | `stages/`, `pipelines/`, `policies/` | Platform team |
| Application repo | `.harness/orgs/<org>/projects/<project>/pipelines/<pipeline>.yaml`, `.../pipelines/<pipeline>/input_sets/*.yaml`, `.../overrides/<env>/services/<service>/*.yaml` | Application team; platform review of pipeline files |

### Versioning

Harness supports two ways to version Git-stored templates: version labels, where Harness creates a separate file per version, or a single file managed on branches. Harness warns not to combine them ([templates best practices](https://developer.harness.io/docs/platform/templates/templates-best-practices#remote-template-versioning)).

This library uses **version labels**:

- **Why branches don't work here.** Consumers live in other repositories, and a template in a different repository from its pipeline resolves from that repository's **default branch** ([remote pipeline templates](https://developer.harness.io/docs/platform/templates/create-a-remote-pipeline-template)). Branches therefore cannot carry versions to consumers.
- **One file per version.** Each version label is its own file on the default branch (`rolling_v1.yaml` holds `0.1.0`). A new version is a new file; a merged version file is never edited.
- **Branches only for authoring.** Use branches to prepare a change and open a PR. Do not also use Git tags or release branches as a versioning scheme.

The single-file-plus-branches approach Harness also describes fits teams that keep templates and pipelines in the same repository, because there the pipeline branch must match the template branch.

### Day-to-day behaviour

- **Autocreation needs a webhook.** Files under `.harness/` on the default branch can be created in Harness automatically once a Git Experience webhook is registered. Pipelines, input sets and overrides each follow a path convention ([autocreation](https://developer.harness.io/docs/platform/git-experience/autocreation-of-entities)). Otherwise import them once.
- **Input sets sit next to the pipeline.** Each input set names its pipeline with `pipeline.identifier` ([pipeline repo](https://developer.harness.io/docs/platform/git-experience/manage-a-harness-pipeline-repo-using-git-experience)).
- **Triggers are not in Git.** Triggers are stored in Harness, not Git. Create them in Harness and point them at an input set.

### Git changes bypass Harness RBAC

A commit to `.harness/` changes the pipeline without Harness checking pipeline edit permission. Protect the files on both sides:

- **Branch protection and code owners.** Require platform review for `.harness/**/pipelines/*.yaml` and `.harness/**/overrides/**`; leave `input_sets/` to the team. Protect the library's default branch the same way.
- **OPA on Git commits.** Enable `PIPE_OPA_GITX_ENFORCEMENT` and `PIPE_ENABLE_OPA_GOVERNANCE_FOR_AUTO_CREATION`. Harness then evaluates On Save policies on direct Git commits and blocks execution when the latest commit fails ([enforce on Git entities](https://developer.harness.io/docs/platform/governance/policy-as-code/enforce-policies-on-git-backed-entities)).
- **On Run as a backstop.** Keep On Run policies enforced as well.

## Security

### Where the protection comes from

RBAC on templates protects the template itself, but not the consumer pipeline. A user with pipeline edit can choose **Remove template** or **Change template** in Pipeline Studio ([use a template](https://developer.harness.io/docs/platform/templates/use-a-template)) and then edit a plain pipeline. RBAC cannot express "edit, but keep the template link". Withholding pipeline edit and requiring Git review are what prevent unlinking. OPA is the backstop: it cannot tell an unlinked pipeline from a linked one with the same stages, but it rejects any change to the governed shape.

| Risk | Fixed / variables | Inserts | Control |
| --- | --- | --- | --- |
| Edit the template | Blocked | Blocked | RBAC on templates; library branch protection |
| Copy the template into an unlinked pipeline | Blocked | Blocked | RBAC: no `core_template_copy` |
| Remove or change the template link | Blocked without pipeline edit; possible through Git | Possible | No pipeline edit for developers; code owners on `.harness/**/pipelines/*.yaml`. OPA does not catch unlinking itself: an unlinked pipeline with unchanged stages passes |
| Change the governed shape (steps, rollback, failure strategy, approvals, stage-only runs) | Only by unlinking | Only by unlinking | Policies 1, 2, 4 and 5 |
| Arbitrary slot content | n/a | Possible | Policies 2, 3, 5, 6 |
| Remove or weaken an approval | Only by unlinking | Only by unlinking | Policies 4 and 7 |
| Redirect Blue/Green traffic | Through override files | Same | Code owners on overrides; RBAC on service edit |
| Approve one's own release | Blocked for the person who ran it | Same | Approver group excludes change authors |
| Change the policies | Blocked | Blocked | RBAC: no governance permissions for developers |

### RBAC

Permission identifiers come from the [permissions reference](https://developer.harness.io/docs/platform/role-based-access-control/permissions-reference). Bind roles through resource groups at the scope where the templates live.

| Role | Grant | Do not grant |
| --- | --- | --- |
| **Template owner** (platform; ideally a service account driven by library CI) | `core_template_view/create/edit/delete/access` | Pipeline execute in application projects |
| **Policy admin** (security) | `core_governancePolicy_*`, `core_governancePolicySets_*` | Template edit |
| **Release approver** (the group that replaces `<APPROVED_RELEASE_GROUP>`) | Pipeline view; membership of the approver user group | Pipeline or template edit; developers who author changes |
| **Infrastructure automation** (service account writing overrides) | `core_service_edit` for service-specific overrides, environment view | Pipeline edit or execute |
| **Pipeline creator** (service account used by IDP or Terraform) | `core_pipeline_create/edit`, `core_template_access` | Execute, template edit |
| **Developer, fixed/variable** | `core_pipeline_view/execute`, `core_inputset_view/edit`, `core_template_view/access`; `view` + `access` on services, environments, connectors and secrets | `core_pipeline_create/edit/delete`; `core_template_copy/create/edit/delete`; edit on services, environments, connectors and secrets |
| **Developer, inserts** | The above plus `core_pipeline_create/edit` | Same as above; only with the policies enforced |

**Production environments.** Use [ABAC](https://developer.harness.io/docs/platform/role-based-access-control/attribute-based-access-control) to split environment permissions by type (Production / Pre-Production). If developers trigger the whole pipeline they are likely to need `core_environment_access` on Production, and Prod is then protected by the approval and OPA rather than RBAC. Confirm in a sandbox how environment access is checked for the user who runs the pipeline.

### OPA policies

The policies are in [policies/](../policies/), one self-contained file each, ready to paste into Harness. Create one policy set per entity and event, with **Error and exit** ([governance overview](https://developer.harness.io/docs/platform/governance/policy-as-code/harness-governance-overview)).

| # | Policy | Entity / events | Models |
| --- | --- | --- | --- |
| 1 | [Approved pipeline template, if linked; stage-only runs disabled](../policies/1-approved-pipeline-template.rego) | Pipeline: On Save, On Run | All |
| 2 | [Approved stage templates, if linked; every Deployment stage matches an approved ECS stage shape](../policies/2-approved-stage-templates.rego) | Pipeline: On Save, On Run | All |
| 3 | [Exactly one deployment stage per insert slot; no Custom, CI or Approval stages](../policies/3-insert-slot-contents.rego) | Pipeline: On Save, On Run | Inserts |
| 4 | [Approval gates intact in the expanded payload](../policies/4-approval-gates.rego) | Pipeline: On Save, On Run | All |
| 5 | [No Ignore / MarkAsSuccess / ManualIntervention](../policies/5-no-failure-masking.rego) | Pipeline: On Save, On Run | All |
| 6 | [No production environment before Prod](../policies/6-environment-per-slot.rego) | Pipeline: On Run | All |
| 7 | [Template guardrails](../policies/7-template-guardrails.rego) | Template: On Save | All |

**Using the Helm library as well?** Policies 1 and 2 deny anything not in their approved lists, so a Helm copy would reject ECS pipelines and the reverse. Load one copy of each, with the ECS and Helm identifiers merged into `approved_parents` and `approved_stage_templates`, and the Helm stage shapes added to `approved_shapes`. Policies 3–7 name no library-specific templates and are the same in both libraries; load one copy of each.

**Shape, not just reference.** Policy 2 records each approved stage template as an ordered list of forward step types. When a stage template changes its steps in a new version, add the new shape in the same PR.

**Check the payload before enforcing:**

- **What OPA sees.** OPA receives an expanded pipeline YAML, and expressions are not resolved. Harness's resolved pipeline YAML drops `pipeline.template` and each stage's `template` block. It keeps the stages, steps and `allowStageExecutions` from the templates, and keeps insert slots as `pipeline.stages[].insert.stages[].stage`. The Harness samples read `stage.template.templateRef`, so the OPA payload may still carry references. Policies 1 and 2 therefore handle both shapes: a template reference is checked when it is present, and its absence does not deny. In the expanded shape, each Deployment stage must match an approved stage template's deployment type and ordered forward steps, keep its rollback steps, and use only `StageRollback`.
- **Policies 3, 4 and 6 handle both shapes too.**
  - **Policy 3** reads slots from either location. A slot stage passes if it has a `template` block (linked; policy 2 checks the ref) or is a Deployment stage (expanded; policy 2 checks the shape).
  - **Policy 4** checks the approval stages only in the expanded payload. In a linked payload the approvals live in the parent, which policy 1 pins to an approved version and policy 7 protects on save.
  - **Policy 6** reads the environment from the stage (expanded) or from the stage's template inputs (linked). A runtime input still unresolved in the payload (`<+input>`) matches no production identifier and passes, so confirm On Run payloads carry the chosen environment.
- **If the payload carries both.** If testing shows the OPA payload has `pipeline.template` alongside the expanded stages, re-add a strict "must be linked" rule to policy 1. Then OPA would catch unlinking as well. Policy 4 would need its `not input.pipeline.template` condition dropped, because the approvals would then be visible.
- **Test in Warn mode first.** Test each policy in the policy editor against a real pipeline of each model, adjust the paths, and run in Warn mode before switching to Error. The policies have not yet been evaluated against a Harness payload.
- **When each event runs.** Templates are evaluated On Save only, and existing templates are not re-evaluated when a policy is added ([templates](https://developer.harness.io/docs/platform/governance/policy-as-code/policy-as-code-for-templates)). Pipelines can also be evaluated On Step Start behind `PIPE_IS_PRE_STEP_OPA_POLICY_EVALUATION_ENABLED`.

## Rollout checklist

1. Register the stage templates, then the pipeline templates, at account scope as Remote templates from this repository, with the approver group set.
2. Create the roles and resource groups. Confirm a developer cannot edit, copy or delete templates.
3. Add code owners and branch protection to the library and to the application repos.
4. Load the policies in Warn mode, run each example, and fix payload paths until only intended violations remain. Then switch to Error and exit.
5. Run negative tests as a developer. Each of these must be blocked:
   - removing the template link in Pipeline Studio (blocked by missing pipeline edit, not by OPA)
   - unlinking and then changing a step, the rollback or an approval (blocked by OPA)
   - committing a changed pipeline straight to Git
   - leaving a slot empty
   - adding a shell stage to Prod
   - adding an `Ignore` failure strategy
   - targeting Prod from Dev
   - approving their own run
6. Only then enable `PIE_FLEXIBLE_TEMPLATES` for the teams that need inserts.

## Validation still required

These templates have been saved and expanded in a Harness sandbox, and Harness's own resolution confirms service propagation from Dev. The Blue/Green override wiring has not been saved in Harness yet. No deployment, CV analysis or approval has been executed. Before production use:

- **Happy path.** Run a successful deployment and confirm CV analysis actually ran.
- **Failure paths.** Force a deployment failure and a CV failure, then reject an approval and let one time out. Confirm rollback, and confirm no later environment deploys.
- **Errored promotion.** Force the Canary promotion step to end in an error. The Rolling rollback after a Canary promotion runs only for SUCCEEDED, FAILED, ABORTED, EXPIRED and ERRORED. `ERRORED` was added based on Harness's status list, which the docs show only as a screenshot, so confirm it fires.
- **Promotion and recovery.** Confirm the same artifact reaches Prod, that the routing ARNs resolve from overrides, and that Blue/Green rolls back after the old service is scaled down.
