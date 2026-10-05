# Generic GCP pipelines and a small test

Both pipelines and both input sets are saved in `bau_payments / GCP_Project`. Harness read-back reports valid YAML. **No build or deployment has run yet.** These are pipeline candidates; reusable templates follow execution verification.

## Run the example

Open **GCP GAR Build Scan Push** and select input set **Hello Cloud Run - build and push** (`hello_build_deploy`). Review before running. One run performs:

```text
Checkout → Gitleaks → Checkov → Build → Trivy → Push to GAR
```

CI stops after push. Build triggers and automatic CD chaining are deferred until the two pipelines have been tested separately. Gitleaks scans the latest commit with redacted output; it is not a full-history audit. Checkov scans the build-context directory for Dockerfile/IaC issues. Each scan blocks high/critical findings.

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

The test input set checks out `harness-template-library` on `main`, builds `gcp/cr-service/Dockerfile` with context `gcp/cr-service`, and pushes `hello-cloud-run`. Python's built-in HTTP server serves one static page on port 8080 as a non-root user. It is for testing only.


## Use another repository, registry or service

Change input sets, not pipeline code:

- Set codebase connector, repository and branch/tag/commit; keep `cloneCodebase` enabled for source scans.
- Set `dockerfile` and `build_context` to the application's paths.
- Set GAR project, region, repository, image name and connector.
- Select another Harness service, environment and infrastructure. Services must expose a `gar` GoogleArtifactRegistry artifact source with the same runtime fields as [the sample service](services/cloud-run-test.yaml). The sample service also exposes a Git-backed `cloud_run` manifest; CD supplies its connector, repository, path and commit through runtime inputs.
- Set the Kubernetes execution connector and namespace for native Cloud Run steps.

The manifest uses `<+service.name>` and `<+artifact.image>`; service display names must already be valid Cloud Run names (lowercase letters, digits and hyphens). It does not transform names. The image and service names are independent.

The base-image connector is a direct step runtime input because Harness rejected an expression inside its connector list.

After CI succeeds, run **GCP Cloud Run Deploy** with the [CD input set](inputsets/hello-deploy.yaml), `hello_deploy`. Supply the pushed `build-<sequence>` tag, its GAR SHA256 digest, and the Git commit from that CI execution. The manifest uses that exact commit. CD targets `harness-cloudrun-test` in `harness-management / europe-west2`; the first successful deployment should create the GCP service. The Harness service definition alone does not create a GCP resource.


## Verification and limits

The native GAR steps use BuildX through Docker Layer Caching for OIDC. Build exports a local archive; Trivy blocks high/critical vulnerabilities; Push uploads that same archive without rebuilding. CI/Cloud/DLC and STO must be available in this account.

The native Basic Cloud Run deployment prepares rollback, applies the manifest and performs native instance checks. Application acceptance and rollback must still be tested. On first-deployment rollback Harness deletes the new service; subsequent rollback restores traffic to previous revisions. A maximum instance setting is not a hard spending cap.

`default` is the test execution namespace; confirm the existing cluster/delegate can run CD pods there. GAR permissions, Cloud Run permissions, default runtime service-account `actAs`, monitoring access, OIDC claim restrictions and the actual sample image scan result remain unverified.

No GCP resource has been created by these edits. Harness service/infrastructure definitions were created for the test; existing orders resources were not repurposed. The earlier orders service files are retained as historical configuration snapshots.

Run local checks:

```sh
python3 harness-template-library/gcp/check.py
```

Checks verify input coverage, source paths, scan gating, the shared image archive, Git manifest configuration and rollback wiring. They do not prove cloud execution.

## References

- [GAR step settings](https://developer.harness.io/continuous-integration/use-harness-ci/use-harness-ci/build-and-upload-artifacts/build-and-push/build-and-push-to-gar)
- [Build-only and push-only](https://developer.harness.io/continuous-integration/use-harness-ci/use-harness-ci/build-and-upload-artifacts/build-without-push)
- [Pipeline chaining](https://developer.harness.io/harness-platform/use-harness-platform/pipelines/pipeline-chaining)
- Local `docs/developer-hub/docs/platform/variables-and-expressions/harness-expressions-reference.md`: built-in `<+service.name>` expression.
- [GAR tag lookup](https://docs.cloud.google.com/artifact-registry/docs/reference/rest/v1/projects.locations.repositories.packages.tags/get)
