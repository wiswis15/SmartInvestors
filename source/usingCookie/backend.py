import traceback
import socket
import time
import sys
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import json
from threading import Thread, Lock
from discord.ext import commands
import datetime
from discord.utils import get
from discord.ext.tasks import loop
import schedule
import queue
import requests
import pathlib
#import win32api
import struct


import trade 
from  discordAlerts import DiscordAlert as discordAlert
from alertsdatabase import AlertDatabase as alertsdb
import etoro as etorolib
from loglib import logger as log 
import EtoroScraping  
import generalFunctions
from  proxies import ProxiesProvider as ProxiesProvider

simulationMode=False  #just for simulation
simulationProfile='wislina'  #just for simulation
password='26042017'
MaxNumberOfFollwers=10
mainThreadAlertDb=alertsdb("mainThread")

listOFConnectedClients=[]

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 1515        # The port used by the server
serverToClientsdMessages = queue.Queue() # buffer for reading/writing
ClientsToServerMessages = queue.Queue() # buffer for reading/writing
etoroRequestQueue=queue.Queue()  # queue for all the job requests to etoro
etoroResponseQueue=queue.Queue()  # data to be consumed


timeBetweeeneachEtoroRequest=1 #seconds between each request for etoro , by using proxies, it can be lowered
freq = 30#frequencey at which the scheduler create new task for each profile
scrapingFrequency =3 #frequency of scraping

portfolioHistory=dict() # map that keep track of the etoronameInstrumentId:quantity
#example portfolioHAshHistory[wislina32]=200 # mean wislina has 200 units if instruments Id 32
portfolioHistoryFile="portfolioHistoryFile.json" # we save the file, to load on startup

"""
def ReadportfolioHistoryFil():
    try:
        portfolioHistoryFilepath=os.path.join(pathlib.Path(__file__).parent.absolute(),portfolioHistoryFile)
        if os.path.exists(portfolioHistoryFilepath):
            with open(portfolioHistoryFilepath, 'r') as file:
                portfolioHistory = json.load(file) 
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in ReadportfolioHistoryFil {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

ReadportfolioHistoryFil()


def exit_handler():
    global portfolioHistory
    myjson = json.dumps(portfolioHistory)
    f = open(portfolioHistoryFile,"w+")
    f.write(myjson)
    f.close()
    log.info('backend shutting down --> dumping portfolioHistory')


"""



MessageFile="textToAllUsers.txt"


startTime=datetime.datetime.now()

"""
initialization
"""
#load the map etoroProofiles-->channels
etoroChannelsMap=dict()
AllFollowedProfiles= { }  #all profiles being watched : nested dictionary AllFollowedProfiles["wislina"]=["cid":"13231,..."]
AllFollowedProfilesLock=Lock()
TraderCidMap=dict()  # dictionary of all instrumentid in potfolio, the key=etoroPrfile



#premiumProfiles=[]  #list of etoro premium profiles who have SL/TP subscriptions
#sltpDiscordSubscribers=mainThreadAlertDb.GetSLTPSubscriptioons()  # get alll subscribers
#slAlertsSubscribers=mainThreadAlertDb.GetSLAlertsSbscribers()





myProxyProvider=ProxiesProvider()  #only ip proxies provider
        
def ReloadDatabase():
    """Reload the database when a change happens
    
    """
    global AllFollowedProfiles
    global etoroChannelsMap
    global AllFollowedProfilesLock
    #global premiumProfiles
    try:
        #get all the etoro profiles being followed
        AllFollowedProfilesLock.acquire()
        AllFollowedProfiles.clear()
        etoroChannelsMap.clear()
        (status,AllProfilesDetails)=mainThreadAlertDb.GetAllFollowedProfiles()
        # id, profile, cid, date, sltpchangenotifications, slalerts, slalertlevel, image
        #'1', 'rapidstock', '13735765', '2021-02-17', NULL, NULL, NULL, 'https://etoro-cdn.etorostatic.com/avatars/150X150/13735765/6.jpg'
        for profile in AllProfilesDetails:
            AllFollowedProfiles[profile[1]]={} #empty dictionary
            AllFollowedProfiles[profile[1]]['profile']=profile[1]# profile in the database
            AllFollowedProfiles[profile[1]]['cid']=profile[2]# cid in the database
            AllFollowedProfiles[profile[1]]['sltpchangenotifications']=profile[4]# image in the database
            AllFollowedProfiles[profile[1]]['slalerts']=profile[5]# image in the database
            AllFollowedProfiles[profile[1]]['slalertlevel']=profile[6]# image in the database
            AllFollowedProfiles[profile[1]]['image']=profile[7]# image in the database
            #add premium profiles
            #if profile[4] or profile[5]:
            #    premiumProfiles.append(profile) 

        if not status:
            log.critical("Coudl not read the list of followed etoro profiles!")
        #load the map etoroProofiles-->channels
        subscribers=[]  # empty list
        for followedProfile in AllFollowedProfiles:
            (status,subscribers)=mainThreadAlertDb.GetDiscordListOfSubscribers(followedProfile) #profile
            if not status:
                log.critical("Error while loading the map of subscribers")
            etoroChannelsMap[followedProfile]=[]
            for subscriber in subscribers:
                etoroChannelsMap[followedProfile].append(subscriber)
        if (AllFollowedProfilesLock.locked()):
            AllFollowedProfilesLock.release()
        
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in ReloadDatabase {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))





