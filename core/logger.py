import logging
import os
import sys

def setup_logging(level=logging.INFO):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stderr)]
    
    # En modo empaquetado, también escribir a fichero en ~/.firmapdf/
    if getattr(sys, "frozen", False):
        log_dir = os.path.expanduser("~/.firmapdf")
        os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(
            os.path.join(log_dir, "firmapdf.log"), encoding="utf-8"
        ))
    
    logging.basicConfig(level=level, format=fmt, handlers=handlers)
