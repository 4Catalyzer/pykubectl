import json
import unittest
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


class ExecuteJobTests(unittest.TestCase):
    def test_inherits_pod_level_scheduling_fields(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job("migration", ["alembic", "upgrade", "head"])

        job = _applied_job_definition(kubectl)
        pod_spec = job["spec"]["template"]["spec"]

        self.assertEqual(
            pod_spec["nodeSelector"], {"qsi.io/executor-node-type": "service"}
        )
        self.assertEqual(pod_spec["serviceAccountName"], "executor")
        self.assertEqual(pod_spec["volumes"], [{"name": "scratch", "emptyDir": {}}])
        self.assertEqual(
            pod_spec["tolerations"], [{"key": "dedicated", "operator": "Exists"}]
        )
        self.assertEqual(pod_spec["restartPolicy"], "Never")

    def test_inherits_image_env_and_resources_and_sets_command(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job("migration", ["alembic", "upgrade", "head"])

        container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
            "containers"
        ][0]

        self.assertEqual(container["image"], "cex-api:abc123")
        self.assertEqual(container["env"], [{"name": "ENV", "value": "staging"}])
        self.assertEqual(
            container["resources"], {"requests": {"cpu": "250m", "memory": "256Mi"}}
        )
        self.assertEqual(container["command"], ["alembic", "upgrade", "head"])

    def test_strips_health_probes(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job("migration", ["alembic", "upgrade", "head"])

        container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
            "containers"
        ][0]

        self.assertNotIn("livenessProbe", container)
        self.assertNotIn("readinessProbe", container)
        self.assertNotIn("startupProbe", container)

    def test_extra_overrides_apply_to_container(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job(
            "migration",
            ["alembic", "upgrade", "head"],
            resources={"requests": {"cpu": "1"}},
        )

        container = _applied_job_definition(kubectl)["spec"]["template"]["spec"][
            "containers"
        ][0]

        self.assertEqual(container["resources"], {"requests": {"cpu": "1"}})

    def test_pod_overrides_apply_to_pod_spec(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job(
            "migration",
            ["alembic", "upgrade", "head"],
            pod_overrides={"nodeSelector": {"qsi.io/executor-node-type": "compute"}},
        )

        pod_spec = _applied_job_definition(kubectl)["spec"]["template"]["spec"]

        self.assertEqual(
            pod_spec["nodeSelector"], {"qsi.io/executor-node-type": "compute"}
        )

    def test_ttl_and_backoff_limit_and_job_naming(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job(
            "migration", ["alembic", "upgrade", "head"], ttlSeconds=86400, backoffLimit=2
        )

        job = _applied_job_definition(kubectl)

        self.assertEqual(job["spec"]["ttlSecondsAfterFinished"], 86400)
        self.assertEqual(job["spec"]["backoffLimit"], 2)
        self.assertTrue(job["metadata"]["name"].startswith("cex-api-migration-"))
        self.assertEqual(
            job["spec"]["template"]["spec"]["containers"][0]["name"],
            job["metadata"]["name"],
        )

    def test_does_not_mutate_original_deployment_definition(self):
        deployment, kubectl = _make_deployment()

        deployment.execute_job("migration", ["alembic", "upgrade", "head"])

        original_container = deployment.definition["spec"]["template"]["spec"][
            "containers"
        ][0]
        self.assertIn("livenessProbe", original_container)
        self.assertEqual(original_container["name"], "cex-api")


if __name__ == "__main__":
    unittest.main()