def start_server():
   host = HOST
   port = PORT # arbitrary non-privileged port
   soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
   log.info("Backend Server Socket created")
   try:
      soc.bind((host, port))
   except:
      print("Bind failed. Error : " + str(sys.exc_info()))
      sys.exit()
   soc.listen(6) # queue up to 6 requests
   log.info("Socket now listening on {}".format((host, port)))
   # infinite loop- do not reset for every requests
   while True:
        newClient=soc.accept()
        listOFConnectedClients.append(newClient)
        connection, address = newClient
        ip, port = str(address[0]), str(address[1])
        log.info("New Client Connected with " + ip + ":" + port)
        try:
            Thread(target=clientThread, args=(connection, ip, port)).start()
        except:
            log.error("Thread did not start.")
            traceback.print_exc()
            time.sleep(2)





def ConsumeCid(mainThreadAlertDb,**kwargs):
    """
    update the portfolio of instruments (CIDs)
    """
    TraderCidMap[kwargs["etoroprofile"]]=kwargs["data"] #update the dictionary with the new data
    for instrument in kwargs["data"]:
        key=kwargs["etoroprofile"]+str(instrument["InstrumentID"])
        """
        because of etoro blocking the traffic, i only enabling this feature to premium users
        """
        if ((key not in portfolioHistory) or (portfolioHistory[key] !=instrument["Invested"])\
            or (kwargs["etoroprofile"] in premiumProfiles) or kwargs["etoroprofile"] in slAlertsSubscribers) :
            portfolioHistory[key]=instrument["Invested"]
            #only request and update if the potfolio for that particular instrument has changed
            #or we need to calculate the SL/TP change/Alerts
            AddCurrentPositionsJob(etoroprofile=kwargs["etoroprofile"],cid=kwargs["cid"],InstrumentID=instrument["InstrumentID"])
            #AddClosedPositionsJob(etoroprofile=kwargs["etoroprofile"],cid=kwargs["cid"])






def ConsumeCurrentPositions(alertDb,**kwargs):
    """
    Consume the new received instruments data
    
    """
    try:
        for receivedPosition in kwargs["data"]:
            newTrade=trade.Trade(receivedPosition["PositionID"])
            newTrade.ExtractDetails(receivedPosition)#extract all informatin
            newTrade.market=alertDb.GetInstrumentName(kwargs["InstrumentID"])
            newTrade.displayName=newTrade.market
            (exists,tradeDetails)=alertDb.DoesTradeExists(receivedPosition["PositionID"])
            if exists:
                oldData=trade.Trade(receivedPosition["PositionID"])
                oldData.stoploss=tradeDetails[10]
                oldData.takeprofit=tradeDetails[11]
                oldData.displayName=newTrade.market
                alert=discordAlert(newTrade)
                if kwargs["etoroprofile"] in premiumProfiles:
                    slTpMessageNotification,SLCautionAlert=alert.DetectChangeInSLTP(kwargs["etoroprofile"],newTrade,oldData)
                    if  slTpMessageNotification:# SL or TP changed-->update the database
                        alertDb.ReplaceTradeIntoDatabase(kwargs["etoroprofile"],newTrade)
                        for sltpDiscordSubscriber in sltpDiscordSubscribers:
                            message = {
                            "type": "SL/TP change notification",
                            "profile":kwargs["etoroprofile"],
                            "guildId":sltpDiscordSubscriber[0],
                            "channel_id":sltpDiscordSubscriber[1],
                            "owner_id":"",
                            "image":AllFollowedProfiles[kwargs["etoroprofile"]]['image'],
                            "result": slTpMessageNotification,
                            "direction":newTrade.direction,
                            "rate":newTrade.rate,
                            "leverage":newTrade.leverage,
                            "openclose":newTrade.openClose,
                            "NetProfit":newTrade.NetProfit,
                            "market":newTrade.market ,
                            "instrument_image":alertsdb.GetInstrumentIconImage(newTrade.market.upper())  
                            }
                            jsonResult= json.dumps(message)
                            serverToClientsdMessages.put(jsonResult)
                        log.debug("Change in SL/TP Alert:  {}".format(alert))
                #Now the turn for the SL Alerts
                if kwargs["etoroprofile"] in slAlertsSubscribers:
                    for slalertsubscribers in slAlertsSubscribers[kwargs["etoroprofile"] ]:
                        message = {
                            "guildId":slalertsubscribers[0],
                            "channel_id":slalertsubscribers[1],
                            "market":newTrade.market,
                            "result": SLCautionAlert,
                            "instrument_image":alertsdb.GetInstrumentIconImage(newTrade.market.upper())   
                        }
                        jsonResult= json.dumps(message)
                        serverToClientsdMessages.put(jsonResult)
                log.debug("SLCautionAlert Alert:  {}".format(SLCautionAlert))
                
            else:#new trade -->insert it
                alertDb.InsertTradeIntoDatabase(kwargs["etoroprofile"],newTrade)
                if newTrade.OpenDateTime:
                    openTime=newTrade.OpenDateTime#2021-02-13T21:02:48.3800000Z
                    time=openTime[0:19]
                    time=time.replace('T',' ')
                    tradeTime=datetime.strptime(time,"%Y-%m-%d %H:%M:%S")
                    if ( (tradeTime.date() < startTime.date())\
                            or (tradeTime.time() <  (startTime -datetime.timedelta(hours=1)).time() )):#old trade--> dont fire any alert,1h added because etoro time is 1 h behind
                            continue
                #now send the alert 
                alert=discordAlert(newTrade)
                NewTradeAlert=alert.NewPositionAlertMessage(kwargs["etoroprofile"]) # construct the alert to send
                allSubscribers=etoroChannelsMap[kwargs["etoroprofile"]]
                for discordSubscriber in allSubscribers:
                    message = {
                        "profile":kwargs["etoroprofile"],
                        "guildId":discordSubscriber[2],
                        "channel_id":discordSubscriber[3],
                        "owner_id":discordSubscriber[4],
                        "image":AllFollowedProfiles[kwargs["etoroprofile"]]['image'],
                        "result": NewTradeAlert,
                        "direction":newTrade.direction,
                        "rate":newTrade.rate,
                        "leverage":newTrade.leverage,
                        "openclose":newTrade.openClose,
                        "NetProfit":newTrade.NetProfit,
                        "market":newTrade.market ,
                        "instrument_image":alertsdb.GetInstrumentIconImage(newTrade.market.upper())                   
                    }
                    jsonResult= json.dumps(message)
                    serverToClientsdMessages.put(jsonResult)
                log.debug("NewTradeAlert= {}".format(NewTradeAlert))
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in currentPositionsUpdate :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

