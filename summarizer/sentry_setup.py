import sentry_sdk
from sentry_sdk.integrations.loguru import LoguruIntegration, LoggingLevels

from .config import Sentry


def init_sentry() -> bool:
    if not Sentry.DSN:
        return False

    sentry_sdk.init(
        dsn=Sentry.DSN,
        environment=Sentry.ENVIRONMENT,
        integrations=[
            LoguruIntegration(
                level=LoggingLevels.INFO.value,
                event_level=LoggingLevels.ERROR.value,
            ),
        ],
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
    return True
