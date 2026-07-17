import logging

# Configure logging
logging.basicConfig(
    filename=f'test.log', 
    level=logging.INFO,  # Log all messages from DEBUG level and above
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.info('started')
logging.info('completed')