def ConsumeClosedPositions(databaseDb,**kwargs):
    """
    Consume the new received instruments data
    
    """
    try:
        for closedpos in kwargs["data"]:
            newTrade=trade.Trade(closedpos["PositionID"])
            newTrade.ExtractDetails(closedpos)#extract all informatin
            newTrade.openClose="close"
            newTrade.market=databaseDb.GetInstrumentName(closedpos["InstrumentID"])
            newTrade.displayName=newTrade.market
            (exists,tradeDetails)=databaseDb.DoesTradeExists(closedpos["PositionID"])
            if exists and tradeDetails[7]=="open":
                databaseDb.ReplaceTradeIntoDatabase(kwargs["etoroprofile"],newTrade)
                #check if the trade is new
                closeTime=startTime
                if newTrade.CloseDateTime:
                    time=newTrade.CloseDateTime[0:19]
                    time=time.replace('T',' ')
                    closeTime=datetime.strptime(time,"%Y-%m-%d %H:%M:%S")
                if ( (closeTime.date() < startTime.date())\
                    or (closeTime.time() <  (startTime -datetime.timedelta(hours=1)).time() )):#old trade--> dont fire any alert
                    continue
                alert=discordAlert(newTrade)
                closeAlertMessage=alert.ClosedAlertMessage(kwargs["etoroprofile"])
                for discordSubscriber in etoroChannelsMap[kwargs["etoroprofile"]]:
                    message = {
                        "profile":kwargs["etoroprofile"],
                        "guildId":discordSubscriber[2],
                        "channel_id":discordSubscriber[3],
                        "owner_id":discordSubscriber[4],
                        "image":AllFollowedProfiles[kwargs["etoroprofile"]]['image'],
                        "result": closeAlertMessage,
                        "direction":newTrade.direction,
                        "rate":newTrade.rate,
                        "leverage":newTrade.leverage,
                        "openclose":newTrade.openClose,
                        "NetProfit":newTrade.NetProfit,
                        "market":newTrade.market ,
                        "instrument_image":alertsdb.GetInstrumentIconImage(newTrade.market.upper())                        
                    }
                    jsonResult= json.dumps(message)
                    serverToClientsdMessages.put(jsonResult)
                    log.debug("closeAlertMessage= {}".format(closeAlertMessage))
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in ConsumeClosedPositions {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))


