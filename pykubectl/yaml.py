from yaml.events import StreamEndEvent
from yaml.loader import Loader as LoaderBase


class Loader(LoaderBase):
    def get_node_anchors(self):
        if not self.check_event(StreamEndEvent):
            # Drop the STREAM-START event.
            self.get_event()
            # Drop the DOCUMENT-START event.
            self.get_event()
            self.compose_node(None, None)

        return self.anchors
