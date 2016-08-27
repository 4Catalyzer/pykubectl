# PyKubeCtl

A python bridge to kubectl providing additional functionalities useful for CD and automation.


## Prerequisites

kubectl must be installed in your system

## How to use it

First initalize a `kubectl` object:

```py
kubectl = KubeCtl()

# specify a path to the kubectl binary
kubectl = KubeCtl('/path/to/kubectl/bin')

# you can provide global flags as well
kubectl = Kubectl('--token=XXX --server https://my.kubernetes.cluster')
```

then:

```py
pod = Pod(kubectl, { 'kind': 'Pod', 'metadata': '...', spec: '...' })
# you can specify a file
pod = Pod.from_file(kubectl, 'pod.yaml')
# you can even substitute templated variables
pod = Pod.from_file('pod.yaml', build='v01')

pod.apply()
pod.get()

# you can always use all the kubectl functionalities
kubectl.execute('scale --replicas=3 deployment/foo')
```

A use case for deployment

```py
deployment = Deployment.from_file('deployment.yaml')

# execute required task before deployment
deployment.execute_pod('migration', ['alembic', 'upgrade', 'head'])

# apply the deployment and wait until at least one pod is
# successfully running. Automatically rollback after timout expires
deployment.deploy(attempts=20)
```

## Why using kubectl instead of the REST APIs?

kubectl has additional well tested functionalities that make it easier to interact with the APIs, especially with file definitions. In addition to that, porting automation script from bash it's easier, since the same functionalities are supported.