def ConsumeDataFromScraper(ScrapEtoroDb,**kwargs):
    """
    Consume the data  coming from the Scraper    
    """
    global etoroChannelsMap
    try:
        for actualTrade in  kwargs["data"] :       
            if not "positionID" in actualTrade\
                and ('type' not in actualTrade) and  \
                (actualTrade['type']!='OpenOrder') :#sometimes we receive a post from the user feed which does not contain any data
                continue
            #extracting the data
            if ( ('type' in actualTrade) and (actualTrade['type']=='OpenOrder')):
                continue #for now lets skip orders
            if not 'positionID' in actualTrade:
                continue
            lastTrade=trade.Trade(actualTrade['positionID'])
            if not lastTrade.ExtractAllData(actualTrade):# failed--> continue to next one
                log.error("ConsumeDataFromScraper(): failed to decode input")
                continue
            (exists,oldTradeDetails)=ScrapEtoroDb.DoesTradeExists(actualTrade["positionID"])#check if the trade is already saved into the database
            if not exists or (simulationMode  and (kwargs["etoroprofile"]==simulationProfile)):
                #New Trade detected!
                tradeTime=datetime.datetime.fromtimestamp(int(actualTrade["occurredAt"]/1000.0)) #occurredAt": 1613528786637
                ScrapEtoroDb.InsertTradeIntoDatabase(kwargs["etoroprofile"],lastTrade)
                tradeTime=datetime.datetime.fromtimestamp(int(actualTrade["occurredAt"]/1000.0)) 
                if ((tradeTime.date() != startTime.date()) and not simulationMode):
                    continue
                newdateTime=startTime -datetime.timedelta(hours=1)
                if ((tradeTime <  newdateTime)  and not simulationMode):#old trade--> dont fire any alert
                    continue
                alert=discordAlert(lastTrade)
                NewTradeAlert=alert.NewPositionAlertMessage(kwargs["etoroprofile"]) # construct the alert to send
                if lastTrade.openClose=="close":
                    NewTradeAlert=alert.ClosedAlertMessage(kwargs["etoroprofile"]) # construct the alert to send
                allSubscribers=etoroChannelsMap[kwargs["etoroprofile"]]#subscribeds channels
                #check how many ther traders use 
                success,AlltradersWithThisTrade=ScrapEtoroDb.GetTradersWhoHaveSuchPosition(lastTrade.market,lastTrade.direction)
                analysis=""

                #now send the alert 
                # discordSubscriber
                # id, etoroProfile, guildId, channelId, channel_owner, date, filterMode, filterValue
                for discordSubscriber in allSubscribers:
                    if lastTrade.openClose=='open':
                        status,myListOFFollowedPrfiles=ScrapEtoroDb.GetMyListFollowedProfiles(guild_id=discordSubscriber[2],\
                                channel_id=discordSubscriber[3],owner_id=discordSubscriber[4])

                        numberOfTrdersWithSamePosition=0
                        TradersAsString=""
                        for profile in myListOFFollowedPrfiles:
                            if profile in AlltradersWithThisTrade and kwargs["etoroprofile"]!=profile: 
                                numberOfTrdersWithSamePosition+=1
                                info="{}({})".format(profile,AlltradersWithThisTrade[profile]) #get the average
                                TradersAsString+=info
                                TradersAsString+=" ,"
                        TradersAsString = TradersAsString[:-1]
                        if discordSubscriber[6] and  numberOfTrdersWithSamePosition<discordSubscriber[7]:
                            continue # no alert because condition is not met
                        if  (numberOfTrdersWithSamePosition>2  and not discordSubscriber[6]) : #subscriber activated Filter Mode, or just normal use
                                analysis=" {} investors have opened the same position {} ".format(numberOfTrdersWithSamePosition,TradersAsString)

                    if discordSubscriber[6] and not analysis:  #user choosed to filter the alerts
                        continue

                    instrument_image=""
                    if lastTrade.image:
                        instrument_image=lastTrade.image
                    else:
                        instrument_image=alertsdb.GetInstrumentIconImage(lastTrade.market.upper())


                    message = {
                        "profile":kwargs["etoroprofile"],
                        "guildId":discordSubscriber[2],
                        "channel_id":discordSubscriber[3],
                        "owner_id":discordSubscriber[4],
                        "image":AllFollowedProfiles[kwargs["etoroprofile"]]['image'],
                        "result": NewTradeAlert,
                        "analysis":analysis,
                        "direction":lastTrade.direction,
                        "rate":lastTrade.rate,
                        "leverage":lastTrade.leverage,
                        "openclose":lastTrade.openClose,
                        "NetProfit":lastTrade.NetProfit,
                        "percentage":lastTrade.percentage,
                        "market":lastTrade.market ,
                        "instrument_image":instrument_image
                    }
                    jsonResult= json.dumps(message)
                    serverToClientsdMessages.put(jsonResult)
                log.debug("NewTradeAlert= {}".format(NewTradeAlert))

            else: #exists: check if it has been closed instead
                if ((oldTradeDetails[7]=="open") and   (lastTrade.openClose=="close") ):
                    #trade closed 
                    #wissem 06032021: to minimize the siz of the database, we better remove the closed trades from the database
                    ScrapEtoroDb.ReplaceTradeIntoDatabase(kwargs["etoroprofile"],lastTrade)
                    #check if the trade is new
                    tradeTime=datetime.datetime.fromtimestamp(int(actualTrade["occurredAt"]/1000.0)) 
                    if ((tradeTime.date() != startTime.date()) and not simulationMode):
                        continue
                    if ((tradeTime.time() <  (startTime -datetime.timedelta(hours=1)).time() ) and not simulationMode):#old trade--> dont fire any alert
                        continue
                    alert=discordAlert(lastTrade)
                    closeAlertMessage=alert.ClosedAlertMessage(kwargs["etoroprofile"])
                    for discordSubscriber in etoroChannelsMap[kwargs["etoroprofile"]]:
                        instrument_image=""
                        if lastTrade.image:
                            instrument_image=lastTrade.image
                        else:
                            instrument_image=alertsdb.GetInstrumentIconImage(lastTrade.market.upper())
                        message = {
                            "profile":kwargs["etoroprofile"],
                            "guildId":discordSubscriber[2],
                            "channel_id":discordSubscriber[3],
                            "owner_id":discordSubscriber[4],
                            "image":AllFollowedProfiles[kwargs["etoroprofile"]]['image'],
                            "result": closeAlertMessage,
                            "direction":lastTrade.direction,
                            "rate":lastTrade.rate,
                            "leverage":lastTrade.leverage,
                            "openclose":lastTrade.openClose,
                            "NetProfit":lastTrade.NetProfit,
                            "market":lastTrade.market,
                            "instrument_image":instrument_image
                        }
                        jsonResult= json.dumps(message)
                        serverToClientsdMessages.put(jsonResult)
                    log.debug("closeAlertMessage= {}".format(closeAlertMessage))
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in ConsumeDataFromScraper {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))



