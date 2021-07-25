import requests
import sys
import os
from loglib import logger as log 
import statistics



def get_trader_aggregated_positions(**kwargs ):
    """
    get aggregated positions without any sessions
    
    """
    try:
        url = 'https://www.etoro.com/sapi/trade-data-real/live/public/portfolios?cid={}&format=json'.format(kwargs ['cid'])
        proxies = {"http":"http://{}:{}@{}".format(kwargs ['user'],kwargs ['password'],kwargs ["proxy"])}
        usingProxy=requests.get(url, proxies=proxies)
        r =requests.get(url)
        if r.status_code != requests.codes.ok:
            log.error('get_trader_aggregated_positions failed with reason: %s', r.text)
            return []
        return r.json()['AggregatedPositions']
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in get_trader_aggregated_positions proxy={} {} {} {} {}".format(kwargs ["proxy"],exc_type, fname, exc_tb.tb_lineno,ex))
        return []

def get_all_current_positions(**kwargs ):
    try:
        url = 'https://www.etoro.com/sapi/trade-data-real/live/public/positions?InstrumentID={}&cid={}&format=json'.format(kwargs ['InstrumentID'],kwargs ['cid'])
        proxies = {"http":"http://{}:{}@{}".format(kwargs ['user'],kwargs ['password'],kwargs ["proxy"])}
        usingProxy=requests.get(url, proxies=proxies)
        r =requests.get(url)

        if r.status_code != requests.codes.ok:
            log.error('cannot get  positions: %s', r.text)
        r.raise_for_status()
        res = r.json()
        # res if of type list
        res = res['PublicPositions']
        return res
        
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in get_all_current_positions: proxy: {} {} {} {} {}".format(kwargs ["proxy"],exc_type, fname, exc_tb.tb_lineno,ex))



def GetAggregatedStocks(alertsDb,**kwargs):
    """
    Get the stocks owned by all my followed profiles, and rank them
    
    """
    try:
        allStocks=dict()
        success,allprofiles=alertsDb.GetMyListFollowedProfiles(kwargs["guild_id"],kwargs["channel_id"],kwargs["owner_id"])
        for profile in allprofiles:
            status,allpositions=alertsDb.GetOpenPositions(profile)
            for position in allpositions:
                market=position[3]
                value=position[6]
                if market in allStocks:
                    listOfProfiles=allStocks[market][0]  #set of profiles
                    listOfProfiles.add(profile)
                    values=allStocks[market][1]
                    values.append(value)
                    allStocks[market]=(listOfProfiles,values)
                else:
                    initialset=set()
                    initialset.add(profile)
                    allStocks[market]=(initialset,[value])

        withAverage=dict()
        for stock in allStocks:
            average=statistics.mean(allStocks[stock][1])
            withAverage[stock.upper()]=(len(allStocks[stock][0]),average)
        
        def take_average(elem):
            return elem[1][0]  
        
        list=sorted(withAverage.items(), key=take_average, reverse=True)
        return list
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in GetMostCommonStocks:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
        return []

def get_trader_cid(trader_login):
    url = 'https://www.etoro.com/api/logininfo/v1.1/users/{0}'
    r = requests.get(url.format(trader_login))
    res = r.json()['realCID']
    log.info('fetched trader CID for `%s`: %s', trader_login, res)
    return res


allIndustries=dict()
def buildIndustriesDict():
    global allIndustries
    allIndustries['0']='COMMODITIES'
    allIndustries['1']='BASIC MATERIALS'
    allIndustries['2']='CONGLOMERATES'
    allIndustries['3']='CONSUMERS GOODS'
    allIndustries['4']='FINANCIAL'
    allIndustries['5']='HEALTHCARE'
    allIndustries['6']='COMMODITIES'
    allIndustries['7']='INDUSTRIAL GOODS'
    allIndustries['8']='TECHNOLOGY'
    allIndustries['9']='UTILITIES'

buildIndustriesDict()


def GetAllInstruments():
    url = ('https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/'
        'instruments')
    r = requests.get(url)

    instruments = r.json()['InstrumentDisplayDatas']
    instruments_by_symbol=dict()
    for instrument in instruments:
        if 'StocksIndustryID' in instrument:
            instruments_by_symbol[instrument['SymbolFull']]=allIndustries[str(instrument['StocksIndustryID'])]
    
    return instruments_by_symbol

allInstruments=GetAllInstruments()

def GetIndustry(instrumentname):
    if instrumentname in allInstruments:
        return allInstruments[instrumentname]
    else :
        return ""




