from loguru import logger

logger.add("debug/debug.log", format="{time} {level} {message}", level="DEBUG")