#first load the data from the database
ReloadDatabase()



#Now Start headless chrome and make the connection
#myconnection =etorolib.Etoro("wislina","d37de0fa10")
#myconnection =etorolib.Etoro()


def cidUpdate(**kwargs):   #(name,cid)
    newData=generalFunctions.get_trader_aggregated_positions(proxy=myProxyProvider.GetOneProxy(),user='wiswis15',password='CNNWPYLAFGIV9AOO8RO9P6WV',**kwargs)
    #newData=myconnection.get_trader_aggregated_positions(kwargs["cid"])
    dataToConsume=("cidUpdate",kwargs,newData)
    etoroResponseQueue.put(dataToConsume)


def currentPositionsUpdate(**kwargs):
    try:
        allInstruments= TraderCidMap[kwargs["etoroprofile"]]
        newData=generalFunctions.get_all_current_positions(proxy=myProxyProvider.GetOneProxy(),user='wiswis15',password='CNNWPYLAFGIV9AOO8RO9P6WV',**kwargs)
        dataToConsume=("currentPositionsUpdate",kwargs,newData)
        etoroResponseQueue.put(dataToConsume)
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in currentPositionsUpdate :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))


def closedPositionsUpdate(**kwargs):
    newData=myconnection.get_closed_positions(kwargs["cid"],"real")
    dataToConsume=("closedPositionsUpdate",kwargs,newData)
    etoroResponseQueue.put(dataToConsume)

etoroscraper=EtoroScraping.EtoroScraper()  # for now it is one instance, can be multiple later

def GetDataFromScraper(**kwargs):   #(name,cid)
    global etoroscraper
    try:
        newData=etoroscraper.GetLatestTrades(proxy=myProxyProvider.GetOneProxy(),user='wiswis15',password='CNNWPYLAFGIV9AOO8RO9P6WV',**kwargs)
        if not newData: # no data 
            return
        dataToConsume=("DataFRomScraperUpdate",kwargs,newData)
        etoroResponseQueue.put(dataToConsume)
    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in GetDataFromScraper :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))



def AddCidJob(**kwargs):
    newjob=("cidUpdate",kwargs)
    etoroRequestQueue.put(newjob)

def AddCurrentPositionsJob(**kwargs):
    newjob=("currentPositionsUpdate",kwargs)
    etoroRequestQueue.put(newjob)

def AddClosedPositionsJob(**kwargs):
    newjob=("closedPositionsUpdate",kwargs)
    etoroRequestQueue.put(newjob)

def AddScraperJob(**kwargs):
    newjob=("Scraper",kwargs)
    etoroRequestQueue.put(newjob)



FunctionsEtoroRequestsDisctionary={
    "cidUpdate":cidUpdate,
    "currentPositionsUpdate":currentPositionsUpdate,
    "closedPositionsUpdate":closedPositionsUpdate,
    "Scraper":GetDataFromScraper
}

