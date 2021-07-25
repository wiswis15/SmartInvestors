import sys
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import json
import urllib.request
import random
import requests
from bs4 import BeautifulSoup

import trade
from loglib import logger as log 


class EtoroScraper():
    def __init__(self):
        self.userTradesLink="https://www.etoro.com/api/streams/v2/streams/user-trades/{}?&languagecode=en-gb&pageNumber=1"



    def GetLatestTrades(self,**kwargs ):
        """
        get the latest trades using the user trade page
        """
        getTradesApi=self.userTradesLink.format(kwargs ["etoroprofile"])
        try:
            proxies = {"http":"http://{}:{}@{}".format(kwargs ['user'],kwargs ['password'],kwargs ["proxy"])}
            usingProxy=requests.get(getTradesApi, proxies=proxies)
            data = usingProxy.json()
            return data
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetLatestTrades proxy={} {} {} {} {} ".format(kwargs ["proxy"],exc_type, fname, exc_tb.tb_lineno,ex))
            return []






