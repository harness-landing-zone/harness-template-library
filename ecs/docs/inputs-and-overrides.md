# Inputs, input sets and overrides

How a value reaches a step in the ECS templates, who can change it, and what to watch for. Written for platform engineers who run the library and for application engineers who consume it.

Statements about Harness behaviour link to the Harness Developer Hub page and line they come from. Statements about this library point to its files. **Status:** the templates and examples are saved in a Harness sandbox, but nothing has been executed yet. Items marked *unverified* still need a sandbox run.

## In short

- **Teams choose targets, not behaviour.** A team picks the service, environments, infrastructure and artifact tag. Steps, Verify, rollback, failure strategy and approvals are fixed in the templates.
- **Service and artifact are chosen once, in Dev.** Staging and Prod reuse them through `useFromStage: Dev`, so their input sets carry only an environment and an infrastructure.
- **Day-to-day values live in input sets.** The artifact tag is the exception: it is entered at run time or supplied by a trigger.
- **Where-it-runs values live in overrides.** Blue/Green routing is resolved from the environment and service at run time. It is never typed in, and developers cannot change it.
- **Tests and strategy live in the consumer pipeline file.** Changing them needs a pull request (PR) with code-owner review, not Harness pipeline edit.
- **Anything else needs a new template version.** Nothing in the library can be overridden by a caller.

## How a value reaches a step

```text
 PLATFORM (library repo)                       APPLICATION TEAM (app repo)              RUN TIME
 ─────────────────────────────                 ───────────────────────────              ─────────────────────
 Stage template                                Consumer pipeline file                   Run form or trigger
   fixed: steps, Verify, rollback,               keeps <+input>, or fixes a value:        artifact tag
          failure strategy                         Developer_Functional_Test steps        anything still <+input>
   <+input>: service, environment,                 strategy per environment
             infrastructure, test slot             (variables model)
   reads <+serviceVariables.*>                            │
        │                                                 ▼
        ▼                                      Input set(s) / overlay
 Pipeline template                               Dev: service, environment, infra
   fixed: approvals, order, conditions,          Staging, Prod: environment, infra
          useFromStage: Dev (Staging, Prod)
   passes through: Dev service, every
          environment/infra, the test slot
                                                                 │
 SERVICE + OVERRIDES (Harness entities, owned by whoever owns the load balancer)
   service declares variables (defaults)  ──►  override for <environment, service> replaces them
                                                 ──►  <+serviceVariables.prodListenerArn> etc. at run time
```