def RequestDataFromEtoro():
    """
    Only function to connect to Etoro
    """
    while True:
        try:
            task = etoroRequestQueue.get(block=True)
            taskName=task[0]
            taskDetails=task[1]
            if "InstrumentID" not in taskDetails:
                taskDetails["InstrumentID"]=0 #dummy
            FunctionsEtoroRequestsDisctionary[taskName](cid=taskDetails["cid"],InstrumentID=taskDetails["InstrumentID"],\
                etoroprofile=taskDetails["etoroprofile"])
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in RequestDataFromEtoro {}:{}:{} {} {} {}".format(task[0],taskDetails["etoroprofile"],exc_type, fname, exc_tb.tb_lineno,ex))
        finally:
            time.sleep(timeBetweeeneachEtoroRequest)
    

#lets start our Server
ServerThread=Thread(target=start_server)
ServerThread.start()



RequestDataFromEtoroThread=Thread(target= RequestDataFromEtoro)
RequestDataFromEtoroThread.start()


def ScrapEtoro():
    """
    This the ONLY thread scraping Etoro
    """
    time.sleep(15)# give some time for the initialization
    ScrapEtoroDb=alertsdb("ScrapEtoro")
    while True:
        try:
            
            for etoroProfile in AllFollowedProfiles:
                AllFollowedProfilesLock.acquire()
                GetDataFromScraper(etoroprofile=AllFollowedProfiles[etoroProfile]['profile'],cid=AllFollowedProfiles[etoroProfile]['cid'])
                if AllFollowedProfilesLock.locked():
                    AllFollowedProfilesLock.release()
                time.sleep(scrapingFrequency)
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in ScrapEtoro {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
        finally:
            if AllFollowedProfilesLock.locked():
                AllFollowedProfilesLock.release()
            
            



#start a cron for each premium trader, to get SL,Alerts
#for etoroProfile in premiumProfiles:
    #id, profile, cid, date, sltpchangenotifications, slalerts, slalertlevel, image
#    schedule.every(freq).seconds.do(AddCidJob, etoroprofile=etoroProfile[1],cid=etoroProfile[2])

def restart():
    if  sys.platform=="win32":
        win32api.InitiateSystemShutdown()  
    else:#link
       os.system('reboot now')
       log.error("rebooting the machine")
schedule.every().day.at("00:00").do(restart)


FunctionsConsumeDisctionary={
    "cidUpdate":ConsumeCid,
    "currentPositionsUpdate":ConsumeCurrentPositions,
    "closedPositionsUpdate":ConsumeClosedPositions,
    "DataFRomScraperUpdate":ConsumeDataFromScraper
}

def ConsumeReceivedDataFromEtoro():
    ''' Main job to request new data from ETORO, it will get the jobs from the queue '''
    ConsumeReceivedDataFromEtoroDb=alertsdb("ConsumeReceivedDataFromEtoro")
    while True:
        try:
            task = etoroResponseQueue.get(block=True)
            etoroprofileName=task[1]["etoroprofile"]
            cid=task[1]["cid"]
            if "InstrumentID" in task[1]:
                InstrumentID=task[1]["InstrumentID"]
            else:
                InstrumentID=0
            newData=task[2]
            FunctionsConsumeDisctionary[task[0]](ConsumeReceivedDataFromEtoroDb,etoroprofile=etoroprofileName,cid= cid,data=newData,InstrumentID=InstrumentID)
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in ConsumeReceivedDataFromEtoro function name={}-{} {} {} {}".format(task[0],exc_type, fname, exc_tb.tb_lineno,ex))




ConsumeReceivedDataFromEtoroThread=Thread(target= ConsumeReceivedDataFromEtoro)
ConsumeReceivedDataFromEtoroThread.start()


def search(list, ip,port):
    for i in range(len(list)):
        localconnection, address = list[i]
        localip, localport = str(address[0]), str(address[1])        
        if ((localip == ip) and (localport==port)):
            return True,i
    return False




def clientThread(connection, ip, port, max_buffer_size = 5120):
   while True:
        try:
            client_input = receive_input(connection, max_buffer_size)
            log.debug("received: {} from one client".format(client_input))
            if "--QUIT--" in client_input:
                print("Client is requesting to quit")
                connection.close()
                print("Connection " + ip + ":" + port + " closed")
                is_active = False
            #else:
                #print("Received Message: {}".format(client_input))
                #connection.sendall("Server acknowledge reception of: {}".format(client_input).encode("utf8"))
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            #log.error("Exception in receive_input(): looks like one client has disconnected. Removing it from the list of clients")
            log.info("One client has disconnected, Removing it from the List. Remaining clients={}".format(len(listOFConnectedClients)-1))
            result=search(listOFConnectedClients,ip,port)
            if result[0]:
                del listOFConnectedClients[result[1]]
            return
        


def receive_input(connection, max_buffer_size):
    client_input = connection.recv(max_buffer_size)
    client_input_size = sys.getsizeof(client_input)
    if client_input_size > max_buffer_size:
        print("The input size is greater than expected {}".format(client_input_size))
    decoded_input = client_input.decode("utf8").rstrip()
    jsonReceived=json.loads(decoded_input)
    funcName=jsonReceived["method"]
    try :
        if funcName in FunctionsDictionary:
            ClientsToServerMessages.put(decoded_input) #append received data to the buffer
            return "Command Received!"
        else:
            return "Command Does not exist!"
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in receive_input():{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))



