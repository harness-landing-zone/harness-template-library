# Choosing a template model

This library offers three ways to consume the Helm templates. This guide recommends one, compares all three, and describes how to run them across a large organisation from Git with RBAC and OPA. It follows the [ECS guide](../../ecs/docs/choosing-a-template.md) and says where Helm differs. Statements about Harness behaviour link to the Harness Developer Hub page they come from.

## Recommendation

**Use opinionated templates by default: a fixed profile, or strategy variables where a team needs a different strategy per environment. Allow stage inserts only by exception.**

- **Harness intends pipeline templates to be closed.** Harness's guidance is to provide all parameters in the pipeline template, and it notes that you "cannot customize on top of a pipeline template" ([templates best practices](https://developer.harness.io/docs/platform/templates/templates-best-practices)). Harness standardised its own deployments on a single golden pipeline template ([CD pipeline modeling](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/cd-pipeline-modeling-overview)).
- **Developers only need inputs.** Harness recommends letting developers run pipelines with input sets kept in Git, without pipeline create/edit, so every change goes through a reviewed PR ([input sets at scale](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). The opinionated templates make that possible. Stage inserts do not, because filling a slot requires pipeline edit.
- **Inserts need extra governance.** With stage inserts, a team can put almost anything in a slot or unlink the template. OPA can reject slot contents and shape changes, though not unlinking itself, and it is extra machinery to build, test and run.

Opinionated templates only work at scale with a clear way to ask for changes. When a team needs something the templates do not offer, it raises a PR or request against this library, and the platform team ships it as a new template version. Without that route, teams fall back to copying templates.

## Why Kubernetes with Helm charts, not Native Helm

Harness deploys Helm charts in two ways ([Helm CD quickstart](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/helm-cd-quickstart)):

| | Kubernetes + Helm chart manifest (this library) | Native Helm |
| --- | --- | --- |
| How it deploys | `helm template`, then Harness Kubernetes steps (`kubectl apply`) | `helm install` / `helm upgrade` |
| Rolling, Canary, Blue Green | All three; Harness generates the steps for each | Rolling documented; Canary and Blue Green steps exist, but the docs disagree (see below) |
| Versioning and rollback | Rolling and Canary: Harness versions the release and rolls back to the last successful version. Blue Green: not versioned; rollback swaps traffic back to the previous colour | Helm's own rollback; Harness does not version deployments |
| Helm hooks | Not supported; move hook work into Jobs | Honoured |
| Namespace validation setting | Not documented; test | Not supported for Helm Canary ([Native Helm](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/native-helm-quickstart)) |

The library uses the Kubernetes deployment type for three reasons:

- **Progressive delivery with Verify is documented end to end.** The Kubernetes [Canary](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/kubernetes-executions/create-a-kubernetes-canary-deployment) and [Blue Green](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/kubernetes-executions/create-a-kubernetes-blue-green-deployment) pages describe each step, where verification goes and how rollback works. Every stage template here uses Canary or Blue Green with a Verify step, so this is the core requirement.
- **Native Helm progressive delivery is not settled in the docs.** The Helm step reference lists `HelmCanaryDeploy` and `HelmBGDeploy` (delegate 84300+). The quickstart still lists Canary and Blue Green as "coming soon", and an FAQ says Native Helm supports only Rolling. No page shows a Native Helm Canary or Blue Green pipeline with Verify or explains its rollback. A governed template should not depend on behaviour that is described inconsistently.
- **Harness-managed rollback.** For Rolling and Canary, Harness versions the release and rolls back to the last successful version itself. Blue Green resources are not versioned; rollback routes traffic back to the previous colour ([Kubernetes rollback](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/cd-k8s-ref/kubernetes-rollback)).

The trade-off is **Helm hooks**. Harness's guidance for the Kubernetes path is to split hooks into Jobs. A chart that cannot drop its hooks needs Native Helm. That is a separate, Rolling-only template set, which this library does not include.

## At a glance

| | Fixed profile | Strategy variables | Stage inserts |
| --- | --- | --- | --- |
| Pipeline template | `helm_rolling_delivery`, `helm_canary_delivery`, `helm_blue_green_delivery` | `helm_variable_delivery` | `helm_stage_insert_delivery` |
| Strategy | One for all environments | Per environment, from `rolling`, `canary`, `blue-green` | Per slot, by choice of stage template |
| What the team changes | Input set | Input set; strategy values through a reviewed PR | The pipeline file: the whole content of each slot |
| Same release (chart version) promoted across environments | Yes | Yes | Not guaranteed (see cons) |
| Developer Harness permission | Execute + input sets | Execute + input sets | Pipeline Create/Edit as well |
| Feature flags | `PIE_FLEXIBLE_TEMPLATES`, `PIE_FLEXIBLE_TEMPLATES_PHASE2` (for the [developer test slot](#developer-functional-tests)) | Same | Same |
| Governance effort | Low | Low | High |
| Use for | Most services | A different strategy in Prod | A reviewed need to add own stages |

## The three models

### Fixed profile

The consumer pipeline is a template reference plus runtime inputs ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_rolling.yaml)). Service, environments and infrastructure come from an input set ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_rolling/input_sets/environments.yaml)).

