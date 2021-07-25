import sys
import os
import etoro as etorolib
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from loglib import logger as log 

profile="wislina"
log.info("checking etoro profile = ".format(profile))



myconnection =etorolib.Etoro("wislina","d37de0fa10")

myconnection.get_own_all_current_positions("Real")
