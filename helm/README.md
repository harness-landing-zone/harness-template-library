# Helm delivery templates

A Harness template library for deploying Helm charts to Kubernetes through Dev → Staging → Prod with mandatory approvals, Continuous Verification (CV) and native rollback. The platform team owns the templates; application teams consume them from their own Git repositories.

**Recommended model:** use the opinionated templates (a fixed profile, or strategy variables) so developers only change input sets in Git. Allow stage inserts only by exception. [Choosing a template model](docs/choosing-a-template.md) explains why, compares the models, and covers the Git workflow, RBAC and OPA.

## How Helm is deployed

The stage templates use `deploymentType: Kubernetes` with a **Helm chart manifest** in the service. Harness fetches the chart, runs `helm template`, and deploys the rendered manifests with its own Rolling, Canary or Blue Green steps. Harness calls this "Helm charts managed by Harness"; Native Helm (`deploymentType: NativeHelm`) is the alternative, where Harness runs `helm install`/`helm upgrade`. [Why not Native Helm](docs/choosing-a-template.md#why-kubernetes-with-helm-charts-not-native-helm) gives the reasons. In short:

- **All three strategies are documented end to end** for Kubernetes, including the Verify step between deploy and promote. For Native Helm, Harness's own pages disagree on whether Canary and Blue Green are supported, and none show a working pipeline.
- **Harness manages rollback.** For Rolling and Canary, Harness versions the release and rolls back to the last successful version. Blue Green resources are not versioned; rollback swaps traffic back to the previous colour.
- **The cost: Helm hooks are not run.** Charts that depend on hooks must move that work into Jobs, or stay on Native Helm (not covered by this library).

## Contents

| Folder | Owner | What it holds |
| --- | --- | --- |
| [stages/](stages/) | Platform | Stage templates: Kubernetes deployment of a Helm chart, Verify and rollback for one strategy |
| [pipelines/](pipelines/) | Platform | Pipeline templates: Dev → Approve Staging → Staging → Approve Prod → Prod |
| [policies/](policies/) | Platform / security | OPA policies, one Rego file each |
| [examples/](examples/) | Application team | Consumer pipelines, input sets, a service and an override as they would sit in an application repo |

### Templates

| Template | Identifier | Kind |
| --- | --- | --- |
| [Rolling stage](stages/rolling_v1.yaml) | `helm_rolling_stage` | Stage |
| [Canary stage](stages/canary_v1.yaml) | `helm_canary_stage` | Stage |
| [Blue Green stage](stages/blue-green_v1.yaml) | `helm_blue_green_stage` | Stage |
| [Variable strategy stage](stages/variable-strategy_v1.yaml) | `helm_variable_strategy_stage` | Stage |
| [Rolling delivery](pipelines/rolling_v1.yaml) | `helm_rolling_delivery` | Pipeline, fixed profile |
| [Canary delivery](pipelines/canary_v1.yaml) | `helm_canary_delivery` | Pipeline, fixed profile |
| [Blue Green delivery](pipelines/blue-green_v1.yaml) | `helm_blue_green_delivery` | Pipeline, fixed profile |
| [Variable delivery](pipelines/variables_v1.yaml) | `helm_variable_delivery` | Pipeline, strategy per environment |
| [Stage insert delivery](pipelines/stage-inserts_v1.yaml) | `helm_stage_insert_delivery` | Pipeline, developer-filled slots |

All templates are version `0.1.0`. Each version label is its own file (`*_v1.yaml` holds `0.1.0`); see [Versioning](docs/choosing-a-template.md#versioning).

### Examples

The examples use the Harness Git Experience layout (`.harness/orgs/<org>/projects/<project>/...`). With a Git Experience webhook configured, Harness can import files in this layout automatically. Replace `ORG_ID`, `PROJECT_ID`, `my_helm_service`, the environment and infrastructure identifiers and the `<...>` placeholders with your own values.

| Combination | Consumer pipeline | Input set |
| --- | --- | --- |
| Rolling everywhere | [helm_rolling.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_rolling.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_rolling/input_sets/environments.yaml) |
| Canary everywhere | [helm_canary.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_canary.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_canary/input_sets/environments.yaml) |
| Blue Green everywhere | [helm_blue_green.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_blue_green.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_blue_green/input_sets/environments.yaml) |
| Rolling → Canary → Blue Green by variable | [helm_variable_strategy.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_variable_strategy.yaml) | [environments.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_variable_strategy/input_sets/environments.yaml) |
| Rolling → Canary → Blue Green by stage insert | [helm_stage_inserts.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/helm_stage_inserts.yaml) | Bindings live in the pipeline file, which the team owns in this model |

Supporting files:

- **Service:** [my_helm_service.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/services/my_helm_service.yaml) is a Kubernetes service with a Helm chart manifest. The chart version is a runtime input.
- **Override:** [overrides.yaml](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_helm_service/overrides.yaml) is a service-specific environment override for Prod. It adds a Prod values file and service variables.
- **Values file:** [deploy/values/prod.yaml](examples/deploy/values/prod.yaml) is the Prod values file, which reads those variables as `<+serviceVariables.*>`.

In the fixed and variable models, the pipeline file is little more than a template reference. The team's day-to-day changes go into the input set; per-environment chart values go into overrides. The chart version stays a runtime input, so a Helm chart trigger or the person running the pipeline supplies it.

## What every pipeline enforces

- **Approvals before Staging and Prod.** Each needs one approver from the release group, the person who ran the pipeline cannot approve, and a rejection or timeout aborts the run. Approvers are fixed in the template and are never runtime inputs: every approval reads the pipeline template's fixed variable `release_approver_group`.
- **No stage-only runs.** Stage-only execution is disabled, so nobody can run Prod on its own.
- **No later environment after a failure.** In the fixed and variable models, Staging and Prod run only if every earlier stage and approval succeeded.
- **One release promoted across environments.** In the fixed and variable models, the service and chart version are chosen once in Dev; Staging and Prod reuse them (`useFromStage: Dev`).

## What the stage templates do

| Strategy | Forward flow | Verify mode | Rollback |
| --- | --- | --- | --- |
| Rolling | Rolling deployment → Verify → developer tests | `Rolling` | Rolling Rollback |
| Canary | Canary deployment (1 pod) → Verify → developer tests → Canary Delete → Primary rolling deployment | `Canary` | Canary Delete; Rolling Rollback if the primary deployment started |
| Blue Green | Stage deployment → Verify → developer tests → swap primary and stage services | `Bluegreen` | Swap back if the forward swap started |

- **Verify:** uses the Default monitored service, HIGH sensitivity, a 15-minute analysis window and a 2-hour timeout.
- **Developer tests:** every stage has an optional `Developer_Functional_Test` step insert after Verify. The team adds its tests in the consumer pipeline file; an empty slot is skipped, and a failing test rolls the stage back before traffic moves. See [Developer functional tests](docs/choosing-a-template.md#developer-functional-tests).
- **Failure:** any failure rolls back the stage. No step can be ignored or marked as successful.
- **Canary:** this is Harness Kubernetes Canary: one extra canary pod next to the current release, verified, deleted, then a full rolling update. It is not weighted traffic shifting.
- **Blue Green:** the previous colour keeps running after the swap, so rollback is a selector swap. Expect double capacity per service; the templates do not scale down the old colour, because doing so would slow rollback.
- **Pruning is off** (`pruningEnabled: false`). Resources removed from the chart are not deleted from the cluster.

## Chart requirements

- **Canary and Blue Green:** exactly one Kubernetes `Deployment` in the chart. Rolling manages `Deployment`, `DaemonSet` and CRD workloads; other workloads, such as Jobs, are not managed ([what can I deploy](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/kubernetes/cd-k8s-ref/what-can-i-deploy-in-kubernetes)). Other objects in the chart can be applied unmanaged with the `harness.io/direct-apply: "true"` annotation.
- **Blue Green:** the chart needs a Kubernetes `Service`. With one Service, Harness creates the `-stage` copy itself. With two, annotate them `harness.io/primary-service: "true"` and `harness.io/stage-service: "true"`.
- **No reliance on Helm hooks.** Harness does not run them with this deployment type.

## Before first use

1. **Register the templates.** Register the stage templates first, then the pipeline templates, at account scope as Remote templates from this repository. The pipeline templates reference their stage templates as `account.helm_*_stage`, so the stage templates must exist at account scope first.
2. **Set the approver group.** Approvals go to the account user group `helm_release_approvers`. Add its members, who must not be the people authoring the releases. To use another group, change it in two places: the `release_approver_group` variable of each pipeline template in [pipelines/](pipelines/) (one line per file), and `approval_group` in [policies/4-approval-gates.rego](policies/4-approval-gates.rego).
3. **Prepare Kubernetes.** Create a Kubernetes connector and one infrastructure definition per environment with its namespace. Keep the default release name (`release-<+INFRA_KEY_SHORT_ID>`), which Harness uses to track the resources of each release. The templates do not create clusters, namespaces or connectors.
4. **Prepare the service.** Use a Kubernetes service with a Helm chart manifest, like the [example](examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/services/my_helm_service.yaml), and put per-environment values in overrides.
5. **Prepare monitoring.** For each service, configure a monitored service and health source for each environment. Verify can be skipped when no monitoring is configured, so a green stage alone does not prove analysis ran.
6. **Apply governance.** Put the RBAC roles and [OPA policies](policies/) from the guide in place before giving teams access, and especially before enabling stage inserts.