A value set at one layer cannot be changed by a later layer. Once a field is fixed, it is no longer a runtime input, and Harness only accepts input set values for fields that are runtime inputs ([input-sets.md:71](https://developer.harness.io/docs/platform/pipelines/input-sets), [:118](https://developer.harness.io/docs/platform/pipelines/input-sets)).

## Who changes what, where

| Value | Declared in | Set in | Who | How it changes |
| --- | --- | --- | --- | --- |
| Steps, Verify, rollback, failure strategy | [Stage templates](../stages/) | Fixed | Platform | PR to the library, new version |
| Approvals, approver group, stage order and conditions | [Pipeline templates](../pipelines/) | Fixed | Platform | PR to the library, new version |
| Strategy (fixed profile) | Choice of parent template | Consumer pipeline `templateRef` | App team + platform review | PR to the app repo |
| Strategy per environment (variables model) | `ecs_variable_delivery` variables, `<+input>.default(rolling).allowedValues(...)` | Consumer pipeline file | App team + platform review | PR to the app repo |
| Service | Stage template `serviceRef: <+input>` | Dev stage in the input set | App team | PR to `input_sets/` |
| Service in Staging and Prod | Pipeline template `useFromStage: Dev` | Fixed | Nobody | — |
| Artifact tag | Service artifact `tag: <+input>`, through Dev `serviceInputs` | Run form or trigger | Person running it, or the trigger | Per run |
| Environment and infrastructure | Stage template `<+input>` | Every stage in the input set | App team | PR to `input_sets/` |
| Developer tests | Insert slot `Developer_Functional_Test`, `steps: <+input>` | Consumer pipeline file | App team + platform review | PR to the app repo |
| Blue/Green routing, `candidateHealthUrl` | Service variables, empty by default | Service-specific environment override | Load-balancer owner or infrastructure automation | PR to `overrides/`, or the automation |
| Anything else | — | — | — | Request a new template version |

## The layers, one by one

### 1. Stage template (platform)

The stage templates fix the execution and leave the deployment targets open. From [rolling_v1.yaml](../stages/rolling_v1.yaml):

```yaml
      environment:
        environmentRef: <+input>
        deployToAll: false
        environmentInputs: <+input>
        serviceOverrideInputs: <+input>
        infrastructureDefinitions: <+input>
      service:
        serviceRef: <+input>
        serviceInputs: <+input>
      execution:
        steps:
        # ... Rolling deploy and Verify, fixed ...
        - insert:
            name: Developer Functional Test
            identifier: Developer_Functional_Test
            steps: <+input>
```

`environmentInputs` and `serviceOverrideInputs` pass through any runtime inputs that the environment or an override declares. The library itself declares none.

The Blue/Green stage does not take routing as input. It reads routing from service variables ([blue-green_v1.yaml](../stages/blue-green_v1.yaml)):

```yaml
            type: EcsBlueGreenCreateService
            spec:
              loadBalancer: <+serviceVariables.loadBalancer>
              prodListener: <+serviceVariables.prodListenerArn>
              prodListenerRuleArn: <+serviceVariables.prodListenerRuleArn>
              stageListener: <+serviceVariables.candidateListenerArn>
              stageListenerRuleArn: <+serviceVariables.candidateListenerRuleArn>
```

The variable strategy stage limits the choice with a default and an allowed list ([variable-strategy_v1.yaml](../stages/variable-strategy_v1.yaml)):

```yaml
    variables:
      - name: deploymentStrategy
        type: String
        required: true
        value: <+input>.default(rolling).allowedValues(rolling,canary,blue-green)
```

What this means in practice:

- **A default in a template is final.** A parent cannot change a default set in a template, unless the input also has `.executionInput()` or the parent supplies a fixed value or expression ([runtime-input-usage.md:158-164](https://developer.harness.io/docs/platform/variables-and-expressions/runtime-input-usage#default-values-in-templates)). The pipeline template supplies an expression, which is allowed.
- **Allowed values are checked only when a value is given.** `required: true` stops the value from being left empty ([runtime-input-usage.md:179](https://developer.harness.io/docs/platform/variables-and-expressions/runtime-input-usage#set-allowed-values)).
- **`.allowedValues()` is deprecated** in favour of `.selectOneFrom()`. Editing the input in Pipeline Studio rewrites the YAML to the new form ([runtime-input-usage.md:214-223](https://developer.harness.io/docs/platform/variables-and-expressions/runtime-input-usage#set-allowed-values)). Edit templates in Git so that the diffs stay clean.

### 2. Pipeline template (platform)

The pipeline template decides which stage inputs reach the consumer. In Staging and Prod, it replaces the service input with a fixed reference to Dev ([blue-green_v1.yaml](../pipelines/blue-green_v1.yaml)):

```yaml
    - stage:
        name: Staging
        identifier: Staging
        template:
          templateRef: ecs_blue_green_stage
          versionLabel: 0.1.0
          templateInputs:
            type: Deployment
            spec:
              service:
                useFromStage:
                  stage: Dev
              environment:
                environmentRef: <+input>
                environmentInputs: <+input>
                serviceOverrideInputs: <+input>
                infrastructureDefinitions: <+input>
              execution:
                steps:
                - insert:
                    identifier: Developer_Functional_Test
                    steps: <+input>
```

In the variables model, the parent lifts each stage's strategy to a pipeline variable ([variables_v1.yaml](../pipelines/variables_v1.yaml)):

```yaml
    variables:
    - name: devDeploymentStrategy
      type: String
      required: true
      value: <+input>.default(rolling).allowedValues(rolling,canary,blue-green)
    # ... stagingDeploymentStrategy, prodDeploymentStrategy ...
          templateInputs:
            # ...
            variables:
            - name: deploymentStrategy
              type: String
              value: <+pipeline.variables.devDeploymentStrategy>
```

A parent may list only a subset of a child's allowed values ([reconcile-pipeline-templates.md:135](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates)). To add a strategy, add it to the stage template first, then to the pipeline template.

### 3. Consumer pipeline (application team, platform review)

The consumer pipeline is a template reference plus the remaining inputs. A team either leaves an input as `<+input>` or fixes it here. Two inputs are fixed here on purpose, because they change how a release is tested or deployed:

- **The strategy per environment.** From [ecs_variable_strategy.yaml](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy.yaml):

  ```yaml
      templateInputs:
        variables:
        - name: devDeploymentStrategy
          type: String
          value: rolling
        - name: stagingDeploymentStrategy
          type: String
          value: canary
        - name: prodDeploymentStrategy
          type: String
          value: blue-green
  ```

- **The developer tests.** From [ecs_blue_green.yaml](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_blue_green.yaml):

  ```yaml
                  execution:
                    steps:
                    - insert:
                        identifier: Developer_Functional_Test
                        steps:
                        - step:
                            name: Candidate health check
                            identifier: Candidate_Health_Check
                            type: Http
                            timeout: 2m
                            spec:
                              url: <+serviceVariables.candidateHealthUrl>
                              method: GET
                              headers: []
                              assertion: <+httpResponseCode> == 200
                              outputVariables: []
  ```

Once a value is fixed here, an input set or the run form can no longer change it. Every change becomes a PR on the pipeline file, which code owners review.

### 4. Input sets and overlays (application team)

An input set stores values for the remaining runtime inputs. The library's examples use one input set per pipeline, covering all three environments. From [ecs_rolling/input_sets/environments.yaml](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_rolling/input_sets/environments.yaml):

```yaml
inputSet:
  name: Environments
  identifier: environments
  pipeline:
    identifier: ecs_rolling
    template:
      templateInputs:
        stages:
        - stage:
            identifier: Dev
            template:
              templateInputs:
                type: Deployment
                spec:
                  service:
                    serviceRef: my_ecs_service
                  environment:
                    environmentRef: dev
                    infrastructureDefinitions:
                    - identifier: dev_ecs
        - stage:
            identifier: Staging
            template:
              templateInputs:
                type: Deployment
                spec:
                  environment:            # no service: Staging uses Dev's
                    environmentRef: staging
                    infrastructureDefinitions:
                    - identifier: staging_ecs
        # Prod: same shape as Staging
```

**What an input set can hold**

- **Runtime inputs only.** An input set holds values for runtime inputs and nothing else ([input-sets.md:71](https://developer.harness.io/docs/platform/pipelines/input-sets#specify-settings-that-use-runtime-input), [:118](https://developer.harness.io/docs/platform/pipelines/input-sets)). In this library that means the Dev service, each stage's environment and infrastructure, and any slot or strategy the consumer pipeline left as `<+input>`.
- **Partial values.** An input set doesn't have to fill every input ([input-sets.md:120](https://developer.harness.io/docs/platform/pipelines/input-sets)). Harness recommends a partly filled input set when some inputs can be fixed ([manage-inputsets-at-scale.md:32](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). The examples deliberately leave out `serviceInputs`, so the artifact tag is still asked for at run time.
- **Missing required values.** If a required input still has no value, the run form shows an error until someone fills it in ([input-sets.md:309-314](https://developer.harness.io/docs/platform/pipelines/input-sets#value-resolution)).

**Overlays**

- An overlay combines input sets in order, and the last value set wins ([input-sets.md:232-234](https://developer.harness.io/docs/platform/pipelines/input-sets#priority-in-overlays)).
- A typical layout is one shared set plus one set per environment, or one set per team. Harness describes teams with one input set per environment ([manage-inputsets-at-scale.md:49](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)).
- Keep the Dev service in the same input set as the Staging and Prod bindings. Harness says stages linked by service propagation must use the same input set ([propagate-and-override-cd-services.md:28](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/services/propagate-and-override-cd-services)). *Unverified:* whether an overlay that spreads the stages across several input sets counts as "the same input set".

**Git**

- Input sets sit in `pipelines/<pipeline>/input_sets/` next to the pipeline and change by PR, which release leads review ([manage-inputsets-at-scale.md:51](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)).
- An input set in the pipeline's repository is read from the branch that runs. One in another repository is read from that repository's default branch, unless a trigger sets `inputSetBranchName` ([input-sets.md:384-387](https://developer.harness.io/docs/platform/pipelines/input-sets#default-branch-resolution)).

**RBAC**

- **Without the input set feature flag**, creating an input set needs **Pipeline: Create/Edit** ([input-sets.md:65](https://developer.harness.io/docs/platform/pipelines/input-sets#before-you-begin)).
- **With the feature flag.** `PIE_INPUTSET_RBAC_PERMISSIONS` gives input sets their own View, Create/Edit and Delete permissions. Harness Support runs a migration (`CDS_INPUT_SET_MIGRATION`) before enabling it ([input-sets.md:250-252](https://developer.harness.io/docs/platform/pipelines/input-sets#manage-access-to-input-sets)).
- **Running with an input set** needs View on the input set and Execute on the pipeline. Changing one needs input set Create/Edit ([input-sets.md:263-274](https://developer.harness.io/docs/platform/pipelines/input-sets#input-set-permissions); permission `core_inputset_edit`, [permissions-reference.md:143](https://developer.harness.io/docs/platform/role-based-access-control/permissions-reference)).
- **Execute without edit.** Harness recommends giving developers execute and access to their services and environments, but not pipeline create/edit, so that changes go through Git ([manage-inputsets-at-scale.md:63-65](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). The library's developer role follows this, and it depends on `PIE_INPUTSET_RBAC_PERMISSIONS`.

**Can an input set carry the developer tests?**

The slot is a runtime input (`steps: <+input>`), so in principle an input set can hold it. But Harness says that supplying steps to an insert block as a runtime input in the pipeline needs **Pipeline: Create/Edit** ([inject-step-stage-templates.md:279](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates#rbac-required)). The docs don't say whether that check also applies to an input set that carries the steps, or to the user who runs with one. *Unverified.* Until a sandbox test shows otherwise, assume a developer without pipeline edit can neither save nor use an input set that fills the test slot. That is why the library keeps tests in the consumer pipeline file.

### 5. Run time and triggers

**Artifact tag.** The service leaves the tag open (`tag: <+input>` on `ECS_Service_One`), and only the Dev stage exposes `serviceInputs`. The sandbox pipeline `ecs_dev_rolling_cv_validation` shows the path to it:

```yaml
            service:
              serviceRef: ECS_Service_One
              serviceInputs:
                serviceDefinition:
                  type: ECS
                  spec:
                    artifacts:
                      primary:
                        sources:
                        - identifier: ecr_image
                          type: Ecr
                          spec:
                            tag: '60'
```

- **Use a concrete tag.** For example `60`, or `<+trigger.artifact.build>` from an artifact trigger ([trigger-on-a-new-artifact.md:151, :159](https://developer.harness.io/docs/platform/triggers/trigger-on-a-new-artifact)). Avoid `<+lastPublished.tag>`: propagation copies the service configuration, not the resolved artifact, so that expression is evaluated again in Staging and Prod and can pick a newer image ([propagate-and-override-cd-services.md:30](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/services/propagate-and-override-cd-services)).
- **Triggers take an input set or explicit values, not both.** A trigger can still change single fields with `inputYaml`, which takes precedence over the input set ([input-sets.md:284](https://developer.harness.io/docs/platform/pipelines/input-sets#run-pipelines-with-input-sets-or-overlays), [customize_trigger_input_configuration_using_override_yaml.md:135](https://developer.harness.io/docs/platform/triggers/customize_trigger_input_configuration_using_override_yaml)). A typical trigger references `environments` and supplies only the tag. Triggers are stored in Harness, not Git.
- **Reruns reuse inputs.** A rerun "From Last Failed Stage" reuses the earlier inputs, and changes made before the rerun are ignored ([input-sets.md:570](https://developer.harness.io/docs/platform/pipelines/input-sets)).

## Overrides (Overrides V2)

Overrides V2 is behind `CDS_SERVICE_OVERRIDES_2_0` and is described as beta ([overrides-v2.md:9](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2)). Overrides can be defined at project, org and account scope ([overrides-v2.md:15](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2)).

### Types, priority and permissions

| Priority | Override type | YAML `type` | Applies to | Permission needed |
| --- | --- | --- | --- | --- |
| 1 (wins) | Service & Infrastructure Specific | `INFRA_SERVICE_OVERRIDE` | One service on one infrastructure | Service: Create/Edit |
| 2 | Infrastructure Specific | `INFRA_GLOBAL_OVERRIDE` | All services on one infrastructure | Environment: Create/Edit |
| 3 | Service Specific | `ENV_SERVICE_OVERRIDE` | One service in one environment | Service: Create/Edit |
| 4 | Global Environment | `ENV_GLOBAL_OVERRIDE` | All services in one environment | Environment: Create/Edit |
| — | The service's own variables | — | Default when no override sets the variable | Service: Create/Edit |

Sources: priority [overrides-v2.md:163-170](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-priority) and permissions [overrides-v2.md:23-30](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#permissions). Across scopes, project beats org, which beats account ([overrides-v2.md:175-179](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-priority)).

- **Whole values.** A variable override replaces the whole value ([overrides-v2.md:122](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-types)). `<+serviceVariables.NAME>` resolves to the value that wins ([overrides-v2.md:124](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-types)).
- **No runtime inputs at infrastructure level.** Infrastructure Specific and Service & Infrastructure Specific variables don't support runtime inputs ([overrides-v2.md:34](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#limitations)). The library uses no runtime inputs in overrides.

### Service variables vs overrides

The **service** declares the variable and its default. The **override** supplies the value for one environment, and the template only ever reads `<+serviceVariables.*>`. In the sandbox, `ECS_Service_One` declares the routing variables with empty defaults:

```yaml
service:
  identifier: ECS_Service_One
  serviceDefinition:
    type: ECS
    spec:
      variables:
      # ...
      - name: loadBalancer
        type: String
        value: ''
      - name: prodListenerArn
        type: String
        value: ''
      - name: prodListenerRuleArn
        type: String
        value: ''
      - name: candidateListenerArn
        type: String
        value: ''
      - name: candidateListenerRuleArn
        type: String
        value: ''
      - name: candidateHealthUrl
        type: String
        value: ''
```

The library's [Prod override example](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/overrides/prod/services/my_ecs_service/overrides.yaml) fills them for one environment and service:

```yaml
overrides:
  identifier: prod_my_ecs_service
  environmentRef: prod
  serviceRef: my_ecs_service
  type: ENV_SERVICE_OVERRIDE
  spec:
    variables:
    - name: loadBalancer
      type: String
      value: <PROD_LOAD_BALANCER_ARN>
    - name: prodListenerArn
      type: String
      value: <PROD_LIVE_LISTENER_ARN>
    # ... prodListenerRuleArn, candidateListenerArn, candidateListenerRuleArn, candidateHealthUrl
```

Each stage resolves its own environment's override. Staging uses the service propagated from Dev, but takes the Staging override for it.

**What the sandbox does today.** The routing values reach the stage in two places, and only one of them could be read:

- **Environment variables.** The Dev and Prod environments carry the routing values as environment variables that reference IaCM workspace outputs (Staging was not checked). From `experian_app1_prod`:

  ```yaml
  environment:
    identifier: experian_app1_prod
    type: Production
    variables:
    - name: loadBalancer
      type: String
      value: <+workspace.ecs_app1_prod.alb_name>
    - name: prodListenerArn
      type: String
      value: <+workspace.ecs_app1_prod.prod_listener_arn>
    - name: prodListenerRuleArn
      type: String
      value: <+workspace.ecs_app1_prod.prod_listener_rule_arn>
    - name: candidateListenerArn
      type: String
      value: <+workspace.ecs_app1_prod.stage_listener_arn>
    - name: candidateListenerRuleArn
      type: String
      value: <+workspace.ecs_app1_prod.stage_listener_rule_arn>
    # ... liveHealthUrl ...
    - name: candidateHealthUrl
      type: String
      value: <+workspace.ecs_app1_prod.candidate_health_url>
  ```

  Environment configuration overrides service variables with the same name ([environment-overview.md:334-349](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/environments/environment-overview#override-priority)). Under Overrides V2, however, environment variables belong in Global Environment overrides ([overrides-v2.md:39](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#important-notes)).
- **An override for the service.** Each of `experian_app1_dev`, `_staging` and `_prod` also lists an override for `ECS_Service_One`. Its type and body could not be read through the API used for this review.

Pick one place, the service-specific override, so there is one owner and one value per environment.

### What happens when an override is missing

- **The values come back empty.** The service's empty defaults win, so `EcsBlueGreenCreateService` receives empty strings for the load balancer and listener values. The Blue/Green test step calls an empty URL.
- **Nothing warns before the run.** Overrides are not runtime inputs, so the run form doesn't ask for them, and `required: true` on a service variable doesn't help.
- **Where it fails.** *Unverified:* where exactly the run fails. Expect the Blue/Green step to fail, which triggers stage rollback.
- **Mitigation.** Treat "an override exists for every Blue/Green environment" as an onboarding check. A future template version could add a guard step that fails fast when a routing variable is empty.

The same applies to an override value that references an IaCM output that doesn't exist yet (see below).

### Why routing moved from runtime inputs to overrides

- **It depends only on where the service runs.** Harness recommends overrides for inputs that are tied to the deployment target ([manage-inputsets-at-scale.md:24](https://developer.harness.io/docs/continuous-delivery/cd-onboarding/new-user/manage-inputsets-at-scale)). It is the same for every release of that service in that environment.
- **Developers can't redirect traffic.** As runtime inputs, any listener ARN could be typed into the run form or an input set. As overrides, they need Service: Create/Edit, which developers don't have.
- **Fewer inputs, fewer mistakes.** Five ARNs per environment would otherwise sit in every input set.

### Who owns overrides

- **RBAC.** Service-specific overrides need Service: Create/Edit; Global Environment and Infrastructure overrides need Environment: Create/Edit ([overrides-v2.md:23-30](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#permissions)). Grant these to the load-balancer owner or to an infrastructure-automation service account, not to developers. The library's RBAC table already does this.
- **Git.** Put code owners on `.harness/**/overrides/**`. A commit there changes production routing.

### Overrides in Git

- **Inline or remote.** Overrides are stored inline in Harness or remotely in Git ([overrides-v2.md:183-187](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#manage-overrides-using-git-experience)).
- **Git needs remote parents.** An override can move to Git only if its environment is in Git. A service-specific override also needs a remote service, and an infrastructure-specific override a remote infrastructure ([overrides-v2.md:210-212](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#moving-overrides-from-inline-to-remote)). In the sandbox, `ECS_Service_One` and the three environments are inline, so their overrides can only be inline.
- **Path convention.** The project-level path for autocreation is `.harness/orgs/<org>/projects/<project>/overrides/<env>/services/<service>/overrides.yaml` ([autocreation-of-entities.md:356](https://developer.harness.io/docs/platform/git-experience/autocreation-of-entities)). The library example follows it.
- **Migration from V1.** Overrides migrated from V1 remote environments become inline ([overrides-v2.md:42](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#important-notes)).

### Referencing IaCM outputs

- **The syntax.** An IaCM workspace output can be referenced as `<+workspace.<workspace_id>.<output>>` from "any pipeline that is being created in the scope of the project where the Workspace is defined" ([output-variables.md:18-19](https://developer.harness.io/docs/infra-as-code-management/reports-insights/output-variables)).
- **Resolved per run.** The value is resolved at run time and can differ between executions ([output-variables.md:24-25](https://developer.harness.io/docs/infra-as-code-management/reports-insights/output-variables)). An IaCM apply can therefore change routing without any change in Harness.
- **Untested in overrides.** The docs describe pipeline use only. *Unverified:* whether the expression resolves inside an override or environment variable value. The sandbox wires it that way, but it hasn't run.
- **Project scope only.** Keep such overrides at project scope, next to the workspace.
- **Check the workspace has outputs.** The Dev workspace `ecs_app1_dev` has the expected outputs, for example `alb_arn`, `alb_name`, `prod_listener_arn`, `prod_listener_rule_arn`, `stage_listener_arn`, `stage_listener_rule_arn` and `candidate_health_url`. The Prod workspace `ecs_app1_prod` returned no outputs when it was read for this review. A Prod Blue/Green run today would therefore get empty values.

**Load balancer name or ARN?** The Harness Blue/Green example sets `loadBalancer: my-app-elb`, a name, while the listener and rule fields are ARNs ([traffic-shifting.md:262-264](https://developer.harness.io/docs/continuous-delivery/deploy-srv-diff-platforms/aws/ecs/traffic-shifting)). The sandbox uses the `alb_name` output, and the library example's placeholder says `<PROD_LOAD_BALANCER_ARN>`. Confirm which one the step accepts in the first Blue/Green run.

## Template-level flexibility

### Template overrides: not used

Harness can let callers override selected advanced settings of a template:

- **How it works.** The template lists them in `allowedOverrides`, and the caller supplies `templateOverrides` next to `templateInputs`. The feature is behind `PIPE_TEMPLATE_OVERRIDES` ([template-overrides.md:28, :55-58](https://developer.harness.io/docs/platform/templates/template-overrides)).
- **What can be overridden.** The overridable settings are conditional execution, looping, execution strategy, failure strategy, policy enforcement, delegate selectors and a few pipeline-level settings ([template-overrides.md:230-240](https://developer.harness.io/docs/platform/templates/template-overrides#supported-settings-by-template-type)). A pipeline template can only expose pipeline-level settings, not those of its stages ([template-overrides.md:242](https://developer.harness.io/docs/platform/templates/template-overrides#supported-settings-by-template-type)).
- **The library allows none.** No template defines `allowedOverrides`, and an empty or absent list "means nothing can be overridden" ([template-overrides.md:55](https://developer.harness.io/docs/platform/templates/template-overrides#how-template-overrides-work)). [Policy 7](../policies/7-template-guardrails.rego) rejects any template that adds one. The settings it could open (failure strategy, conditions) are exactly the ones the library keeps fixed.
- **The unofficial workaround is caught.** Putting a setting next to the `template` block still works in the YAML editor, but Harness discourages it and plans to block it ([template-overrides.md:255-256](https://developer.harness.io/docs/platform/templates/template-overrides)). Policies 2 and 5 reject the result.

### What is fixed in each model

| | Fixed profile | Strategy variables | Stage inserts |
| --- | --- | --- | --- |
| Steps, Verify, rollback, failure strategy | Fixed | Fixed (conditional per strategy) | Fixed per stage template the team picks |
| Strategy | Fixed by parent | One of `rolling`, `canary`, `blue-green` per environment, in the pipeline file | Team picks a stage template per slot |
| Approvals and order | Fixed | Fixed | Fixed |
| Service in Staging and Prod | From Dev | From Dev | Chosen per slot by the team |
| Test slot | Pipeline file | Pipeline file | Pipeline file |
| Who needs pipeline edit | Nobody (PR only) | Nobody (PR only) | Developers |

### Getting something new

1. Raise a PR or request against this library.
2. The platform team adds a **new version file**, for example `rolling_v2.yaml` with `versionLabel: 0.2.0`. A released file is never edited.
3. In the same PR, update the policies: [policy 1](../policies/1-approved-pipeline-template.rego) `approved_versions`, and the [policy 2](../policies/2-approved-stage-templates.rego) shapes if the steps change.
4. Teams move by changing `versionLabel` in their pipeline file, by PR, and reconciling (see the checklist below).

Harness's position is that a pipeline template should carry all its parameters and "cannot customize on top" ([templates-best-practices.md:316](https://developer.harness.io/docs/platform/templates/templates-best-practices)). The PR route is what keeps that workable.

## Things to consider

**Test slot**

- [ ] **Don't write `steps: []`.** Harness rejects it when the pipeline is saved. To leave the slot empty, keep `steps: <+input>` and supply nothing. The compiled YAML then shows the slot as empty without failing ([inject-step-stage-templates.md:257](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates)).
- [ ] **An empty slot used to fail.** Pipeline service 1.175.1 fixed an empty insert step being marked as failed ([pipeline release notes, pipeline-releases.md:280](https://developer.harness.io/release-notes/pipeline)). Self-managed installs need that version or later.
- [ ] **Slot limits.** The slot's content can't be the output of a step. Inserts can't be nested and can't sit in parallel with other stages ([inject-step-stage-templates.md:260-262](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates#limitations)).
- [ ] **A slot left `<+input>` is open at run time.** Anyone with pipeline edit can supply steps when they run, without a PR. Policies 5 and 8 still check On Run. Fixing the tests in the pipeline file closes this.

**Overrides**

- [ ] **A missing override gives empty ARNs.** Check that every Blue/Green environment has a service-specific override with all five routing variables and `candidateHealthUrl`.
- [ ] **One place per value.** Don't keep routing both as environment variables and in a service-specific override, as the sandbox does today.
- [ ] **IaCM outputs must exist.** Applied workspaces only: `ecs_app1_prod` showed no outputs. Values can change between runs.

**Service propagation**

- [ ] **Staging and Prod input sets carry no service.** No `service`, `serviceRef` or `serviceInputs` for Staging or Prod: those fields are not runtime inputs there, so Harness doesn't accept them in an input set ([input-sets.md:118](https://developer.harness.io/docs/platform/pipelines/input-sets)).
- [ ] **Keep the service and later stages in one input set** ([propagate-and-override-cd-services.md:28](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/services/propagate-and-override-cd-services)).
- [ ] **Use a concrete artifact tag**, not `<+lastPublished.tag>` ([propagate-and-override-cd-services.md:30](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/services/propagate-and-override-cd-services)).
- [ ] **No stage-only runs.** A stage that uses a propagated service doesn't work when run on its own ([propagate-and-override-cd-services.md:20-22](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/services/propagate-and-override-cd-services)). The templates disable stage-only runs anyway.

**OPA**

- [ ] **Unresolved inputs pass.** A runtime input still unresolved in the payload (`<+input>`) matches no production identifier, so [policy 6](../policies/6-environment-per-slot.rego) passes it. Confirm the On Run payload carries the chosen environment before relying on policy 6.
- [ ] **Policies see expressions, not values.** OPA never sees override values, so it can't check routing ARNs.

**After a template change**

- [ ] **Reconcile.** When a template adds, removes or retypes a runtime input, Harness flags referencing pipelines for reconciliation ([reconcile-pipeline-templates.md:12](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates), [templates-best-practices.md:744-752](https://developer.harness.io/docs/platform/templates/templates-best-practices#reconciliation)). For a remote pipeline, each reconciliation is a commit ([reconcile-pipeline-templates.md:132](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates)).
- [ ] **An unreconciled pipeline still runs.** It runs on the current template content, and new inputs are missing from the run form or passed as null, without a warning ([reconcile-pipeline-templates.md:428-433](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates#best-practices)).
- [ ] **Bulk reconciliation.** It is behind `PIPE_BULK_RECONCILIATION` ([reconcile-pipeline-templates.md:215](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates#bulk-reconciliation-of-templates)). For remote entities it also needs `PIPE_BULK_RECONCILIATION_PHASE2`, and it opens PRs ([reconcile-pipeline-templates.md:312-315](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates)).
- [ ] **Edit the consumer pipeline to match.** Its `<+input>` placeholders must mirror the template's. Copy the new shape from the updated example files rather than hand-editing.
- [ ] **Recheck input sets.** *Unverified:* what Harness does with an input set that sets a field the new version no longer exposes. Re-run each input set after a version bump.
- [ ] **Avoid "Always use Stable".** It pushes every change to every pipeline at once ([templates-best-practices.md:522](https://developer.harness.io/docs/platform/templates/templates-best-practices)). Pin version labels.

**Scope**

- [ ] **Templates at account scope, everything else in the project.** Account and org templates can't fix a service or environment, which is why they stay inputs ([templates-best-practices.md:488-496](https://developer.harness.io/docs/platform/templates/templates-best-practices)). Services, environments, infrastructure, overrides and IaCM workspaces stay in the project.
- [ ] **Override scope.** A project override beats an org or account override for the same target ([overrides-v2.md:175-179](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-priority)).
- [ ] **Policy lists must match the scope prefix.** [Policy 1](../policies/1-approved-pipeline-template.rego) approves `account.ecs_*` references. The sandbox registers the templates at project scope (`templateRef: ecs_blue_green_delivery`), so the policy would reject the sandbox pipelines unless its list is changed.

**Feature flags**

| Flag | Needed for | Status in this library |
| --- | --- | --- |
| `CDS_SERVICE_OVERRIDES_2_0` | Overrides V2 ([overrides-v2.md:9](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2)) | Required (routing overrides) |
| `PIE_FLEXIBLE_TEMPLATES`, `PIE_FLEXIBLE_TEMPLATES_PHASE2` | Insert blocks ([inject-step-stage-templates.md:8](https://developer.harness.io/docs/platform/templates/inject-step-stage-templates)) | Required (test slot, every model) |
| `PIE_INPUTSET_RBAC_PERMISSIONS` (after `CDS_INPUT_SET_MIGRATION`) | Input set permissions separate from pipeline edit ([input-sets.md:250-252](https://developer.harness.io/docs/platform/pipelines/input-sets#manage-access-to-input-sets)) | Required for the developer role |
| `PIPE_BULK_RECONCILIATION`, `PIPE_BULK_RECONCILIATION_PHASE2` | Bulk reconciliation, and for remote entities ([reconcile-pipeline-templates.md:215, :315](https://developer.harness.io/docs/platform/templates/reconcile-pipeline-templates#bulk-reconciliation-of-templates)) | Recommended at scale |
| `PIPE_TEMPLATE_OVERRIDES` | `allowedOverrides` ([template-overrides.md:28](https://developer.harness.io/docs/platform/templates/template-overrides)) | Not used; policy 7 forbids it |
| `PIPE_OPA_GITX_ENFORCEMENT`, `PIPE_ENABLE_OPA_GOVERNANCE_FOR_AUTO_CREATION` | OPA on Git commits (see [Choosing a template model](choosing-a-template.md#git-changes-bypass-harness-rbac)) | Recommended |

**Other**

- [ ] **Blank values.** Harness treats blank inputs differently with and without input sets. "Save Blank Fields as Empty String" makes this consistent ([input-sets.md:123](https://developer.harness.io/docs/platform/pipelines/input-sets)).
- [ ] **Null doesn't fall back to the default.** An expression that resolves to null is not replaced by the default ([runtime-input-usage.md:95](https://developer.harness.io/docs/platform/variables-and-expressions/runtime-input-usage#null-values-are-valid-values)).
- [ ] **No commas in pipeline names.** Harness rejects them, so the example name `My ECS Service - Rolling, Canary, Blue Green` in [ecs_variable_strategy.yaml](../examples/.harness/orgs/ORG_ID/projects/PROJECT_ID/pipelines/ecs_variable_strategy.yaml) won't import as is. This was observed while registering the Helm examples.
- [ ] **One service definition per strategy.** `ECS_Service_One` points at a Blue/Green ECS service definition (`servicedef-blue-green.yaml`). A Rolling or Canary stage for the same service may need a different one. The Harness list of overridable manifest types doesn't include ECS task or service definitions ([overrides-v2.md:102](https://developer.harness.io/docs/continuous-delivery/x-platform-cd-features/overrides-v2#override-types)). Yet the sandbox pipeline `ecs_dev_rolling_cv_validation` is described as using a "scoped Rolling manifest override". *Unverified:* how that override is built. Confirm it before mixing strategies for one service in the variables model.

## Not verified yet

These points need a sandbox run before production use:

- **Insert steps in input sets.** Whether an input set can carry `Developer_Functional_Test` steps for a user who has execute and input set edit but no pipeline edit.
- **IaCM outputs in overrides.** Whether `<+workspace.<id>.<output>>` resolves inside an override or environment variable value.
- **The sandbox override.** What the service-specific overrides on `ECS_Service_One` contain, and which wins over the environment variables in the sandbox.
- **Missing overrides.** How a Blue/Green stage fails when an override is missing or resolves to empty.
- **Load balancer field.** Whether `loadBalancer` takes the name or the ARN.
- **Overlays and propagation.** Whether propagation still resolves when the stages' bindings come from different input sets in an overlay.
- **Input sets after a version bump.** What happens to input sets after a template version adds or removes inputs.