def process_receivedMessages():
    """
    Function to consume all the received requests
    """
    process_receivedMessagesAlertDb=alertsdb("process_receivedMessages")
    #print("Processing the input received from client")
    #return "received message from clinent:{} \n".format(input_str)
    while True:
        input=ClientsToServerMessages.get(block=True)
        try:
            inputJson = json.loads(input)
            functionname=inputJson["method"]
            args=inputJson["params"]
            FunctionsDictionary[functionname](process_receivedMessagesAlertDb,**args)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in process_receivedMessages:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            time.sleep(2)
            continue


ProcessInputFromClientsThread=Thread(target=process_receivedMessages)
ProcessInputFromClientsThread.start()



def sendMessagestoAllclients(): 
    """
    dispatch all server messages to all clients
    """
    while True:
        try:
            message=serverToClientsdMessages.get(block=True)#block and wait for new messages
            # Prefix each message with a 4-byte length (network byte order)
            msg = struct.pack('>I', len(message)) + str.encode(message)
            for client in listOFConnectedClients : 
                client[0].send(msg)
            log.debug("Server sending message: {}".format(message))
        except Exception as ex:
            log.error("Exception in serverToClientsdMessages:{}".format(ex))





DispatchOutputThread=Thread(target=sendMessagestoAllclients)
DispatchOutputThread.start()





def follow(alertsDb,**args):
    global freq
    global premiumChannel
    try:
        result=""
        #first check the Number of Followed profiles
        success,myFollowedProfiles=alertsDb.GetMyListFollowedProfiles(args["guild_id"],args["channel_id"],args["owner_id"])
        if password != args['password'] and len(myFollowedProfiles)>= MaxNumberOfFollwers  :
            result="Sorry, This version is limited to {} profiles, maybe you want to replace one!".format(MaxNumberOfFollwers)

        if not result:
            #first check if the profile exists:
            url="https://www.etoro.com/api/streams/v2/streams/user-trades/{}?&languagecode=en-gb&pageNumber=1".format(args["etoroProfile"])
            request=requests.get(url)
            if request.status_code !=200:
                result="Profile Not Found!"
            else:
                if not alertsDb.DoesEtoroProfileExists(args["etoroProfile"]):
                    cid=generalFunctions.get_trader_cid(args["etoroProfile"])
                    #profilePhtoPath=myconnection.GetProfilePicture(profile)
                    #alertsDb.AddEtoroProfile(profile,cid,profilePhtoPath)
                    alertsDb.AddEtoroProfile(args["etoroProfile"],cid)
                    trader_conf=(args["etoroProfile"],cid)
                    #cidUpdate(etoroprofile=args["etoroProfile"],cid=cid) #add get all current positions

                success,result=alertsDb.FollowProfile(args["etoroProfile"],args["guild_id"],args["channel_id"],args["owner_id"])
        #create a json object result
        message = {
        "type": "commandReplay",
        "profile":args["etoroProfile"],
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "image":"",
        "result": result
        }
        jsonResult= json.dumps(message)
        serverToClientsdMessages.put(jsonResult)
        ReloadDatabase() # reload the database
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in follow:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))



def StopFolllowing(alertsDb,**args):
    try:
        #first check if the profile exists:
        """
        url="https://www.etoro.com/api/streams/v2/streams/user-trades/{}?&languagecode=en-gb&pageNumber=1".format(profile)
        request=requests.get(url)
        result=(False,"")
        if request.status_code !=200:
            result=(False,"You are already not following!  AND profile not found! :rolling_eyes:  :rolling_eyes:  ")
        else:
            result=alertsDb.StopFollowingProfile(profile,guildId,channel_id,owner_id)"""

        result=alertsDb.StopFollowingProfile(args["etoroProfile"],args["guild_id"],args["channel_id"],args["owner_id"])
        #create a json object result
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"] ,
        "result": result[1]
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        ReloadDatabase() # reload the database
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in StopFolllowing:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))


def RemoveSubscription(alertsDb,**args):
    #for now just skipe this part -->it is indeed working but lets enable it later
    try:
        #first check if the profile exists:
        result=alertsDb.RemoveSubscription(args["etoroProfile"],args["guild_id"],args["channel_id"],args["owner_id"])
        #create a json object result
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"] ,
        "result": ""
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        #serverToClientsdMessages.put(jsonResult) no need to send any message
        ReloadDatabase() # reload the database
        if result:
            log.error("RemoveSubscription called on profile {} channelId {}".format(args["etoroProfile"],args["channel_id"]))
        else:
            log.error("Failed in RemoveSubscription called on profile {} channelId {}".format(args["etoroProfile"],args["channel_id"]))
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in RemoveSubscription:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))


