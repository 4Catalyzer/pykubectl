import json
from unittest.mock import MagicMock

from pykubectl.objects import Deployment


def _deployment_definition():
    """A representative Deployment definition, similar to what a real
    templateSpec (nodeSelector/serviceAccountName/volumes/resources/probes)
    would render to.
    """
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "cex-api"},
        "spec": {
            "template": {
                "spec": {
                    "nodeSelector": {"qsi.io/executor-node-type": "service"},
                    "serviceAccountName": "executor",
                    "volumes": [{"name": "scratch", "emptyDir": {}}],
                    "tolerations": [{"key": "dedicated", "operator": "Exists"}],
                    "containers": [
                        {
                            "name": "cex-api",
                            "image": "cex-api:abc123",
                            "env": [{"name": "ENV", "value": "staging"}],
                            "resources": {
                                "requests": {"cpu": "250m", "memory": "256Mi"}
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": 8080}
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/health", "port": 8080}
                            },
                            "startupProbe": {
                                "httpGet": {"path": "/health", "port": 8080}
                            },
                        }
                    ],
                }
            }
        },
    }


def _make_deployment():
    kubectl = MagicMock()
    # Job.execute() polls .get() until status.succeeded == 1; return that
    # immediately so tests don't sleep through the retry loop.
    kubectl.get.return_value = {"status": {"succeeded": 1}}
    return Deployment(_deployment_definition(), kubectl), kubectl


def _applied_job_definition(kubectl):
    """Parse the JSON definition passed to kubectl.apply()."""
    raw = kubectl.apply.call_args[0][0]
    return json.loads(raw)


def test_inherits_pod_level_scheduling_fields():
    deployment, kubectl = _make_deployment()

    deployment.execute_job("migration", ["alembic", "upgrade", "head"])

    job = _applied_job_definition(kubectl)
    pod_spec = job["spec"]["template"]["spec"]

    assert pod_spec["nodeSelector"] == {"qsi.io/executor-node-type": "service"}
    assert pod_spec["serviceAccountName"] == "executor"
    assert pod_spec["volumes"] == [{"name": "scratch", "emptyDir": {}}]
    assert pod_spec["tolerations"] == [{"key": "dedicated", "operator": "Exists"}]
    assert pod_spec["restartPolicy"] == "Never"


def test_inherits_image_env_and_resources_and_sets_command():
    deployment, kubectl = _make_deployment()

    deployment.execute_job("migration", ["alembic", "upgrade", "head"])

    container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
        "containers"
    ][0]

    assert container["image"] == "cex-api:abc123"
    assert container["env"] == [{"name": "ENV", "value": "staging"}]
    assert container["resources"] == {"requests": {"cpu": "250m", "memory": "256Mi"}}
    assert container["command"] == ["alembic", "upgrade", "head"]


def test_strips_health_probes():
    deployment, kubectl = _make_deployment()

    deployment.execute_job("migration", ["alembic", "upgrade", "head"])

    container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
        "containers"
    ][0]

    assert "livenessProbe" not in container
    assert "readinessProbe" not in container
    assert "startupProbe" not in container


def test_extra_overrides_apply_to_container():
    deployment, kubectl = _make_deployment()

    deployment.execute_job(
        "migration",
        ["alembic", "upgrade", "head"],
        resources={"requests": {"cpu": "1"}},
    )

    container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
        "containers"
    ][0]

    assert container["resources"] == {"requests": {"cpu": "1"}}


def test_pod_overrides_apply_to_pod_spec():
    deployment, kubectl = _make_deployment()

    deployment.execute_job(
        "migration",
        ["alembic", "upgrade", "head"],
        pod_overrides={"nodeSelector": {"qsi.io/executor-node-type": "compute"}},
    )

    pod_spec = _applied_job_definition(kubectl)["spec"]["template"]["spec"]

    assert pod_spec["nodeSelector"] == {"qsi.io/executor-node-type": "compute"}


def test_ttl_and_backoff_limit_and_job_naming():
    deployment, kubectl = _make_deployment()

    deployment.execute_job(
        "migration", ["alembic", "upgrade", "head"], ttlSeconds=86400, backoffLimit=2
    )

    job = _applied_job_definition(kubectl)

    assert job["spec"]["ttlSecondsAfterFinished"] == 86400
    assert job["spec"]["backoffLimit"] == 2
    assert job["metadata"]["name"].startswith("cex-api-migration-")
    assert (
        job["spec"]["template"]["spec"]["containers"][0]["name"]
        == job["metadata"]["name"]
    )


def test_does_not_mutate_original_deployment_definition():
    deployment, kubectl = _make_deployment()

    deployment.execute_job("migration", ["alembic", "upgrade", "head"])

    original_container = deployment.definition["spec"]["template"]["spec"][
        "containers"
    ][0]
    assert "livenessProbe" in original_container
    assert original_container["name"] == "cex-api"
