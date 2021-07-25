import json
import urllib.request
import database
import threading
import trade
import discord
from discord.ext import commands
from datetime import datetime
import asyncio

intents = discord.Intents(messages=True, guilds=True)
intents.members = True

bot = commands.Bot(command_prefix="!",intents=intents)
#target_channelId = 782934587655454731  # taken from discord developper mode automatic-checks

target_channelId = 770796370511659048   #rapid-alerts channel

channelFromMessage=None



UserTrades="https://www.etoro.com/api/streams/v2/streams/user-trades/{}?&languagecode=en-gb&pageNumber=1".format("RapidStock")
UserDiscussions="https://www.etoro.com/api/streams/v2/streams/user-discussions/{}?languagecode=en-gb".format("RapidStock")
getTradesApi=UserTrades

@bot.event
async def on_ready() :
    print('Bot is ready')



@bot.event
async def on_guild_available(guild):
    print("Hello !! RapidAlert is Active on guild {}".format(guild.name))
    if guild.name!= "RapidStock":
        return


async def DetectLatestTrades():
    """
    get the latest trade of rapidStock
    """       
    try:
        await bot.wait_until_ready()
        print("DetectLatestTrades is being called \n")
        numberOfCyclces=0
        while True:
            try:
                time = 60 #seconds
                await asyncio.sleep(time)
                numberOfCyclces+=1
                if numberOfCyclces > 100:  
                    numberOfCyclces=0
                if numberOfCyclces%2==0:# 1 cycle from the usertrades and the next one from userDiscussions
                    getTradesApi=UserTrades
                else:
                    getTradesApi=UserDiscussions

                with   urllib.request.urlopen(getTradesApi) as jsonTrades:

                    data = json.loads(jsonTrades.read().decode())
                    channel = bot.get_channel(target_channelId)

                    for actualTrade in data :       
                        #extracting the data
                        lastTrade=trade.Trade(actualTrade['id'])
                        if not lastTrade.ExtractAllData(actualTrade):# failed--> continue to next one
                            print("failed to decode input")
                            continue

                        if not database.GetLastTradeId(lastTrade.id):#check if the trade is already saved into the database
                            # id different  -->store it in the Database
                            print("inserting trade id= {} into the database".format(lastTrade.id))
                            now = datetime.now()
                            formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
                            database.InsertTradeIntoDatabase(lastTrade) 
                    

                            #send the Alert
                            now = datetime.now()
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

                            alert=""
                            if lastTrade.order:
                                alert+="THIS is an ORDER for the following position:\n"
                            if lastTrade.openClose=="Close":
                                alert+="{} -Position:  Market= {}, Type:Close, Direction ={},  Leverage ={} :gun: , Rate ={}, gain= {} \n".format(formatted_date,lastTrade.displayName,lastTrade.direction,lastTrade.leverage,lastTrade.rate,lastTrade.gainLoss)
                            elif lastTrade.openClose=="Open": # trade is of type OPEN
                                alert+="{} -Position:  Market= {}, Type:Open :green_circle: , Percentage= {}, Direction ={}, Leverage ={}, Rate ={}  \n".format(formatted_date,lastTrade.displayName,lastTrade.percentage,lastTrade.direction,lastTrade.leverage,lastTrade.rate)
                            else:#lastTrade.openClose  is empty
                                alert+="{} -Position:  Market= {}, Type:XXXXXX , Direction ={}, Leverage ={}, Rate ={}  \n".format(formatted_date,lastTrade.displayName,lastTrade.direction,lastTrade.leverage,lastTrade.rate)

                            #add common text
                            link="Trade: https://www.etoro.com/posts/"
                            link+=lastTrade.id
                            link+="\n"
                            alert+=link
                            marketlink="Market: https://www.etoro.com/markets/"
                            marketlink+=lastTrade.market
                            alert+=marketlink
                            alert+="\n"
                            if lastTrade.messageBody:
                                alert+="Message: "
                                alert+=lastTrade.messageBody
                                alert+="\n"
                            alert+="@everyone"
                            await channel.send(alert)
                            #print(alert)
            except Exception as ex:
                print("DetectLatestTrades(): Exception caught!={}".format(ex))
                waittime = 120 #seconds
                await asyncio.sleep(waittime)
                continue
    except:# specially made to catch the stop command
        print("DetectLatestTrades function killed ")
        return


        
#example of colors
@bot.command(name='rapidAlertsStatus')
async def listOfCommands(ctx):
    returnMessage= str("Thanks god im alive :blush:  :blush: ")
    await ctx.send(returnMessage)

                


bot.loop.create_task(DetectLatestTrades())
#run event loop for the bot
bot.run('Nzg5Nzc3Nzc2ODY5MTEzODg2.X92_3w.nhOMEJpowHhAS8Z2Be0PzqqHb08')

