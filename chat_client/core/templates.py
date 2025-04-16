from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import logging
import os
from jinja2 import Environment, FileSystemLoader


logger: logging.Logger = logging.getLogger(__name__)


def _get_template_dirs():
    """
    Get the template directories.
    """
    template_dirs = []
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, "..", "templates")
    template_dirs.append(template_path)
    return template_dirs


def get_templates():
    """
    Returns a Jinja2Templates object with the template directories set.
    """
    template_dirs = _get_template_dirs()

    loader = FileSystemLoader(template_dirs)
    templates = Jinja2Templates(
        directory=template_dirs,
        loader=loader,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return templates


def get_static_files():
    """
    Returns a StaticFiles object with the static directory set.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "..", "static")
    static_files = StaticFiles(directory=static_dir)
    return static_files


async def get_template_content(template_path: str, context_values: dict) -> str:
    """
    Get template string content from a jinja2 template and a dict of context values
    """

    template_dirs = _get_template_dirs()
    loader = FileSystemLoader(template_dirs)
    env = Environment(loader=loader)
    template = env.get_template(template_path)
    return template.render(context_values)