**Pros**

- **Nothing to change but inputs and test steps.** Apart from the [developer test slot](#developer-functional-tests), no steps, stages, failure strategies or conditions are exposed. The templates define no `allowedOverrides`, which "means nothing can be overridden" ([template overrides](https://developer.harness.io/docs/platform/templates/template-overrides)).
- **One release promoted.** The service and chart version are chosen once in Dev; Staging and Prod reuse them through `useFromStage`.
- **Simplest to run and approve.** It has the smallest graph, the easiest executions to read and the clearest approvals.
- **Least access.** Developers need no pipeline edit permission.

**Cons**

- **One strategy per pipeline.** Changing strategy means referencing a different parent template.
- **Three parents to maintain.** The three pipeline templates must be kept aligned.

### Strategy variables

One parent whose stage selects Rolling, Canary or Blue Green from a variable per environment ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_variable_strategy.yaml)).

**Pros**

- **One governed graph, mixed strategies.** For example, Rolling in Dev and Blue Green in Prod.
- **Limited choice.** The choice is restricted to `allowedValues`; developers still edit values only.
- **One release promoted.** Same as the fixed profile.
- **No extra inputs for Blue Green.** Unlike ECS, Kubernetes Blue Green takes its routing from the Services in the chart, so no strategy adds inputs or overrides.

**Cons**

- **Harder-to-read executions.** The stage template carries conditional deploy, Verify and rollback branches.
- **The chart must suit every strategy offered.** Canary and Blue Green accept exactly one `Deployment`, and Blue Green needs a `Service` ([supported workloads](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/kubernetes-executions/create-a-kubernetes-blue-green-deployment)). Picking `blue-green` for a chart without a Service fails at deploy time.
- **Switching strategy can hit immutable selectors.** Kubernetes label selectors are immutable. Harness adds `harness.io/track: stable` to the selector, so switching an environment between Canary and Rolling can fail with an "Invalid value: LabelSelector ... field is immutable" error. Harness recommends a forced fresh deployment when switching, or the **Disable addition of Harness track selector in Kubernetes deployments** setting ([Helm FAQ, switching deployment types](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/helm-deployment-faqs), [skip track selector](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/cd-kubernetes-category/skip-harness-label-selector-tracking-on-kubernetes-deployments)).
  - **Recommendation:** enable that setting in every project that uses strategy variables, before the first deployment there. Harness stops adding the label to the selector of new objects, but still adds it to pods for traffic routing. It does not remove the label from objects that already have it, so for those, plan a forced fresh deployment.
  - **Blue Green to another strategy:** this leaves the blue/green Deployments and the stage Service in the namespace. Treat that switch as a planned migration, not a value edit.

### Stage inserts

