"""Offline checks for the build/scan/push boundary and native rollback wiring."""
from pathlib import Path

import io
import json
import os
import subprocess
import tempfile
from unittest.mock import patch

import yaml

root = Path(__file__).parent
ci = yaml.safe_load((root / "pipelines/gar-build-scan-push.yaml").read_text())["pipeline"]
cd = yaml.safe_load((root / "pipelines/cloud-run-deploy.yaml").read_text())["pipeline"]
service = yaml.safe_load((root / "services/cloud-run-test.yaml").read_text())["service"]
stage = ci["stages"][0]["stage"]
prepare, build, scan, push, token, outputs = [item["step"] for item in stage["spec"]["execution"]["steps"]]
assert [build["type"], scan["type"], push["type"]] == ["BuildAndPushGAR", "AquaTrivy", "BuildAndPushGAR"]
assert build["spec"]["envVariables"]["PLUGIN_NO_PUSH"] == "true"
assert push["spec"]["envVariables"]["PLUGIN_PUSH_ONLY"] == "true"
archive = build["spec"]["envVariables"]["PLUGIN_TAR_PATH"]
assert archive == scan["spec"]["target"]["workspace"] == push["spec"]["envVariables"]["PLUGIN_SOURCE_TAR_PATH"]
assert scan["spec"]["image"]["type"] == "local_archive"
assert scan["spec"]["advanced"]["fail_on_severity"] == "high"
assert stage["failureStrategies"][0]["onFailure"]["action"]["type"] == "Abort"
assert all(step["spec"]["caching"] for step in [build, push]), "OIDC requires BuildX"
for key in ["connectorRef", "host", "projectID", "imageName", "tags"]:
    assert build["spec"][key] == push["spec"][key]
assert all("when" not in step and "failureStrategies" not in step for step in [build, scan, push])
deploy = cd["stages"][0]["stage"]
execution = deploy["spec"]["execution"]
group = execution["steps"][0]["stepGroup"]
rollback = execution["rollbackSteps"][0]["stepGroup"]
assert [s["step"]["type"] for s in group["steps"]] == ["DownloadManifests", "GoogleCloudRunPrepareRollbackData", "GoogleCloudRunDeploy"]
assert rollback["steps"][0]["step"]["type"] == "GoogleCloudRunRollback"
assert group["stepGroupInfra"] == rollback["stepGroupInfra"]
assert deploy["failureStrategies"][0]["onFailure"]["action"]["type"] == "StageRollback"
inputs = deploy["spec"]["service"]["serviceInputs"]["serviceDefinition"]["spec"]
artifact = inputs["artifacts"]["primary"]["sources"][0]
assert artifact["spec"]["digest"] == "<+pipeline.variables.image_digest>"

sources = service["serviceDefinition"]["spec"]["artifacts"]["primary"]["sources"]
assert any(s["identifier"] == artifact["identifier"] and s["type"] == "GoogleArtifactRegistry" for s in sources)
assert all(not p["allowStageExecutions"] for p in [ci, cd])
assert all(v["value"] == "<+input>" for v in ci["variables"] if v["name"] != "image_tag")
assert all(v["value"] == "<+input>" for v in cd["variables"])
chain = ci["stages"][1]["stage"]
assert chain["type"] == "Pipeline" and chain["when"]["pipelineStatus"] == "Success"
child_inputs = {v["name"]: v["value"] for v in chain["spec"]["inputs"]["variables"]}
assert "Deployment_Inputs.output.outputVariables.IMAGE_DIGEST" in child_inputs["image_digest"]
assert set(child_inputs) == {v["name"] for v in cd["variables"]}
manifest = yaml.safe_load((root / "cr-service/service.yaml").read_text())
assert manifest["metadata"]["name"] == "<+service.name>"
assert manifest["spec"]["template"]["spec"]["containers"][0]["image"] == "<+artifact.image>"
assert yaml.safe_load(service["serviceDefinition"]["spec"]["manifests"][0]["manifest"]["spec"]["store"]["spec"]["content"]) == manifest
config = yaml.safe_load((root / "inputsets/hello-build-deploy.yaml").read_text())["inputSet"]["pipeline"]
assert {v["name"] for v in config["variables"]} == {v["name"] for v in ci["variables"] if v["value"] == "<+input>"}
command = config["stages"][0]["stage"]["spec"]["execution"]["steps"][0]["step"]["spec"]["command"]
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["sh", "-eu", "-c", command.replace("cd /harness", "cd " + tmp)], check=True)
    for name in ["Dockerfile", "index.html"]:
        assert (Path(tmp) / name).read_text() == (root / "cr-service" / name).read_text()
# Execute the real digest parser against a mocked GAR response, including bad data.
parser = outputs["spec"]["command"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
env = dict(GAR_PROJECT="test", GAR_REGION="europe-west2", GAR_REPOSITORY="repo", IMAGE_NAME="nested/image", IMAGE_TAG="build-1", GCP_TOKEN="test-token")
for digest in ["sha256:" + "a" * 64, "not-a-digest"]:
    response = io.BytesIO(json.dumps({"version": "versions/" + digest}).encode())
    with patch.dict(os.environ, env), patch("urllib.request.urlopen", return_value=response) as request, patch.object(Path, "write_text") as write:
        try:
            exec(parser, {})
        except ValueError:
            assert digest == "not-a-digest"
            write.assert_not_called()
        else:
            assert digest.startswith("sha256:")
            write.assert_called_once_with(digest)
        assert "/packages/nested%2Fimage/tags/build-1" in request.call_args.args[0].full_url
print("PASS: input sets, sample build context, scan/push boundary, digest validation, chaining, manifest expressions and rollback.")
