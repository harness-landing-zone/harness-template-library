# Tiny Cloud Run test

[Dockerfile](Dockerfile) packages [index.html](index.html) in Python Alpine. Python's built-in HTTP server listens on `0.0.0.0:8080` and serves **Hello from Cloud Run**. This server is for this test only; it has no database, dependencies to install, or Google API calls. The base-image tag receives updates; the CI scan gates the image built on each run.

[service.yaml](service.yaml) tells Cloud Run how to run that image. CI checks out this repository and builds this directory. The Harness service fetches the manifest from Git at the commit supplied to CD; use the same commit as the successful CI build.

A **service** supplies a stable HTTPS endpoint. A **revision** represents an image/configuration version. An **instance** is a running container. Each deployment creates a revision; Cloud Run scales instances to handle requests.

| Manifest setting | Meaning |
| --- | --- |
| `name: <+service.name>` | Uses the selected Harness service's display name; test value is `harness-cloudrun-test` |
| `image: <+artifact.image>` | Uses the GAR artifact selected by CD; tag and digest identify the image built by CI |
| CPU `1`, memory `512Mi` | Resources per instance |
| Minimum `0`, maximum `1` | Scale to zero and constrain test scaling; not a hard spending cap |
| `cpu-throttling: true` | Request-based billing |
| Port `8080` | Container HTTP listener; Cloud Run handles external HTTPS |
| Concurrency `10`, timeout `30` | Requests allowed per instance and per-request time limit |
| Traffic `100` to latest | Basic rollout to the latest ready revision |

Keep Harness service display names valid for Cloud Run: lowercase letters, digits and hyphens. `<+service.name>` is not the Harness identifier; `cloud_run_test` is the identifier and `harness-cloudrun-test` is the display name. The manifest can be reused with another validly named service and another artifact.

The project and region come from Harness infrastructure, not this manifest. The new test infrastructure selects `harness-management` in `europe-west2`. The application's runtime identity defaults to the project's default service account; the deployer needs permission to act as it. Use a dedicated least-privilege runtime identity for real applications.

`ingress: all` enables endpoint network reachability but does not grant anonymous access. A new service still requires an authorized caller. Use an authenticated request or Cloud Run's authenticated proxy for the test. Existing IAM permissions are managed separately.

To test locally with Docker:

```sh
docker build -t hello-cloud-run .
docker run --rm -p 8080:8080 hello-cloud-run
# In a second terminal:
curl --fail http://localhost:8080/
```

No deployment has run. After testing, delete the Cloud Run service and delete its GAR image separately if no longer needed.

See [pipeline configuration and input sets](../README.md) and [Google's YAML reference](https://docs.cloud.google.com/run/docs/reference/yaml/v1).
