import json
import urllib.request
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

debugUserSLAlert=True

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class UserSLAlert:
    def __init__(self,etoroid,cid,discordId,alertlevel=3):
        self.etoroid=etoroid
        self.cid=cid   
        self.portfolio=[] #portfolio
        self.discordId=discordId
        self.alertlevel=alertlevel   # this the percentage of SL at which the stop loss will be triggered, per default = 3%
    
    def GetPortfolio(self):
        import time
        try:
            self.portfolio.clear()
            try:
                getPortfolio="https://www.etoro.com/sapi/trade-data-real/live/public/portfolios?cid={}&format=json".format(self.cid)
                if debugUserSLAlert:
                    print("GetPortfolio={}".format(getPortfolio))
                #jsonPortfolio = urllib.request.urlopen(getPortfolio)
                #data = json.loads(jsonPortfolio.read().decode('utf-8'))
                response = requests_retry_session().get(getPortfolio)
                data = response.json()
            except Exception as ex:
                print("Exception in GetPortfolio , details= {}".format(ex))
                time.sleep(2)
                return []
            for position in data["AggregatedPositions"]:
                self.portfolio.append(position["InstrumentID"]) #example "InstrumentID": 19, positions with the same instrument aggrgated together
            return self.portfolio
        except Exception as ex:
            print("GetPortfolio Exception caught!={}".format(ex))
            return []