def MyTradersList(alertsDb,**args):
    try:
        myListAsString=""
        result=alertsDb.GetMyListFollowedProfiles(args["guild_id"],args["channel_id"],args["owner_id"])
        if not result[0]:
            myListAsString= "Something Went Wrong!"
        elif (len(result[1])==0):
             myListAsString= "You are not following any one! Lets get Started :wink:"
        else:
            for trader in result[1]:
                myListAsString+=trader
                myListAsString+=" \n"
        #create a json object result
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "result": myListAsString
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in StopFolllowing:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

def SetEtoroProfile(alertsDb,**args):
    """
    set etoro profile of the user, for later data analysis
    """
    try:
        query,result=alertsDb.UpdateEtoroNameChannelUser(args["etoroProfile"],args["guild_id"],args["channel_id"],args["owner_id"])

        #create a json object result
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "result": result
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in myEtoro:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))



def filter(alertsDb,**args):
    try:
        query,result=alertsDb.SetFilter(args["guild_id"],args["channel_id"],args["owner_id"],args["number"])
        #create a json object re
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "result": result
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in myEtoro:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

def nofilter(alertsDb,**args):
    try:
        query,result=alertsDb.SetFilter(args["guild_id"],args["channel_id"],args["owner_id"],0)
        #create a json object re
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "result": result
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in myEtoro:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

def GetMostCommonStocks(alertsDb,**args):
    """Returns list of commoon stocks, ranked
    """
    try:
        allStocks=generalFunctions.GetAggregatedStocks(alertsDb,**args)
        result=""
        reducedList = allStocks[:15]
        for stock in reducedList :  
            if stock[1][0]<2:  #only show stocks if they are common between more than 2 peoples
                continue
            result += "**{}**".format(stock[0].upper())
            industry= generalFunctions.GetIndustry(stock[0])
            if industry:
                result += ' ,'
                result+=industry #add the industry
            result += " ,"
            #calculate the average
            result += str(stock[1][0])
            result += ' investors, '
            result += 'average price= '
            result += "{:.2f}".format(stock[1][1])
            result += "\n"

        if not result:
            result="Sorry, No Common Stocks! "


        #create a json object re
        message = {
        "type": "commandReplay",
        "guildId":args["guild_id"],
        "channel_id":args["channel_id"] ,
        "owner_id":args["owner_id"],
        "result": result
        }
        jsonResult= json.dumps(message)
        #serverToClientsdMessagesMutex.acquire()
        serverToClientsdMessages.put(jsonResult)
        return (jsonResult)  # return the id of the sender + result
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in GetMostCommonStocks:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
    
    return allStocks

FunctionsDictionary={
    "follow":follow,
    "StopFolllowing":StopFolllowing,
    "MyTradersList":MyTradersList,
    "RemoveSubscription":RemoveSubscription,
    "SetEtoroProfile":SetEtoroProfile,
    "filter":filter,
    "nofilter":nofilter,
    "commonStocks":GetMostCommonStocks
}




#last step-->start scraping
#disabled it to test new way
ScrapEtoroThread=Thread(target= ScrapEtoro)
ScrapEtoroThread.start()

def SendPushMessageToallUsers():
    """"
    Send a message to all users, it reads a file, read it and send its content--> remove it
    """

    messageContent=""
    Filepath=os.path.join(pathlib.Path(__file__).parent.absolute(),MessageFile)
    if os.path.exists(Filepath):
        with open(Filepath, 'r') as file:
            messageContent = file.read()
        os.remove(Filepath)
    else:
        return


    #id, etoroProfile, guildId, channelId, channel_owner, date, filterMode, filterValue, premium
    success,allClients=mainThreadAlertDb.GetAllDiscordClients()
    if not success:
        log.error("Error readding message File")
    
    Servers=[]
    for discordSubscriber in allClients :
        if (discordSubscriber[2]+discordSubscriber[3]) in Servers: 
            continue #send only 1 message to each channel
        Servers.append(discordSubscriber[2]+discordSubscriber[3])
        message = {
            "profile":discordSubscriber[1],
            "guildId":discordSubscriber[2],
            "channel_id":discordSubscriber[3],
            "owner_id":discordSubscriber[4],
            "generalMessage": messageContent,
            "result":""
        }
        jsonResult= json.dumps(message)
        serverToClientsdMessages.put(jsonResult)
    log.debug("generalMessage= {}".format(messageContent))

if __name__ == "__main__":
    #creating the first main thread, responsible to read all new clients
    interruptsignal=False
    try:
        while not interruptsignal:
            try:
                schedule.run_pending()
                SendPushMessageToallUsers()
            except Exception as ex: # pylint: disable=broad-except
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                log.error("Exception in the main function : {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
                time.sleep(2)

    except KeyboardInterrupt:
        interruptsignal=True
    finally:
    #    exit_handler()
        sys.exit(  )




