import copy
import json
import logging
from time import sleep
import yaml
import uuid

from .exceptions import KubernetesException
from .utils import render_definition


class KubeObject(object):
    kind = ''

    @property
    def raw(self):
        return json.dumps(self.definition)

    @classmethod
    def from_file(cls, file_name, kubectl, **keys):
        raw = render_definition(file_name, **keys)

        try:
            data = json.loads(raw)
        except ValueError:
            data = yaml.load(raw)

        self = cls(data, kubectl)
        return self

    def __repr__(self):
        return "{kind}[{name}]".format(kind=self.kind, name=self.name)

    def __str__(self):
        return self.__repr__()

    def __init__(self, definition, kubectl):
        super(KubeObject, self).__init__()
        self.definition = definition
        self.kubectl = kubectl

        kind = definition['kind']

        if not self.kind:
            self.kind = kind
        elif kind != self.kind:
            raise KubernetesException('Invalid kind {} provided'.format(kind))

        self.name = self.definition['metadata']['name']

    def get(self, *args, **kwargs):
        return self.kubectl.get(self.raw, *args, **kwargs)[0]

    def delete(self, *args, **kwargs):
        logging.info('%s: deleting', self)
        return self.kubectl.delete(self.raw, *args, **kwargs)

    def apply(self, *args, **kwargs):
        logging.info('%s: applying', self)
        return self.kubectl.apply(self.raw, *args, **kwargs)

    def describe(self, *args, **kwargs):
        return self.kubectl.describe(self.raw, *args, **kwargs)


class Deployment(KubeObject):
    kind = 'Deployment'

    def undo(self, *args, **kwargs):
        logging.warn('%s: rolling back last deployment', self)
        cmd = 'rollout undo deployment/{}'.format(self.name)
        self.kubectl.execute(cmd, *args, **kwargs)

    def deploy(self, attempts=30):
        logging.info('%s: Deployment initiated', self)
        self.apply()

        while attempts >= 0:
            status = self.get()['status']
            available = status.get('availableReplicas', 0)
            updated = status.get('updatedReplicas', 0)

            if available > 0 and updated > 0:
                logging.info('%s: successfully deployed', self)
                return

            logging.info('%s: waiting for first pod to be deployed...', self)
            sleep(10)
            attempts -= 1

        self.undo(safe=True)
        raise KubernetesException('deployment of {} timed out'.format(self))

    def execute_pod(self, name, override_command=None):
        spec = copy.deepcopy(self.definition['spec']['template']['spec'])
        id = str(uuid.uuid4())[:8]

        spec['restartPolicy'] = 'Never'
        if override_command:
            spec['containers'][0]['command'] = override_command

        pod_definition = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'spec': spec,
            'metadata': {
                'name': '{}-{}-{}'.format(self.name, name, id),
            }
        }

        pod = Pod(pod_definition, self.kubectl)
        pod.execute()


class Pod(KubeObject):
    kind = 'Pod'

    def _abort(self):
        logging.info(self.logs(safe=True))
        self.delete(safe=True)

    def execute(self, attempts=30):
        logging.info('%s: execution initiated', self)

        self.apply()

        while attempts >= 0:
            phase = self.get()['status']['phase']
            if phase == 'Failed':
                self._abort()
                raise KubernetesException('{} execution failed'.format(self))
            if phase == 'Succeeded':
                logging.info('successfully completed')
                return

            logging.info('%s is %s...', self, phase)

            sleep(10)
            attempts -= 1

        self._abort()
        raise KubernetesException('{} execution timed out'.format(self))

    def logs(self, *args, **kwargs):
        cmd = 'logs {}'.format(self.name)
        return self.kubectl.execute(cmd, *args, **kwargs)