The parent fixes the approvals and their order. Each environment is an `insert` slot (`stages: <+input>`) that the team fills ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_stage_inserts.yaml), [insert blocks](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates)).

**Pros**

- **Most flexibility.** A different stage template per environment, or extra stages such as tests or migrations. For Helm this is also where a Native Helm stage could go for a chart that needs hooks, if you decide to allow it.
- **Fixed approvals.** The approvals and their position stay fixed.

**Cons**

- **Developers need pipeline edit permission,** which also lets them remove the template link.
- **A slot can hold almost anything.** Harness accepts CI, CD, Custom and Approval stages with their own failure strategies and conditional execution, and an empty slot simply runs nothing. Approvers approve whatever the slot contained.
- **Release propagation is unproven.** Harness documents that service, environment and infrastructure propagate only inside one insert block. A sandbox test of the ECS library points the other way: Harness accepted a Staging or Prod slot with `useFromStage` pointing at the stage in the Dev slot, stopped asking for the service there, and kept `useFromStage` in the resolved YAML. That is authoring evidence only, against the documented limitation, and it has not been tested for Helm. Until a Dev → Staging run shows the Dev chart version deployed in Staging, treat each slot as selecting its own service. The chart version is a runtime input of the service, and developers own the slots, so nothing stops a slot from deploying a different chart version than the one tested in Dev.
- **Behind feature flags.** Inserts need feature flags, and recent release notes contain several insert-block fixes.

**Enforce policies 1–6 and 8 before enabling stage inserts for any team.**

## Developer functional tests

Every stage template has one step insert, `Developer_Functional_Test`, where the team adds its own tests ([insert blocks](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates)). It is the same slot as in the ECS library. It sits after Verify and before anything that is hard to undo:

| Strategy | Forward flow |
| --- | --- |
| Rolling | Rolling deployment → Verify → **developer tests** |
| Canary | Canary deployment → Verify → **developer tests** → Canary Delete → Primary rolling deployment |
| Blue Green | Stage deployment → Verify → **developer tests** → swap primary and stage services |

- **Optional.** An empty slot runs nothing, and the stage carries on. To leave it empty, keep `steps: <+input>` in the pipeline and supply nothing at run time; in the ECS sandbox, Harness rejected `steps: []` when the pipeline was saved ("there must be a minimum of 1 items"). The Harness docs don't cover this case.
- **A failing test rolls back the stage,** like any other failure. For Blue Green and Canary that happens before live traffic moves.
- **What to test:** Blue Green tests reach the candidate through the `-stage` Service Harness creates, for example through a `candidateHealthUrl` service variable set by the environment's override, such as `http://<stage service>.<namespace>.svc.cluster.local/<path>`. The test step runs on the delegate, so the delegate must reach that address ([example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_blue_green.yaml), [override](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_helm_service/overrides.yaml)).
- **Where the tests live:** in the consumer pipeline file, under each stage's `templateInputs`, changed by PR and reviewed by code owners. Harness requires pipeline create/edit to supply insert content as a runtime input ([insert RBAC](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates#rbac-required)), so keeping tests in Git lets developers stay without pipeline edit in Harness.
- **Limits:**
  - **Tests only:** policy 8 rejects step types starting with `Ecs`, `K8s`, `Helm`, `Terraform`, `Terragrunt` or `IACM`. Other families, such as CloudFormation, ARM, Lambda, ASG or SSH `Command`, aren't covered unless you add them to its list.
  - **No failure masking:** policy 5 rejects `Ignore`, `MarkAsSuccess` and `ManualIntervention`.
  - **No nesting:** Harness doesn't allow nested inserts or a stage insert in parallel with other stages ([limitations](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates#limitations)).
- **Feature flags:** the slot needs `PIE_FLEXIBLE_TEMPLATES` and `PIE_FLEXIBLE_TEMPLATES_PHASE2` for every model, not only stage inserts.
- **Not yet tested for Helm.** The slot is copied from the ECS library and has not been saved or run in Harness for Helm.

## Operating at scale

