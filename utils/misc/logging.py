from loguru import logger

logger.add("debug/debug.log", format="{time} {level} {message}", level="DEBUG", retention="10 MB", compression="zip")
