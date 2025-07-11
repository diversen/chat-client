from starlette.requests import Request
import logging
from chat_client import __version__
from chat_client.core import flash
from chat_client.core import user_session
from chat_client.repositories import user_repository, prompt_repository
import data.config as config


logger: logging.Logger = logging.getLogger(__name__)


async def get_context(request: Request, variables):

    user_id = await user_session.is_logged_in(request)
    profile = await user_repository.get_profile(user_id)
    use_katex = getattr(config, "USE_KATEX", False)

    default_context = {
        "logged_in": user_id,
        "user_id": user_id,
        "profile": profile,
        "request": request,
        "version": __version__,
        "use_katex": use_katex,
        "prompts": await prompt_repository.list_prompts(user_id),
        "flash_messages": flash.get_messages(request=request),
    }

    context = {**default_context, **variables}
    return context
