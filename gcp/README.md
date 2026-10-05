# Generic GCP pipelines and a small test

Both pipelines and both input sets are saved in `bau_payments / GCP_Project`. Harness read-back reports valid YAML. **No build or deployment has run yet.** These are pipeline candidates; reusable templates follow execution verification.

## Run the example

Open **GCP GAR Build Scan Push** and select input set **Hello Cloud Run - build and deploy** (`hello_build_deploy`). Review before running. One run performs:

```text
Prepare tiny web page → Build → Trivy scan → Push to GAR → Resolve digest
                                                               ↓
                                                GCP Cloud Run Deploy
                                                               ↓
                                                  harness-cloudrun-test
```

The native Pipeline stage starts CD only after CI succeeds and passes registry coordinates, image tag, digest, connectors and deployment target inputs. It waits for the child pipeline; a deployment failure fails the parent. There is no separate registry webhook. Registry digest lookup uses a short-lived token from the documented Harness GCP OIDC plugin and the GAR tags API.

The [test input set](inputsets/hello-build-deploy.yaml) supplies:

| Setting | Test value |
| --- | --- |
| GAR project / location | `harness-management` / `europe-west2` |
| GAR repository / image | `gcp-test-image` / `hello-cloud-run` |
| Image tag | Pipeline-generated `build-<sequence>` |
| Harness service | `cloud_run_test`, named `harness-cloudrun-test` |
| Environment / infrastructure | `staging` / `cloud_run_test` |
| Cloud Run target | Dedicated infrastructure points to `harness-management`, `europe-west2` |
| GCP connector | `gcpproject` |
| CD execution cluster / namespace | `account.Shared_Cluster` / `default` |

The test input set disables source checkout and writes the two files in [cr-service](cr-service) into the build workspace. Its codebase fields reference the existing library repository to satisfy the generic input schema; the sample does not depend on its contents being published. Python's built-in HTTP server serves one static page on port 8080 as a non-root user. It is for testing only.

## Use another repository, registry or service

Change input sets, not pipeline code:

- Set codebase connector, repository and branch/tag/commit; enable `cloneCodebase`; replace the preparation command with `true` to use the checked-out files unchanged.
- Set `dockerfile` and `build_context` to the application's paths.
- Set GAR project, region, repository, image name and connector. Keep the OIDC lookup identity consistent with the selected connector and grant it permission to read the image tag.
- Select another Harness service, environment and infrastructure. Services must expose a `gar` GoogleArtifactRegistry artifact source with the same runtime fields as [the sample service](services/cloud-run-test.yaml). Each service owns its manifest.
- Set the Kubernetes execution connector and namespace for native Cloud Run steps.

The manifest uses `<+service.name>` and `<+artifact.image>`; service display names must already be valid Cloud Run names (lowercase letters, digits and hyphens). It does not transform names. The image and service names are independent.

Harness requires the chained pipeline reference to resolve when saving, so the child pipeline's Harness org/project/identifier remain fixed wiring. Registry and deployment choices are runtime inputs. The base-image connector is a direct step runtime input because Harness rejected an expression inside its connector list.

The [standalone CD input set](inputsets/hello-deploy.yaml), `hello_deploy`, supplies target configuration for redeploying an existing image; enter its tag and SHA256 digest. Automated CI supplies those values itself and does not load that standalone input set.

## Verification and limits

The native GAR steps use BuildX through Docker Layer Caching for OIDC. Build exports a local archive; Trivy blocks high/critical vulnerabilities; Push uploads that same archive without rebuilding. A digest lookup error also blocks CD. CI/Cloud/DLC, STO and pipeline chaining must be available in this account.

The native Basic Cloud Run deployment prepares rollback, applies the manifest and performs native instance checks. Application acceptance and rollback must still be tested. On first-deployment rollback Harness deletes the new service; subsequent rollback restores traffic to previous revisions. A maximum instance setting is not a hard spending cap.

`default` is the test execution namespace; confirm the existing cluster/delegate can run CD pods there. GAR permissions, Cloud Run permissions, default runtime service-account `actAs`, monitoring access, OIDC claim restrictions and the actual sample image scan result remain unverified.

No GCP resource has been created by these edits. Harness service/infrastructure definitions were created for the test; existing orders resources were not repurposed. The earlier orders service files are retained as historical configuration snapshots.

Run local checks:

```sh
python3 harness-template-library/gcp/check.py
```

Checks execute the sample preparation command and digest parser with mocked responses, and verify input coverage, scan gating, handoff and rollback wiring. They do not prove cloud execution.

## References

- [GAR step settings](https://developer.harness.io/continuous-integration/use-harness-ci/use-harness-ci/build-and-upload-artifacts/build-and-push/build-and-push-to-gar)
- [Build-only and push-only](https://developer.harness.io/continuous-integration/use-harness-ci/use-harness-ci/build-and-upload-artifacts/build-without-push)
- [Pipeline chaining](https://developer.harness.io/harness-platform/use-harness-platform/pipelines/pipeline-chaining)
- Local `docs/developer-hub/docs/platform/variables-and-expressions/harness-expressions-reference.md`: built-in `<+service.name>` expression.
- [GAR tag lookup](https://docs.cloud.google.com/artifact-registry/docs/reference/rest/v1/projects.locations.repositories.packages.tags/get)
