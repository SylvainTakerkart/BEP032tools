import logging

logging.basicConfig(
    filename='project.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

log = logging.getLogger(__name__)