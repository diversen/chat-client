from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import logging
import os
from starlette.background import BackgroundTask
from starlette.requests import Request
from jinja2 import Environment, FileSystemLoader


logger: logging.Logger = logging.getLogger(__name__)


class AppTemplates(Jinja2Templates):
    def TemplateResponse(
        self,
        name: str,
        context: dict,
        status_code: int = 200,
        headers: dict | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ):
        request = context["request"]
        assert isinstance(request, Request)
        return super().TemplateResponse(
            request,
            name,
            context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )


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
    env = Environment(
        loader=loader,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    templates = AppTemplates(env=env)
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
