import logging
import os
from collections.abc import Mapping
from typing import Any, overload

from jinja2 import Environment, FileSystemLoader
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates, _TemplateResponse

logger: logging.Logger = logging.getLogger(__name__)


class AppTemplates(Jinja2Templates):
    @overload
    def TemplateResponse(
        self,
        request: Request,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> _TemplateResponse:
        pass

    @overload
    def TemplateResponse(
        self,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> _TemplateResponse:
        pass

    def TemplateResponse(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> _TemplateResponse:
        if args and isinstance(args[0], str):
            name = args[0]
            context = kwargs.pop("context", args[1] if len(args) > 1 else {}) or {}

            request = context["request"]
            assert isinstance(request, Request)

            status_code = kwargs.pop("status_code", args[2] if len(args) > 2 else 200)
            headers = kwargs.pop("headers", args[3] if len(args) > 3 else None)
            media_type = kwargs.pop("media_type", args[4] if len(args) > 4 else None)
            background = kwargs.pop("background", args[5] if len(args) > 5 else None)

            return super().TemplateResponse(
                request,
                name,
                context,
                status_code=status_code,
                headers=headers,
                media_type=media_type,
                background=background,
                **kwargs,
            )

        return super().TemplateResponse(*args, **kwargs)


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


async def render_template(
    templates: AppTemplates, request: Request, template_name: str, context_values: dict[str, Any]
) -> _TemplateResponse:
    from chat_client.core.base_context import get_context

    context = await get_context(request, {"request": request, **context_values})
    return templates.TemplateResponse(template_name, context)


async def get_template_content(template_path: str, context_values: dict) -> str:
    """
    Get template string content from a jinja2 template and a dict of context values
    """

    template_dirs = _get_template_dirs()
    loader = FileSystemLoader(template_dirs)
    env = Environment(loader=loader)
    template = env.get_template(template_path)
    return template.render(context_values)
