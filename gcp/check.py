"""Offline checks for the build/scan/push boundary and native rollback wiring."""
from pathlib import Path

import yaml

root = Path(__file__).parent
ci = yaml.safe_load((root / "pipelines/gar-build-scan-push.yaml").read_text())["pipeline"]
cd = yaml.safe_load((root / "pipelines/cloud-run-deploy.yaml").read_text())["pipeline"]
service = yaml.safe_load((root / "services/cloud-run-test.yaml").read_text())["service"]
stage = ci["stages"][0]["stage"]
secrets, iac, tests, build, scan, push = [item["step"] for item in stage["spec"]["execution"]["steps"]]
assert [build["type"], scan["type"], push["type"]] == ["BuildAndPushGAR", "AquaTrivy", "BuildAndPushGAR"]
assert build["spec"]["envVariables"]["PLUGIN_NO_PUSH"] == "true"
assert push["spec"]["envVariables"]["PLUGIN_PUSH_ONLY"] == "true"
archive = build["spec"]["envVariables"]["PLUGIN_TAR_PATH"]
assert archive == scan["spec"]["target"]["workspace"] == push["spec"]["envVariables"]["PLUGIN_SOURCE_TAR_PATH"]
assert scan["spec"]["image"]["type"] == "local_archive"
assert scan["spec"]["advanced"]["fail_on_severity"] == "none"
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
assert len(ci["stages"]) == 1, "CI must stop after push for separate testing"
assert [secrets["type"], iac["type"]] == ["Gitleaks", "Checkov"]
for step in [secrets, iac]:
    assert step["spec"]["mode"] == "orchestration"
    assert step["spec"]["target"]["type"] == "repository"
    assert step["spec"]["advanced"]["fail_on_severity"] == "none"
assert "--redact" in secrets["spec"]["settings"]["tool_args"]
manifest = yaml.safe_load((root / "cr-service/service.yaml").read_text())
assert manifest["metadata"]["name"] == "<+service.name>"
assert manifest["spec"]["template"]["spec"]["containers"][0]["image"] == "<+artifact.image>"
store = service["serviceDefinition"]["spec"]["manifests"][0]["manifest"]["spec"]["store"]
assert store["type"] == "Github" and store["spec"]["gitFetchType"] == "Commit"
assert inputs["manifests"][0]["manifest"]["spec"]["store"]["spec"]["commitId"] == "<+pipeline.variables.source_commit>"
config = yaml.safe_load((root / "inputsets/hello-build-deploy.yaml").read_text())["inputSet"]["pipeline"]
assert {v["name"] for v in config["variables"]} == {v["name"] for v in ci["variables"] if v["value"] == "<+input>"}
assert config["stages"][0]["stage"]["spec"]["cloneCodebase"] is True
assert [s["step"]["identifier"] for s in config["stages"][0]["stage"]["spec"]["execution"]["steps"]] == ["Unit_Tests", "Build_Image"]
values = {v["name"]: v["value"] for v in config["variables"]}
assert (root.parent / values["dockerfile"]).is_file()
assert (root.parent / values["build_context"] / "pom.xml").is_file()
cd_config = yaml.safe_load((root / "inputsets/hello-deploy.yaml").read_text())["inputSet"]["pipeline"]
assert {v["name"] for v in cd_config["variables"]} == {v["name"] for v in cd["variables"]}
print("PASS: STO scan gates, build/push archive, input sets, Git manifest and native rollback.")

assert tests["type"] == "Test" and tests["spec"]["intelligenceMode"] is True
assert all(tests["spec"][field] == "<+input>" for field in ["connectorRef", "image", "command", "globs", "reports"])
settings = config["stages"][0]["stage"]["spec"]["execution"]["steps"][0]["step"]["spec"]
assert list(root.parent.glob(settings["globs"][0])), "Test glob must match Java tests"
assert settings["reports"] == ["gcp/cr-service/target/surefire-reports/TEST-*.xml"]
