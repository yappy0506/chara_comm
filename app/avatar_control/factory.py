from __future__ import annotations

from app.avatar_control.backends.noop import NoopAvatarBackend
from app.avatar_control.mapper import AvatarActionMapper
from app.avatar_control.service import AvatarMotionService
from app.config.settings import Settings


def build_avatar_motion_service(settings: Settings) -> AvatarMotionService:
    mapper = AvatarActionMapper(
        action_to_hotkey={k.lower(): v for k, v in settings.avatar_action_to_hotkey.items()},
        emotion_to_hotkey={k.lower(): v for k, v in settings.avatar_emotion_to_hotkey.items()},
    )

    if settings.avatar_backend == "vtube_studio":
        from app.avatar_control.backends.vtube_studio import VtubeStudioBackend, VtubeStudioBackendConfig

        backend = VtubeStudioBackend(
            VtubeStudioBackendConfig(
                ws_url=settings.vtube_studio_ws_url,
                plugin_name=settings.vtube_studio_plugin_name,
                plugin_developer=settings.vtube_studio_plugin_developer,
                auth_token_path=settings.vtube_studio_auth_token_path,
                timeout_sec=settings.vtube_studio_timeout_sec,
            )
        )
    else:
        backend = NoopAvatarBackend()

    return AvatarMotionService(enabled=settings.avatar_enabled, mapper=mapper, backend=backend)
