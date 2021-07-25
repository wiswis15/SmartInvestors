import sys
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import threading
import discord
from discord.ext import commands
import datetime as dt
import json
import threading
import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import alertsdatabase as alertsdb
import etoro as etorolib
from loglib import logger as log 
from discord.utils import get
from discord.ext.tasks import loop
import schedule
import time
import hashlib
import pickle
import trade 
from  discordAlerts import DiscordAlert as discordAlert
import database



#discord bot part
intents = discord.Intents(messages=True, guilds=True)
intents.members = True
bot = commands.Bot(command_prefix="!",intents=intents)


#get all the etoro profiles being followed
(status,AllFollowedProfiles)=alertsdb.GetAllFollowedProfiles()
if (not status):
    log.critical("Coudl not read the list of followed etoro profiles!")


#load the map etoroProofiles-->channels
etoroChannelsMap=dict()
subscribers=[]  # empty list
for followedProfile in AllFollowedProfiles:
    (status,subscribers)=alertsdb.GetDiscordListOfSubscribers(followedProfile[1]) #profile column which is the etoro name
    if not status:
        log.critical("Error while loading the map of subscribers")
    etoroChannelsMap[followedProfile[1]]=[]
    for subscriber in subscribers:
        etoroChannelsMap[followedProfile[1]].append(subscriber)




myconnection =etorolib.Etoro("wislina","d37de0fa10")

freq=1 #for now, lets assume same frequency for every trade=1mn
portfolioHAshHistory=dict() # map that keep track of the hashlib.hexdigest()  of every followed trader




''' Main cron for a trader '''
def trader_cron(trader_conf):
        # update the list of open trades
        etoroTrader=trader_conf[0]
        etoroTraderCid=trader_conf[1]
        portfolio=[]
        portfolio=myconnection.get_trader_aggregated_positions(etoroTraderCid)  #cid
        #now calculate the hashValue of the new portfolio
        newhash=hashlib.md5(pickle.dumps(portfolio)).hexdigest() 
        if newhash ==portfolioHAshHistory[etoroTrader]:
            return #hash did not change--> no change in portfolio History
        #portfolio changed
        #build set of instruments in the portfolio
        setOfInstrucmnets =set()
        for receivedPosition in portfolio:
            setOfInstrucmnets.add(receivedPosition["InstrumentID"])
        
        allPositioons=[]
        for instrument in setOfInstrucmnets:
            for position in myconnection.get_all_current_positions(etoroTraderCid,instrument,"real"):
                allPositioons.append(position)
            #time.sleep(1)  # wait some time, otherwise, etoro may block us
        for receivedPosition in allPositioons:
            newTrade=trade.Trade(receivedPosition["PositionID"])
            newTrade.ExtractDetails(receivedPosition)#extract all informatin
            newTrade.market=database.GetInstrumentName(instrument)
            newTrade.displayName=newTrade.market
            (exists,tradeDetails)=alertsdb.DoesTradeExists(receivedPosition["PositionID"])
            if exists:
                oldData=trade.Trade(receivedPosition["PositionID"])
                oldData.stoploss=tradeDetails[10]
                oldData.takeprofit=tradeDetails[11]
                alert=discordAlert(newTrade)
                (slTpMessagealert,SLCautionAlert)=alert.DetectChangeInSLTP(etoroTrader,newTrade,oldData)
                #update it and check if stop loss aggregated_positions_changed
                if slTpMessagealert:# SL or TP changed
                    #update the database:
                    alertsdb.ReplaceTradeIntoDatabase(etoroTrader,newTrade)
                    #for discordSubscriber in etoroChannelsMap(trader_conf[0]):
                    #    channel = bot.get_channel(discordSubscriber)
                    #    channel.send(slTpMessagealert)#alert the change in SL or/and TP
                    log.debug("Change in SL/TP Alert:  {}".format(alert))
                if SLCautionAlert:# Stop loss caution alert
                    #update the database:
                    #for discordSubscriber in etoroChannelsMap(trader_conf[0]):
                    #    channel = bot.get_channel(discordSubscriber)
                    #    channel.send(slTpMessagealert)#alert the change in SL or/and TP
                    log.debug("STOP loss  Caution: {}".format(alert))
                
         
            else:#new trade -->insert it
                alertsdb.InsertTradeIntoDatabase(etoroTrader,newTrade)
                #now send the alert 
                alert=discordAlert(newTrade)
                discordAlertMessage=alert.NewPositionAlertMessage(etoroTrader) # content to send
                #for discordSubscriber in etoroChannelsMap(trader_conf[0]):
                #    channel = bot.get_channel(discordSubscriber)
                #    channel.send(discordAlertMessage)
                log.debug("newTrade= {}".format(alert))

        #now get the closed positions
        closedPosistions=myconnection.get_closed_positions(etoroTraderCid,"real")
        for closedpos in closedPosistions:
            newTrade=trade.Trade(receivedPosition["PositionID"])
            newTrade.ExtractDetails(receivedPosition)#extract all informatin
            newTrade.openClose="close"
            newTrade.market=database.GetInstrumentName(instrument)
            newTrade.displayName=newTrade.market
            (exists,tradeDetails)=alertsdb.DoesTradeExists(receivedPosition["PositionID"])
            if exists and tradeDetails[7]=="open":
                alertsdb.ReplaceTradeIntoDatabase(etoroTrader,newTrade)
                alert=discordAlert(newTrade)
                closeAlertMessage=alert.ClosedAlertMessage(etoroTrader)
                log.debug("ClosedTrade= {}".format(alert))








''' Main cron for a trader, wrapper to catch exceptions '''
def trader_cron_wrapper(trader_conf):
    try:
        trader_cron(trader_conf)
    except Exception as e: # pylint: disable=broad-except
        log.error("Exception in trader_cron: {} : {} ".format(trader_conf[0],e))

for etoroPrfile in AllFollowedProfiles:
    if not status:
        continue
    portfolioHAshHistory[etoroPrfile[1]]="" # starting up--> empty hash to force the ready
    schedule.every(freq).minutes.do(trader_cron_wrapper, (etoroPrfile[1],etoroPrfile[2]))


@bot.event
async def on_ready() :
    log.info('SLAlertBotDiscord is ready')



@bot.event
async def on_guild_available(guild):
    log.info("Hello !! SLAlertBotDiscord is Active on guild {}".format(guild.name))



async def SLAlerts():
    """
    """       
    await bot.wait_until_ready()
    log.info("AlertStopLosses is being called \n")
    while True:
        schedule.run_pending()
        time.sleep(1)

            

@bot.command(name='SLAlertBotDiscordStatus')
async def listOfCommands(ctx):
    returnMessage= str("Thanks god im alive :blush:  :blush: ")
    await ctx.send(returnMessage)  

bot.loop.create_task(SLAlerts())
#run event loop for the bot
bot.run('ODA3NTQ0Mzg5OTMyMDIzODA4.YB5iUg.1zRgOepkNaHZUQGRiAuyug40h9A')