- **Scope.** Register the golden templates at **account** scope, so every org and project references the same version (`account.<identifier>`). The pipeline templates reference their stage templates the same way (`account.helm_rolling_stage`). Use **org** scope only for business-unit variants, and keep governed templates out of project scope. Account- and org-scoped templates cannot fix a service or environment; those stay inputs, which these templates already do ([manage templates](https://developer.harness.io/docs/platform/templates/templates-best-practices#manage-templates)).
- **Ownership.** One platform team owns this library, with a named owner per template. Changes arrive as PRs against the library, are reviewed by the owners, and ship as a new version label.
- **Version lifecycle.** Consumers pin a version label. Promote teams to a new version deliberately rather than with "Always use Stable", which pushes every change to every pipeline at once. Before retiring a version, check the [template usage dashboard](https://developer.harness.io/docs/platform/templates/view-template-usage-dashboard) for pipelines still on it.
- **Fewer inputs through overrides.** Values that depend only on where a service is deployed belong in overrides rather than runtime inputs ([input sets at scale](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). For Helm these are chart values, not step inputs. A service-specific environment override adds a values file for that environment and service variables ([overrides](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2), [example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_helm_service/overrides.yaml)). The values file reads them as `<+serviceVariables.*>`, because values files can use Harness expressions ([deploy Helm charts](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/deploy-helm-charts), [example](../examples/deploy/values/prod.yaml)). Override priority is service & infrastructure, then infrastructure, then service, then global environment. Namespaces live in the infrastructure definition, not in values.
- **Chart version as the release.** The service keeps `chartVersion` as a runtime input. A [Helm chart trigger](https://developer.harness.io/docs/platform/triggers/trigger-pipelines-on-new-helm-chart) can supply it with `<+trigger.manifest.version>`. Do not leave it blank in an input set, because Harness then fails the run rather than picking the latest version ([Helm FAQ](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/helm-deployment-faqs)).
- **Input sets per team and environment.** Keep a small number of input sets per pipeline in Git, combined with overlays where needed. Release leads review changes by PR.
- **Platform-created pipelines.** An IDP workflow or Terraform, running as a pipeline-creator service account, creates each team's consumer pipeline. Developers never need pipeline edit.

## Working from Git

| Repository | Contains | Who merges |
| --- | --- | --- |
| Template library (this repo) | `stages/`, `pipelines/`, `policies/` | Platform team |
| Application repo | `.harness/orgs/<org>/projects/<project>/pipelines/<pipeline>.yaml`, `.../pipelines/<pipeline>/input_sets/*.yaml`, `.../services/<service>.yaml`, `.../overrides/<env>/services/<service>/*.yaml`, chart values files | Application team; platform review of pipeline, service and override files |

### Versioning

Harness supports two ways to version Git-stored templates: version labels, where Harness creates a separate file per version, or a single file managed on branches. Harness warns not to combine them ([templates best practices](https://developer.harness.io/docs/platform/templates/templates-best-practices#remote-template-versioning)).

This library uses **version labels**:

- **Why branches don't work here.** Consumers live in other repositories, and a template in a different repository from its pipeline resolves from that repository's **default branch** ([remote pipeline templates](https://developer.harness.io/docs/platform/templates/create-a-remote-pipeline-template)). Branches therefore cannot carry versions to consumers.
- **One file per version.** Each version label is its own file on the default branch (`rolling_v1.yaml` holds `0.1.0`). A new version is a new file; a merged version file is never edited.
- **Branches only for authoring.** Use branches to prepare a change and open a PR. Do not also use Git tags or release branches as a versioning scheme.

Chart versions are separate from template versions. The chart is versioned in its Helm repository and chosen per run; the template version changes only when the delivery process changes.

### Day-to-day behaviour

- **Autocreation needs a webhook.** Files under `.harness/` on the default branch can be created in Harness automatically once a Git Experience webhook is registered. Pipelines, input sets, services and overrides each follow a path convention ([autocreation](https://developer.harness.io/docs/platform/git-experience/autocreation-of-entities)). Otherwise import them once.
- **Remote overrides need remote entities.** An override can be stored in Git only if its environment is in Git, and for a service-specific override, the service too ([overrides](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#manage-overrides-using-git-experience)).
- **Input sets sit next to the pipeline.** Each input set names its pipeline with `pipeline.identifier` ([pipeline repo](https://developer.harness.io/docs/platform/git-experience/manage-a-harness-pipeline-repo-using-git-experience)).
- **Triggers are not in Git.** Triggers are stored in Harness, not Git. Create them in Harness and point them at an input set.

### Git changes bypass Harness RBAC

A commit to `.harness/` changes the pipeline without Harness checking pipeline edit permission. Protect the files on both sides:

- **Branch protection and code owners.** Require platform review for `.harness/**/pipelines/*.yaml`, `.harness/**/services/**` and `.harness/**/overrides/**`; leave `input_sets/` to the team. Decide deliberately who owns Prod values files. They change what runs in Prod without a template change. Protect the library's default branch the same way.
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
| Deploy, swap or change infrastructure from the test slot | Through the pipeline file | Same | Policy 8; code owners on pipeline files |
| Change Prod chart values | Through override and values files | Same | Code owners on overrides and values; RBAC on service edit |
| Deploy outside the approved namespace | Through chart templates or values | Same | Code owners on charts, values and override files; namespace validation setting only once tested (see below) |
| Approve one's own release | Blocked for the person who ran it | Same | Approver group excludes change authors |
| Change the policies | Blocked | Blocked | RBAC: no governance permissions for developers |

**Namespace validation.** A Helm chart can set its own namespace in templates or values. Harness can fail any deployment whose resources target a namespace other than the infrastructure's. Turn on **Enable Namespace validation from different sources with infrastructure level namespace** in Default Settings, which needs delegate 856xx or later ([Native Helm, enforcing namespace consistency](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/helm/native-helm-quickstart#enforcing-namespace-consistency)). Harness documents this setting only on the Native Helm page, so its effect on Kubernetes deployments of Helm charts is not documented. Test it in a sandbox with a chart that hardcodes another namespace. Until that test passes, the control is review: code owners on the chart, values files and override files, so no namespace change reaches the default branch unreviewed. OPA cannot help here, because the namespace comes from the rendered chart, which is not in the pipeline payload.

### RBAC

Permission identifiers come from the [permissions reference](https://developer.harness.io/docs/platform/role-based-access-control/permissions-reference). Bind roles through resource groups at the scope where the templates live.

| Role | Grant | Do not grant |
| --- | --- | --- |
| **Template owner** (platform; ideally a service account driven by library CI) | `core_template_view/create/edit/delete/access` | Pipeline execute in application projects |
| **Policy admin** (security) | `core_governancePolicy_*`, `core_governancePolicySets_*` | Template edit |
| **Release approver** (`helm_release_approvers`, the group named by each pipeline template's `release_approver_group` variable) | Pipeline view; membership of the approver user group | Pipeline or template edit; developers who author changes |
| **Service owner** (team lead or platform; writes services and service-specific overrides) | `core_service_edit`, environment view | Pipeline edit or execute |
| **Pipeline creator** (service account used by IDP or Terraform) | `core_pipeline_create/edit`, `core_template_access` | Execute, template edit |
| **Developer, fixed/variable** | `core_pipeline_view/execute`, `core_inputset_view/edit`, `core_template_view/access`; `view` + `access` on services, environments, connectors and secrets | `core_pipeline_create/edit/delete`; `core_template_copy/create/edit/delete`; edit on services, environments, connectors and secrets |
| **Developer, inserts** | The above plus `core_pipeline_create/edit` | Same as above; only with the policies enforced |

Service-specific overrides need **Service: Create/Edit**, and global environment or infrastructure-specific overrides need **Environment: Create/Edit** ([overrides](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#permissions)). Keep both away from developers if Prod values must be reviewed.

**Production environments.** Use [ABAC](https://developer.harness.io/docs/platform/role-based-access-control/attribute-based-access-control) to split environment permissions by type (Production / Pre-Production). If developers trigger the whole pipeline they are likely to need `core_environment_access` on Production, and Prod is then protected by the approval and OPA rather than RBAC. Confirm in a sandbox how environment access is checked for the user who runs the pipeline.

### OPA policies

The policies are in [policies/](../policies/), one self-contained file each, ready to paste into Harness. Create one policy set per entity and event, with **Error and exit** ([governance overview](https://developer.harness.io/docs/platform/governance/policy-as-code/harness-governance-overview)).

| # | Policy | Entity / events | Models |
| --- | --- | --- | --- |
| 1 | [Approved pipeline template, if linked; stage-only runs disabled](../policies/1-approved-pipeline-template.rego) | Pipeline: On Save, On Run | All |
| 2 | [Approved stage templates, if linked; every Deployment stage matches an approved Helm stage shape, ignoring the test slot](../policies/2-approved-stage-templates.rego) | Pipeline: On Save, On Run | All |
| 3 | [Exactly one deployment stage per insert slot; no Custom, CI or Approval stages](../policies/3-insert-slot-contents.rego) | Pipeline: On Save, On Run | Inserts |
| 4 | [Approval gates intact in the expanded payload](../policies/4-approval-gates.rego) | Pipeline: On Save, On Run | All |
| 5 | [No Ignore / MarkAsSuccess / ManualIntervention](../policies/5-no-failure-masking.rego) | Pipeline: On Save, On Run | All |
| 6 | [No production environment before Prod](../policies/6-environment-per-slot.rego) | Pipeline: On Run | All |
| 7 | [Template guardrails](../policies/7-template-guardrails.rego) | Template: On Save | All |
| 8 | [`Developer_Functional_Test` rejects `Ecs*`, `K8s*`, `Helm*`, `Terraform*`, `Terragrunt*` and `IACM*` steps](../policies/8-developer-test-insert.rego) | Pipeline: On Save, On Run | All |

**Using the ECS library as well?** Policies 1 and 2 deny anything not in their approved lists, so an ECS copy would reject Helm pipelines and the reverse. Load one copy of each, with the ECS and Helm identifiers merged into `approved_parents` and `approved_stage_templates`, and the ECS stage shapes added to `approved_shapes`. Policies 3–8 name no library-specific templates and are the same in both libraries; load one copy of each.

**Shape, not just reference.** Policy 2 records each approved stage template as an ordered list of forward step types. When a stage template changes its steps in a new version, add the new shape in the same PR.

**Check the payload before enforcing:**

- **What OPA sees.** OPA receives an expanded pipeline YAML, and expressions are not resolved. Harness's resolved pipeline YAML drops `pipeline.template` and each stage's `template` block. It keeps the stages, steps and `allowStageExecutions` from the templates, and keeps insert slots as `pipeline.stages[].insert.stages[].stage`. The Harness samples read `stage.template.templateRef`, so the OPA payload may still carry references. Policies 1 and 2 therefore handle both shapes: a template reference is checked when it is present, and its absence does not deny. In the expanded shape, each Deployment stage must match an approved stage template's deployment type and ordered forward steps, keep its rollback steps, and use only `StageRollback`.
- **Policies 3, 4 and 6 handle both shapes too.**
  - **Policy 3** reads slots from either location. A slot stage passes if it has a `template` block (linked; policy 2 checks the ref) or is a Deployment stage (expanded; policy 2 checks the shape).
  - **Policy 4** checks the approval stages only in the expanded payload. In a linked payload the approvals live in the parent, which policy 1 pins to an approved version and policy 7 protects on save. The Helm approvals name their group as `<+pipeline.variables.release_approver_group>`, so policy 4 accepts that expression when the pipeline's `release_approver_group` variable holds the approver group, as well as a literal group list (the ECS form). Policy 7 rejects a template whose `release_approver_group` is a runtime input or expression.
  - **Policy 6** reads the environment from the stage (expanded) or from the stage's template inputs (linked). A runtime input still unresolved in the payload (`<+input>`) matches no production identifier and passes, so confirm On Run payloads carry the chosen environment.
- **If the payload carries both.** If testing shows the OPA payload has `pipeline.template` alongside the expanded stages, re-add a strict "must be linked" rule to policy 1. Then OPA would catch unlinking as well. Policy 4 would need its `not input.pipeline.template` condition dropped, because the approvals would then be visible.
- **Test in Warn mode first.** Test each policy in the policy editor against a real pipeline of each model, adjust the paths, and run in Warn mode before switching to Error. The policies have not yet been evaluated against a Harness payload.
- **When each event runs.** Templates are evaluated On Save only, and existing templates are not re-evaluated when a policy is added ([templates](https://developer.harness.io/docs/platform/governance/policy-as-code/policy-as-code-for-templates)). Pipelines can also be evaluated On Step Start behind `PIPE_IS_PRE_STEP_OPA_POLICY_EVALUATION_ENABLED`.

## Rollout checklist

1. Register the stage templates, then the pipeline templates, at account scope as Remote templates from this repository, with the approver group set.
2. Create the Kubernetes connector, infrastructure definitions, services with Helm chart manifests, and per-environment overrides.
3. Create the roles and resource groups. Confirm a developer cannot edit, copy or delete templates, services or overrides.
4. Add code owners and branch protection to the library and to the application repos.
5. Load the policies in Warn mode, run each example, and fix payload paths until only intended violations remain. Then switch to Error and exit.
6. Run negative tests as a developer. Each of these must be blocked:
   - removing the template link in Pipeline Studio (blocked by missing pipeline edit, not by OPA)
   - unlinking and then changing a step, the rollback or an approval (blocked by OPA)
   - committing a changed pipeline straight to Git
   - leaving a slot empty
   - adding a shell stage to Prod
   - adding an `Ignore` failure strategy
   - adding a deployment step to the test slot
   - targeting Prod from Dev
   - approving their own run
   - deploying a chart that sets a different namespace
7. Only then enable `PIE_FLEXIBLE_TEMPLATES` for the teams that need inserts.

## Validation still required

All nine templates have been saved in a Harness sandbox (project scope, inline), and Harness reported each one valid. A consumer pipeline for each model also saved and expanded. Harness's resolution shows the Kubernetes steps, rollback guards and stage conditions as written, and `useFromStage: Dev` in Staging and Prod. The runtime inputs Harness derives match the example input sets: Staging and Prod ask only for environment and infrastructure, while each insert slot asks for its own service. The `ERRORED` clause in the rollback guards was added after that save, so the sandbox copies of the Canary, Blue Green and variable strategy stages are one change behind this repo. Since then the stage references gained the `account.` prefix, the approvers moved to the `release_approver_group` variable, and the Blue Green Verify step became `Verify_BlueGreen`. Those three changes are registered at account scope (inline, `0.1.0`), and Harness reported each template valid. The developer test slot came later and has not been saved in Harness. No service, override, deployment, CV analysis or approval has been executed. Before production use:

- **Happy path.** Run a successful deployment of each strategy and confirm CV analysis actually ran.
- **Failure paths.** Force a deployment failure and a CV failure in each strategy, then reject an approval and let one time out. Confirm rollback, and confirm no later environment deploys. In particular:
  - Blue Green: a Verify failure must leave production traffic on the old colour, with the rollback swap skipped.
  - Canary: a canary failure must delete the canary and leave the primary untouched.
  - Errored steps: the rollback guards accept `ERRORED` as well as `SUCCEEDED`, `FAILED`, `ABORTED` and `EXPIRED`. Force a runtime error in the primary rolling deployment and in the Blue Green swap (not a failure), and confirm the guarded rollback step runs.
- **Promotion and overrides.** Confirm the same chart version reaches Prod, and that the Prod override's values file and `<+serviceVariables.*>` resolve in the rendered manifest.
