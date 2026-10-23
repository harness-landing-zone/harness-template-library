# ECS delivery templates

Start with an opinionated fixed profile. The canonical source is `stages/`, `pipelines/`, `example/` and `docs/`; `check.py` validates this collection. All template references pin `0.1.0`.

| Approach | Parent template | Consumer example |
| --- | --- | --- |
| Rolling throughout | [Rolling](pipelines/rolling.yaml) | [Rolling example](example/rolling.yaml) |
| Blue/Green throughout | [Blue/Green](pipelines/blue-green_v1.yaml) | [Blue/Green example](example/blue-green.yaml) |
| Native Canary throughout | [Canary](pipelines/canary_v1.yaml) | [Canary example](example/canary.yaml) |
| Strategy variable per environment | [Variables](pipelines/variables.yaml) | [Rolling → Canary → Blue/Green](example/variables.yaml) |
| Independent stage-template selection | [Stage inserts](pipelines/stage-inserts.yaml) | [Rolling → Canary → Blue/Green inserts](example/stage-inserts.yaml) |

Every parent follows:

```text
Dev → Approve Staging → Staging → Approve Prod → Prod
```

Approvals are fixed in the parent, require one approver, disallow the pipeline executor, and abort on failure. Stage-only execution is disabled. Before registration, replace the literal `account.<APPROVED_RELEASE_GROUP>` with a real authorized group reference. This is a registration placeholder, not a runtime option; keep the minimum count and executor restriction fixed. Inject the destination organization/project scope at registration; the public YAML contains no deployment scope.

The four [stage templates](stages/) own native deployment, Continuous Verification (CV), and rollback. There are no generic status/evidence shell steps, application test inserts, or extra release-result stages.

| Strategy | Native forward flow | Verify mode |
| --- | --- | --- |
| Rolling | Rolling deploy → Verify | `Rolling` |
| Canary | Canary deploy → Verify → delete canary → full Rolling deploy | `Canary` |
| Blue/Green | Create candidate → Verify → swap target groups | `Bluegreen` |

Verify uses the Default monitored service, HIGH sensitivity, a 15-minute analysis window and a 2-hour step timeout. Failure inherits `StageRollback`. Missing monitoring or skipped analysis is a known native Verify limitation: a successful stage does not prove analysis ran. Configure the matching monitored service and health source before deployment validation. No unsupported `failOnNoAnalysis` option is added.

For fixed and variable pipelines, select the service/artifact in Dev. Staging and Prod use native `useFromStage: Dev`; their environment, infrastructure, overrides and routing inputs remain separate. Harness save, expansion and runtime-input checks accept this shape; deployment behavior is not yet validated. Stage inserts require service/artifact inputs in each slot and do not enforce release consistency across arbitrary consumer changes.

Blue/Green exposes the load balancer, production/candidate listener and rule ARNs as inputs. The swap explicitly scales the old service to zero while retaining its service definition for rollback. Native Canary is a temporary canary followed by Rolling promotion; it is not weighted traffic shifting. Compatible manifests, routing, IAM and infrastructure must already exist.

See [decisions and tradeoffs](docs/decisions.md) and [testing evidence and follow-up](docs/testing.md). From this repository run:

```sh
python3 ecs/check.py
```

The candidates are registered INLINE in a sandbox, and five comparison consumers plus a Dev-only Rolling consumer have passed save/expansion/input-shape checks. No deployment, CV analysis or approval execution was performed during consolidation. Public examples require resource and approver bindings before use.
