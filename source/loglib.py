import logging
import argparse
import sys
import os


#log file
logFilePath=""
if  sys.platform=="win32":
    logFilePath =os.path.join(os.path.dirname(os.path.realpath(__file__)),'alertsLogFile.txt')#same directory  
else:#link
    logFilePath ='/var/log/alertsLogFile'

#create logger
logger = logging.getLogger(__name__,)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-logConsoleLevel", 
    "--logConsoleLevel", 
    default="debug",
    help= "Provide logging level: Example --logFileLevel debug, default=debug")

parser.add_argument(
    "-logFileLevel", 
    "--logFileLevel", 
    default="warning",
    help= "Provide logging level: Example --logFileLevel warning, default=warning")

options = parser.parse_args()
levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG
}
levelConsole = levels.get(options.logConsoleLevel.lower())
levelFile = levels.get(options.logFileLevel.lower())
if levelFile is None:
    raise ValueError(
        f"log level given: {options.log}"
        f" -- must be one of: {' | '.join(levels.keys())}")


logger.setLevel(levelConsole) 
#addd file handler
fh = logging.FileHandler(logFilePath)
fh.setLevel(levelFile) 

# create console handler with a higher log level
ch = logging.StreamHandler(sys.stdout)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# add ch and fh to logger
logger.addHandler(ch)
logger.addHandler(fh) 


""" logger.debug('debug message')
logger.info('info message')
logger.warning('warn message')
logger.error('error message')
logger.critical('critical message') """