import json
import urllib.request
import threading
import trade
import discord
from discord.ext import commands
import asyncio
from datetime import datetime,time,timedelta
import datetime as dt
import logging
import argparse
import sys
import os
import alertsdatabase as alertsdb
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from loglib import logger as log 

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
    "-log", 
    "--log", 
    default="warning",
    help= "Provide logging level: Example --log debug, default=warning")

options = parser.parse_args()
levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG
}
level = levels.get(options.log.lower())
if level is None:
    raise ValueError(
        f"log level given: {options.log}"
        f" -- must be one of: {' | '.join(levels.keys())}")

#addd file handler
fh = logging.FileHandler(logFilePath)
fh.setLevel(level) 

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(level)


# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# add ch and fh to logger
logger.addHandler(ch)
logger.addHandler(fh)




#load the map etoro-->channels
etoroChannelsMap={}
followedProfiles=alertsdb.GetAllFollowedProfiles()[1]
for followedProfile in followedProfiles:
    subscribers=alertsdb.GetDiscordListOfSubscribers(followedProfile)




intents = discord.Intents(messages=True, guilds=True)
intents.members = True

bot = commands.Bot(command_prefix="!",intents=intents)

target_channelId = 793519549625794600   #customizedalerts in Test server

channelFromMessage=None

UserTrades="https://www.etoro.com/api/streams/v2/streams/user-trades/{}?&languagecode=en-gb&pageNumber=1"
UserDiscussions="https://www.etoro.com/api/streams/v2/streams/user-discussions/{}?languagecode=en-gb"
getTradesApi=UserTrades

tradersList=["kirinboi","lara2758","veselin2020","wislina","golliwael","leonardovoss"]




@bot.event
async def on_ready() :
    print('Bot is ready')



@bot.event
async def on_guild_available(guild):
    print("Hello !! AlertWissem is Active on guild {}".format(guild.name))



async def DetectLatestTrades():

    """
    get the latest trade of the guild
    """       
    try:
        await bot.wait_until_ready()
        print("DetectLatestTrades is being called \n")
        numberOfCyclces=0
        while True:
            lastReceivedTime=dt.datetime.now()
            time = 60 #seconds
            await asyncio.sleep(time)
            numberOfCyclces+=1
            if numberOfCyclces > 100:  
                numberOfCyclces=0
            if numberOfCyclces%2==0:# 1 cycle from the usertrades and the next one from userDiscussions
                getTradesApi=UserTrades
            else:
                getTradesApi=UserDiscussions
            
            try:
                for trader in tradersList:      
                    getTradesApi=getTradesApi.format(trader)#update the link with ETORO profile
                    with   urllib.request.urlopen(getTradesApi) as jsonTrades:
                        data = json.loads(jsonTrades.read().decode())
                        channel = bot.get_channel(target_channelId)
                        for actualTrade in data :       
                            #extracting the data
                            lastTrade=trade.Trade(actualTrade['id'])
                            if not lastTrade.ExtractAllData(actualTrade):
                                continue
                            
                            lastTradeTime=datetime.fromtimestamp(int(float(lastTrade.occuredAt)/1000.0)) # need it to track time
                            

                            if lastTradeTime > lastReceivedTime :
                                now = dt.datetime.now()
                                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

                                #beautify the text a bit
                                if lastTrade.direction=="Long":
                                    lastTrade.direction="Long :rocket: :rocket: :rocket:"
                                else:
                                    lastTrade.direction="Short :shorts: :shorts: :shorts: "

                                #beautify the text a bit
                                if lastTrade.gainLoss>0.0:
                                    lastTrade.gainLoss=str(lastTrade.gainLoss)+ " :muscle:  :muscle: "
                                elif lastTrade.gainLoss<0.0:
                                    lastTrade.gainLoss=str(lastTrade.gainLoss)+ " :weary: :weary: "
                                    

                                #send the Alert
                                alert=""
                                if lastTrade.order:
                                    alert+="THIS is an ORDER for the following position:\n"
                                if lastTrade.openClose=="Close":
                                    alert+="{} Trader: {} \n Position:  Market= {}, Type:Close, Direction ={},  Leverage ={} :gun: , Rate ={}, gain= {} \n".format(formatted_date,trader,lastTrade.displayName,lastTrade.direction,lastTrade.leverage,lastTrade.rate,lastTrade.gainLoss)
                                elif lastTrade.openClose=="Open": # trade is of type OPEN
                                    alert+="{} Trader: {} \n Position:  Market= {}, Type:Open :green_circle: , Direction ={}, Percentage ={}, Leverage ={}, Rate ={}  \n".format(formatted_date,trader,lastTrade.displayName,lastTrade.direction,lastTrade.percentage,lastTrade.leverage,lastTrade.rate)
                                else:#lastTrade.openClose  is empty
                                    alert+="{} Trader: {} \n Position:  Market= {}, Type:XXXXXX , Direction ={}, Leverage ={}, Rate ={}  \n".format(formatted_date,trader,lastTrade.displayName,lastTrade.direction,lastTrade.leverage,lastTrade.rate)

                                #add common text
                                marketlink="Market: https://www.etoro.com/markets/"
                                marketlink+=lastTrade.market
                                alert+=marketlink
                                alert+="\n"
                                if lastTrade.messageBody:
                                    alert+="Message: "
                                    alert+=lastTrade.messageBody
                                    alert+="\n"
                                await channel.send(alert)
                                #print(alert)
            except Exception as ex:
                log.error("Exception {} caught while getting and analysing data".format(ex))
                continue
    except:
        log.error("DetectLatestTrades function killed ")
        return



@bot.command(name='alertsStatus')
async def listOfCommands(ctx):
    returnMessage= str("Thanks god im alive :blush:  :blush: ")
    await ctx.send(returnMessage)               





bot.loop.create_task(DetectLatestTrades())
#run event loop for the bot
bot.run('NzkzNTE4NjEyMzAzNzA4MTYw.X-tbzA.Sgmzw2TPeWWksz5pc08RpH48Hls')

