from string import Template


def render_definition(file_name, **keys):
    with open(file_name, mode='r') as file:
        return Template(file.read()).substitute(keys)
