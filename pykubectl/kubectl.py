import json
import logging
from subprocess import CalledProcessError, check_output


class KubeCtl(object):
    def __init__(self, bin='kubectl', global_flags=''):
        super(KubeCtl, self).__init__()
        self.kubectl = '{} {}'.format(bin, global_flags)

    def execute(self, command, definition=None, safe=False):
        cmd = '{} {}'.format(self.kubectl, command)

        if definition:
            pre = 'echo \'{}\''.format(definition)
            cmd = '{} | {} -f -'.format(pre, cmd)

        logging.debug('executing {}'.format(cmd))

        try:
            return check_output(cmd, shell=True)
        except CalledProcessError as e:
            if not safe:
                raise e
            logging.warn('Command {} failed, swallowing'.format(command))

    def apply(self, *args, **kwargs):
        return self.execute('apply', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.execute('delete', *args, **kwargs)

    def get(self, *args, **kwargs):
        result = self.execute('get -a -o json', *args, **kwargs).decode()
        return json.loads(result)['items']

    def describe(self, *args, **kwargs):
        return self.execute('describe', *args, **kwargs)
