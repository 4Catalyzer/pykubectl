import json
import logging
import tempfile
from subprocess import CalledProcessError, check_output
import warnings


class KubeCtl:
    def __init__(self, bin="kubectl", global_flags=""):
        super().__init__()
        self.kubectl = f"{bin} {global_flags}"

    def execute(self, command, definition=None, safe=False, ignore_errors=False):
        cmd = f"{self.kubectl} {command}"

        with tempfile.NamedTemporaryFile("w") as temp_file:
            if definition:
                temp_file.write(definition)
                temp_file.flush()
                cmd = f"{cmd} -f {temp_file.name}"

            logging.debug(f"executing {cmd}")

            try:
                return check_output(cmd, shell=True)
            except CalledProcessError as e:
                if safe:
                    warnings.warn(
                        "Use ignore_errors instead of safe",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                if not (safe or ignore_errors):
                    raise e
                logging.warn(f"Command {command} failed, swallowing")

    def apply(self, *args, **kwargs):
        return self.execute("apply", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.execute("delete", *args, **kwargs)

    def get(self, *args, **kwargs):
        result = self.execute("get -o json", *args, **kwargs).decode()
        return json.loads(result)["items"]

    def describe(self, *args, **kwargs):
        return self.execute("describe", *args, **kwargs)
