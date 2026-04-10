import logging


def configure_logging(app_name: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s {app_name} %(levelname)s %(name)s %(message)s",
    )
