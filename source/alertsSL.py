
import threading
import discord
from discord.ext import commands
import asyncio
from datetime import datetime,time,timedelta
import datetime as dt
import UserSLAlert
import Position
import database
import json
import urllib.request
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import sys
import os
import http.client, urllib.request, urllib.parse, urllib.error, base64
from requests.auth import HTTPBasicAuth  
from fake_useragent import UserAgent


if  sys.platform=="win32":
    chrome_driver_path =os.path.join(os.path.dirname(os.path.realpath(__file__)),'chromedriver.exe')  
else:#link
    chrome_driver_path ='/usr/bin/chromedriver'
    

# chrome_options = Options()
# chrome_options.add_argument('--headless')

# webdriver = webdriver.Chrome(  executable_path=chrome_driver_path, options=chrome_options)
# WebDriverWait(webdriver,10) # wait 10 seconds



# path="https://www.etoro.com/sapi/trade-data-real/live/public/portfolios?cid=15553291&client_request_id=e23fede0-2822-42b4-8ddf-14e405ed7aaa"
# webdriver.get(path)
# print(webdriver.page_source)
# print(webdriver.execute_script("return JSON.stringify(model);"))

try:
    import requests
    s = requests.session()
    # Note that domain keyword parameter is the only optional parameter here
    my_cookies = {'_gcl_au':'1.1.848823613.1601885851','_hjAbsoluteSessionInProgress':'1','G_AUTHUSER_H':'0'}
    requests.utils.add_dict_to_cookiejar(s.cookies, my_cookies)
    ua = UserAgent()
    print(ua.chrome)
    my_headers = {'User-Agent':str(ua.chrome)}
    print(my_headers)
    s.headers.update(my_headers)
    response = s.get("https://www.etoro.com/sapi/trade-data-real/live/public/portfolios?cid=15553291" )
    data=response.json()
except Exception as e:
    print("exception {}".format(e))



wissem=UserSLAlert.UserSLAlert("wislina",15553291,771615049701523487)
wael=UserSLAlert.UserSLAlert("golliwael",13735765,364055141256790016)


listOfSLAlertsSubscribers=[wissem]

instrumentIdNameMap={} #dictiory containing the mapping between the name and the instrucmnet id
def FillnameInstrumentIdMap():
    global instrumentIdNameMap
    mycursor = database.mydb.cursor()
    query = "SELECT * FROM instrumentidnamemap " 
    mycursor.execute(query)
    records= mycursor.fetchall()
    for record in records:
        instrumentIdNameMap[record[0]]=record[1] # record[0]:id, record[1]=name
    print("instrumentIdNameMap size= {}".format(len(instrumentIdNameMap)))


FillnameInstrumentIdMap()

intents = discord.Intents(messages=True, guilds=True)
intents.members = True

bot = commands.Bot(command_prefix="!",intents=intents)







@bot.event
async def on_ready() :
    print('Bot is ready')




@bot.event
async def on_guild_available(guild):
    print("Hello !! AlertsSL is Active on guild {}".format(guild.name))



async def AlertStopLosses():
    
    """
    Alert the closed stop losses for all the users
    """       
    await bot.wait_until_ready()
    print("AlertStopLosses is being called \n")
    numberOfCyclces=0
    while True:
        lastReceivedTime=dt.datetime.now()
        cycle = 60 #seconds
        await asyncio.sleep(cycle)
        numberOfCyclces+=1
        if numberOfCyclces > 2:  # just for display each 5 mns
            #print("alertsSL is alive!")
            numberOfCyclces=0
        
        # update the list of open trades
        portfolio=[]
        for SLsubscriber in listOfSLAlertsSubscribers: #iterate thrugh all subscribers
            portfolio=SLsubscriber.GetPortfolio()# get portfolio first
            alertMessage=""
            for instrument in portfolio:
                alertMessage+=" {} is are investing in {} \n".format(SLsubscriber.etoroid,instrumentIdNameMap[instrument])
                try:
                    detailsRequest="https://www.etoro.com/sapi/trade-data-real/live/public/positions?InstrumentID={}&cid={}&format=json".format(instrument,SLsubscriber.cid)
                    print(detailsRequest)
                    jsonPortfolio = urllib.request.urlopen(detailsRequest)
                    data = json.loads(jsonPortfolio.read().decode('utf-8'))
                except Exception as ex:
                    print("Exception in AlertStopLosses, details= {}".format(ex))
                    time.sleep(2)
                    continue
                for position in data["PublicPositions"]:#iterate through the positions
                    currentrate=position["CurrentRate"]
                    stopLossrate=position["StopLossRate"]
                    openrate=position["OpenRate"]
                    isbuy=position["IsBuy"]
                    comparerate=openrate*((SLsubscriber.alertlevel/100)+1)
                    print("current rate ={} and SL ={} comparerate={}".format(currentrate,stopLossrate,comparerate))
                    if (isbuy and (currentrate < comparerate)):
                        print("STOP LOSS Alert!, BUY positin id {} with market = {} has very close SL".format(position["PositionID"],instrumentIdNameMap[instrument]))
                    elif currentrate> comparerate:#SELL position
                        print("STOP LOSS Alert!, SELL positin id {} with market = {} has very close SL".format(position["PositionID"],instrumentIdNameMap[instrument]))





            #await bot.get_user(SLsubscriber.discordId).send(allInstrumentsMessage)
            

@bot.command(name='alertsStatus')
async def listOfCommands(ctx):
    returnMessage= str("Thanks god im alive :blush:  :blush: ")
    await ctx.send(returnMessage)  

bot.loop.create_task(AlertStopLosses())
#run event loop for the bot
bot.run('NzkzNTE4NjEyMzAzNzA4MTYw.X-tbzA.Sgmzw2TPeWWksz5pc08RpH48Hls')

