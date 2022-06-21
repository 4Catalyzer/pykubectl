import copy
import json
import logging
from time import sleep
import uuid

from .exceptions import KubernetesException
from .utils import render_definition
from .yaml_utils import Loader


class KubeObject:
    kind = ""

    @property
    def raw(self):
        return json.dumps(self.definition)

    @classmethod
    def from_file(cls, file_name, kubectl, anchors_file_name=None, **keys):
        raw = render_definition(file_name, **keys)
        yaml_loader = Loader(raw)

        if anchors_file_name is not None:
            yaml_raw = render_definition(anchors_file_name, **keys)
            anchors_yaml_loader = Loader(yaml_raw)
            yaml_loader.anchors = anchors_yaml_loader.get_node_anchors()

        data = yaml_loader.get_single_data()

        self = cls(data, kubectl)
        return self

    def __repr__(self):
        return f"{self.kind}[{self.name}]"

    def __str__(self):
        return self.__repr__()

    def __init__(self, definition, kubectl):
        super().__init__()
        self.definition = definition
        self.kubectl = kubectl

        kind = definition["kind"]

        if not self.kind:
            self.kind = kind
        elif kind != self.kind:
            raise KubernetesException(f"Invalid kind {kind} provided")

        self.name = self.definition["metadata"]["name"]

    def get(self, *args, **kwargs):
        return self.kubectl.get(self.raw, *args, **kwargs)

    def delete(self, *args, **kwargs):
        logging.info("%s: deleting", self)
        return self.kubectl.delete(self.raw, *args, **kwargs)

    def apply(self, *args, **kwargs):
        logging.info("%s: applying", self)
        return self.kubectl.apply(self.raw, *args, **kwargs)

    def describe(self, *args, **kwargs):
        return self.kubectl.describe(self.raw, *args, **kwargs)


class Deployment(KubeObject):
    kind = "Deployment"

    def undo(self, *args, **kwargs):
        logging.warn("%s: rolling back last deployment", self)
        cmd = f"rollout undo deployment/{self.name}"
        self.kubectl.execute(cmd, *args, **kwargs)

    def deploy(self, attempts=30):
        logging.info("%s: Deployment initiated", self)
        self.apply()

        while attempts >= 0:
            status = self.get()["status"]
            available = status.get("availableReplicas", 0)
            updated = status.get("updatedReplicas", 0)

            if available > 0 and updated > 0:
                logging.info("%s: successfully deployed", self)
                return

            logging.info("%s: waiting for first pod to be deployed...", self)
            sleep(10)
            attempts -= 1

        self.undo(safe=True)
        raise KubernetesException(f"deployment of {self} timed out")

    def execute_pod(self, name, override_command=None, **extra_overrides):
        spec = copy.deepcopy(self.definition["spec"]["template"]["spec"])
        id = str(uuid.uuid4())[:8]

        spec["restartPolicy"] = "Never"
        if override_command:
            spec["containers"][0]["command"] = override_command

        spec["containers"][0].update(extra_overrides)

        pod_definition = {
            "apiVersion": "v1",
            "kind": "Pod",
            "spec": spec,
            "metadata": {
                "name": f"{self.name}-{name}-{id}",
            },
        }

        pod = Pod(pod_definition, self.kubectl)
        pod.execute()
        
    def execute_job(self, name, command, ttlSeconds=30, backoffLimit=0, **extra_overrides):
        spec = copy.deepcopy(self.definition["spec"]["template"]["spec"])
        id = str(uuid.uuid4())[:8]
        
        job_definition = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"{name}-{id}"
            },
            "spec": {
                "ttlSecondsAfterFinished": ttlSeconds,
                "backoffLimit": backoffLimit,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [{
                            "name": f"{name}-{id}",
                            "image": spec["containers"][0]["image"],
                            "command": command,
                            "env": spec["containers"][0]["env"]
                        }]
                    }
                }
            }
            
        }
        job_definition["spec"]["template"]["spec"]["containers"][0].update(extra_overrides)
        
        job = Job(job_definition, self.kubectl)
        job.execute()
        


class Pod(KubeObject):
    kind = "Pod"

    def execute(self, attempts=30):
        logging.info("%s: execution initiated", self)

        self.apply()

        while attempts >= 0:
            phase = self.get()["status"]["phase"]
            if phase == "Failed":
                raise KubernetesException(f"{self} execution failed")
            if phase == "Succeeded":
                logging.info("successfully completed")
                return

            logging.info("%s is %s...", self, phase)

            sleep(10)
            attempts -= 1

        raise KubernetesException(f"{self} execution timed out")

    def logs(self, *args, **kwargs):
        cmd = f"logs {self.name}"
        return self.kubectl.execute(cmd, *args, **kwargs)

class Job(KubeObject):
    kind = "Job"

    def execute(self, attempts=30):
        logging.info("%s: execution initiated", self)

        self.apply()

        while attempts >= 0:
            jobStatus = self.get()["status"]
            if (isinstance(jobStatus.get("failed"), int) and jobStatus.get("failed") > 0):
                logs = ">> " + self.logs().decode("utf-8").replace("\n", "\n>>\t")
                raise KubernetesException(f"{self} execution failed, see logs below\n{logs}")
            if (jobStatus.get("succeeded") == 1):
                return logging.info("successfully completed")

            sleep(10)
            attempts -= 1

        raise KubernetesException(f"{self} execution timed out")
    
    def logs(self, *args, **kwargs):
        cmd = f"logs jobs/{self.name}"
        return self.kubectl.execute(cmd, *args, **kwargs)
