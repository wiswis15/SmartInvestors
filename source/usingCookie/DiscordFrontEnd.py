import sys
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from threading import Thread, Lock,Event
from datetime import datetime
import asyncio
import socket
import collections  # for the buffer
from discord.utils import get
from discord.ext.tasks import loop
from discord.ext import commands
from discord import Embed
import time
import discord
import json
import  jsonrpcclient 
import queue
import discord
from discord.ext import tasks, commands
import asyncpg
import struct


import etoro as etorolib
from loglib import logger as log 
import trade 
from  discordAlerts import DiscordAlert as discordAlert




HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 1515        # The port used by the server


globalInterruptFlag=False

existingRequests=set()  # here we save all existing requests which is serverId+channelID
connectedToServer=False
mesageNotConnectedToServer="Sorry, our server is under maintenance for now! "

server_address = (HOST, PORT)
mysocket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
bufferSize=2024
MaxNumberOfTrials=20
def ConnectToServer():
    global MaxNumberOfTrials
    global bufferSize
    global mysocket
    global connectedToServer
    global globalInterruptFlag
    previousStatus=False
    NumberOfTrial=0
    while True :
        if globalInterruptFlag:
            return
        try:
            if previousStatus and not connectedToServer:
                log.info("Server is disconnected, A nex trial will be done")
                previousStatus=False
            if connectedToServer and not previousStatus:
                log.info("Discord Front is successfully connected the server")
                previousStatus=True
            while not connectedToServer:   
                    if globalInterruptFlag:
                        return 
                    mysocket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)        
                    NumberOfTrial+=1
                    mysocket.connect((HOST, PORT))  # we connect to the socket
                    connectedToServer=True
                    break;
        except Exception as e: # pylint: disable=broad-except
            log.critical("Trying to connect to the back end!, trial number : {}".format(NumberOfTrial))
        except KeyboardInterrupt:
            log.debug("keyoard Interrut")
            globalInterruptFlag=True
        finally:
            time.sleep(5)


#lets start our Server
ServerThread=Thread(target=ConnectToServer)
ServerThread.start()



def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def read_from_server(buffer, terminate_signal):
    global mysocket
    global connectedToServer
    global globalInterruptFlag
    while True :
        if globalInterruptFlag:
            return
        if not connectedToServer:
            time.sleep(3)
            continue
        try:
            raw_msglen = recvall(mysocket, 4)
            if not raw_msglen:
                return None
            msglen = struct.unpack('>I', raw_msglen)[0]
            # Read the message data
            decoded_input= recvall(mysocket, msglen)
            data =decoded_input.decode('utf-8')
            buffer.put(data)  # type: string contains a json
            log.debug("received message :{} from the server\n".format(data))


            

        except Exception as ex:
            connectedToServer=False
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            #log.error("Exception in read_from_server():{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            time.sleep(3)
        except KeyboardInterrupt:
            log.debug("keyoard Interrut")
            globalInterruptFlag=True
            




def sendToServer(buffer, terminate_signal):
    global connectedToServer
    global mysocket
    global globalInterruptFlag 
    while True :
        if globalInterruptFlag:
            return
        if not connectedToServer:
            time.sleep(3)
            continue
        try:
            message=buffer.get(block=True)     
            if message:
                mysocket.sendall(message.encode())
        except Exception as ex:
            connectedToServer=False
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            #log.error("Exception in sendToServer():{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            time.sleep(3)
        except KeyboardInterrupt:
            log.debug("keyoard Interrut")
            globalInterruptFlag=True






serverToDiscordMessages =  queue.Queue()  # buffer for reading/writing
DiscordToServerMessages = queue.Queue() # buffer for reading/writing



def AppendMessageToServer(message):
    DiscordToServerMessages.put(message)



terminate_signal = Event()  #
terminate_signal.set()
threads = [
  Thread(target=read_from_server, kwargs=dict(
    buffer=serverToDiscordMessages,
    terminate_signal=terminate_signal
  )),
  Thread(target= sendToServer, kwargs=dict(
    buffer=DiscordToServerMessages,
    terminate_signal=terminate_signal
  ))
]

def startThrerads():
    for t in threads:  # start both threads
        t.start()
    for t in threads:  # wait for both threads to finish
        t.join()


NotValidChannels=dict() # here we save the not valid channels example NotValidChannels[wislinaXXXXX]=3  3 number of failed attempts
NotValidChannelsMaxAttempts=7



def messageBlocked(guildId,channelId):
    global NotValidChannels
    global NotValidChannelsMaxAttempts
    key = guildId+channelId
    if key in NotValidChannels:
        NotValidChannels[key]+=1
        if NotValidChannels[key] > NotValidChannelsMaxAttempts:
            #the channel may have blocked us -->remove it
            req=jsonrpcclient.Request("RemoveSubscription",etoroProfile="notused",guild_id=guildId,channel_id=channelId,owner_id="owner_id")
            AppendMessageToServer(json.dumps(req))
            del NotValidChannels[key]  #remove it
            log.error("messageBlocked removed channel: {} on guildid {}".format(channelId,guildId))
    else:
        NotValidChannels[key]=1



def readjsonElemnt(element,jsonStructure):
    if element in jsonStructure:
        return jsonStructure[element]
    else:
        return ""
@tasks.loop(seconds=2.0)
async def sendMessagesToDiscord():
    """
    dispatch all queued messages to all channels
    """

    try:
        if serverToDiscordMessages.empty():
            return

        count=0
        while not serverToDiscordMessages.empty():
            if count > 10: #max number of messages to read in 1 cycle
                return
            message =serverToDiscordMessages.get()
            messageJson = json.loads(message) # message if of type string

            #allow user to send more request
            key=str(messageJson["guildId"])+str(messageJson["channel_id"])
            if key in existingRequests:
                existingRequests.remove(key) #request is answered

            profile=readjsonElemnt('profile',messageJson)
            guildId=readjsonElemnt('guildId',messageJson)
            channelId=readjsonElemnt('channel_id',messageJson)
            owner_id=readjsonElemnt('owner_id',messageJson)
            messageText=readjsonElemnt('result',messageJson) 

            targetGuild=bot.get_guild(int(guildId))
            if targetGuild==None:
                messageBlocked(guildId,channelId)
                continue
            channel=targetGuild.get_channel(int(channelId))
            if channel==None:
                messageBlocked(guildId,channelId)
                continue

            generalMessage=readjsonElemnt('generalMessage',messageJson) 
            if generalMessage:
                #this is a general message
                embed=discord.Embed(title='UPDATE')
                embed.add_field(value=generalMessage, inline=True)
                await channel.send(embed=embed)
                continue

            path="https://www.etoro.com/people/{}".format(profile)

            embed=discord.Embed(title="alert")

            image=readjsonElemnt('image',messageJson) 
            if image:
                embed.set_author(name=profile, url=path, icon_url=messageJson["image"])
            else:
                embed.set_author(name=profile, url=path)

            transactionType=readjsonElemnt('direction',messageJson) 
            if transactionType  and transactionType.lower()=='long':
                transactionType="BUY"
            else :
                transactionType="SELL"

            type=readjsonElemnt('type',messageJson) 
            if type and type=="commandReplay" and messageText:  #this is a response for a command
                embed=discord.Embed()
                embed.description=messageText
                await channel.send(embed=embed) 
                continue

                    
            if "type" in messageJson and messageJson["type"]=="SL/TP change notification":  #this is a response for a command
                embed=discord.Embed(title="SL/TP change Notification")
                embed.description =messageText
                if "image" in   messageJson and messageJson["image"]:
                    embed.set_author(name=profile, url=path, icon_url=messageJson["image"])
                else:
                    embed.set_author(name=profile, url=path)
                if 'instrument_image' in   messageJson and messageJson["instrument_image"]:
                    thumbnail=messageJson["instrument_image"]
                    embed.set_thumbnail(url=thumbnail)
                await channel.send(embed=embed)
                continue
                

            if messageJson["openclose"] =="open":
                embed.title = 'NEW {} TRADE @ {} '.format(transactionType,messageJson["market"].upper())
                if 'market' in messageJson:
                    embed.url = 'https://www.etoro.com/markets/{}'.format(messageJson["market"]) #This URL will be hooked up to the title of the embed 
                if 'instrument_image' in   messageJson and messageJson["instrument_image"]:
                    thumbnail=messageJson["instrument_image"]
                    embed.set_thumbnail(url=thumbnail)
                embed.add_field(name='Rate', value=messageJson["rate"], inline=True)
                embed.add_field(name='Direction', value=messageJson["direction"], inline=True)
                embed.add_field(name='Leverage', value=messageJson["leverage"], inline=True)
                if "percentage" in messageJson and messageJson['percentage']!='XX':
                    embed.add_field(name='Equity Percentage', value=messageJson["percentage"], inline=True)
            else:#close trade
                embed.title = '{} - CLOSED A TRADE @ {} '.format(messageJson["profile"],messageJson["market"].upper())
                if 'market' in messageJson:
                    embed.url = 'https://www.etoro.com/markets/{}'.format(messageJson["market"]) #This URL will be hooked up to the title of the embed 
                if 'instrument_image' in   messageJson and messageJson["instrument_image"]:
                    thumbnail=messageJson["instrument_image"]
                    embed.set_thumbnail(url=thumbnail)
                embed.add_field(name='Rate', value=messageJson["rate"], inline=True)
                embed.add_field(name='Direction', value=messageJson["direction"], inline=True)
                embed.add_field(name='Leverage', value=messageJson["leverage"], inline=True)
                embed.add_field(name='Profit', value=messageJson["NetProfit"], inline=True)

            if "analysis" in messageJson and messageJson["analysis"]:
            #embed.timestamp = datetime.now()
                embed.set_footer(text=messageJson["analysis"])

            try:
                #bot.loop.create_task(channel.send(embed=embed))
                await channel.send(embed=embed)
            except Exception as ex:
                if 'Missing Access' in ex.text:
                    messageBlocked(guildId,channelId)
                time.sleep(1)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("Exception in sendMessagestoAllclients:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))





#discord bot part
intents = discord.Intents(messages=True, guilds=True)
intents.members = True
bot = commands.Bot(command_prefix="+",intents=intents)




@bot.event
async def on_guild_join(guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            embed=discord.Embed()
            embed.add_field(name='Thank you for using The Smart Investors Club EPOPO Bot :blush: ',value=onGuildJoin, inline=True)
            await channel.send(embed=embed)
        break


@bot.event
async def on_ready() :
    log.info('SICEpopo Discord Interface is ready')
    sendMessagesToDiscord.add_exception_type(asyncpg.PostgresConnectionError)
    sendMessagesToDiscord.start()


@bot.event
async def on_guild_available(guild):
    log.info("on_guild_available !! SIC Discord Interface is Active on guild {}".format(guild.name))



AvailableFunctions=set()
AvailableFunctions.add("+status ")
AvailableFunctions.add("+add ")
AvailableFunctions.add("+remove ")
AvailableFunctions.add("+watchlist ")
AvailableFunctions.add("+selectedalerts ")
AvailableFunctions.add("+allalerts ")
AvailableFunctions.add("+commonStocks")

def GetHelpMessage():
    #message="Welcome To Smart Investors Club EPOPO Bot :blush: \n"
    message="**Available functions:** \n"
    message+="**+epopoHelp** : Get the status of SICEpopo Bot \n"
    message+="**+status** : Get the status of SICEpopo Bot \n"
    message+="**+add etoroProfile** : Add etoroProfile to your watchlist \n"
    message+="**+remove etoroProfile** : Remove etoroProfile from your watchlist \n"
    message+="**+watchlist** : Get the list of all followed etoroProfiles\n"
    message+="**+selectedalerts number** : ONLY positions shared with number other traders will be received  \n"
    message+="**+allalerts** : All positions will be received\n"
    message+="**+commonStocks** : Get stocks common in your watchlist, ordered from the most common to least common\n"
    return message


onGuildJoin=GetHelpMessage()

@bot.command(name='epopoHelp')
async def epopoHelp(ctx):
    embed=discord.Embed(title='HELP Menu')
    embed.description=GetHelpMessage()
    await ctx.send(embed=embed)  

            
        

@bot.command(name='status')
async def status(ctx):
    embed=discord.Embed(title='Status')
    embed.description="** OK **"""
    await ctx.send(embed=embed)   


@bot.command(name='add')
async def add(ctx,etoroProfile,psw=''):
    #Request("cat", name="Yoko")
    #{'jsonrpc': '2.0', 'method': 'cat', 'params': {'name': 'Yoko'}, 'id': 1}
    if not connectedToServer:
            embed=discord.Embed()
            embed.description=mesageNotConnectedToServer
            await ctx.send(embed=embed) 
    key=str(ctx.guild.id)+str(ctx.channel.id)
    """     if key in existingRequests:
        await ctx.send("Please wait, we are still working on your previous command!")
        return 
    else:"""
    embed=discord.Embed()
    embed.description=" Command received, one moment please"
    await ctx.send(embed=embed) 
    req=jsonrpcclient.Request("follow", etoroProfile=etoroProfile.lower(),guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id,password=psw)
    print(req)
    AppendMessageToServer(json.dumps(req))
    #{"jsonrpc": "2.0", "method": "follow", "params": {"etoroProfile": "rapidstock", "guild_id": 775627861180416000, "channel_id": 807541501877813248, "owner_id": 
    #771615049701523487}, "id": 1}
    existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))  #means need an answer before any further requests
        


@bot.command(name='remove')
async def remove(ctx,etoroProfile):
    if not connectedToServer:
        embed=discord.Embed()
        embed.description=mesageNotConnectedToServer
        await ctx.send(embed=embed) 
        return
    #Request("cat", name="Yoko")
    #{'jsonrpc': '2.0', 'method': 'cat', 'params': {'name': 'Yoko'}, 'id': 1}
    key=str(ctx.guild.id)+str(ctx.channel.id)
    """if key in existingRequests:
        await ctx.send("Please wait, we are still working on your previous command!")
        return
    else:"""
    embed=discord.Embed()
    embed.description=" Command received, one moment please"
    await ctx.send(embed=embed) 
    req=jsonrpcclient.Request("StopFolllowing", etoroProfile=etoroProfile.lower(),guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id)
    #print(req)
    AppendMessageToServer(json.dumps(req))
    #{"jsonrpc": "2.0", "method": "follow", "params": {"etoroProfile": "rapidstock", "guild_id": 775627861180416000, "channel_id": 807541501877813248, "owner_id": 
    #771615049701523487}, "id": 1}  
    existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))


@bot.command(name='watchlist')
async def watchlist(ctx):
    if not connectedToServer:
        embed=discord.Embed()
        embed.description=mesageNotConnectedToServer
        await ctx.send(embed=embed) 
    key=str(ctx.guild.id)+str(ctx.channel.id)
    """if key in existingRequests:
        await ctx.send("Please wait, we are still working on your previous command!")
        return
    else:"""
    embed=discord.Embed()
    embed.description=" Command received, one moment please"
    await ctx.send(embed=embed) 
    existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))
    req=jsonrpcclient.Request("MyTradersList",etoroProfile="notused",guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id)
    AppendMessageToServer(json.dumps(req))
    #{"jsonrpc": "2.0", "method": "follow", "params": {"etoroProfile": "rapidstock", "guild_id": 775627861180416000, "channel_id": 807541501877813248, "owner_id": 
    #771615049701523487}, "id": 1}
    
    
@bot.command(name='selectedalerts')
async def selectedalerts(ctx,tapedNumber):
    if not connectedToServer:
        await ctx.send(mesageNotConnectedToServer)
        return 
    try:
        valueint =int(tapedNumber)
    except Exception as ex:
        await ctx.send("sorry, filter value shall be a number between 1 and 6")
        return

    if ( (int(tapedNumber)>6) or (int(tapedNumber)<1)):
        await ctx.send("sorry, filter value shall be between 1 and 6")
        return

    key=str(ctx.guild.id)+str(ctx.channel.id)
    """if key in existingRequests:
        await ctx.send("Please wait, we are still working on your previous command!")
        return
    else:"""
    embed=discord.Embed()
    embed.description=" Command received, one moment please"
    await ctx.send(embed=embed) 
    existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))
    req=jsonrpcclient.Request("filter",etoroProfile="notused",guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id,number=int(tapedNumber))
    AppendMessageToServer(json.dumps(req))


@bot.command(name='allalerts')
async def allalerts(ctx):
    if not connectedToServer:
        embed=discord.Embed()
        embed.description=mesageNotConnectedToServer
        await ctx.send(embed=embed) 
    else:
        embed=discord.Embed()
        embed.description=" Command received, one moment please"
        await ctx.send(embed=embed) 
        existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))
        req=jsonrpcclient.Request("nofilter",etoroProfile="notused",guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id)
        AppendMessageToServer(json.dumps(req))


@bot.command(name='commonStocks')
async def commonStocks(ctx):
    if not connectedToServer:
        await ctx.send(mesageNotConnectedToServer)
        return
    else:
        embed=discord.Embed()
        embed.description=" Command received, one moment please"
        await ctx.send(embed=embed) 
        existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))
        req=jsonrpcclient.Request("commonStocks",etoroProfile="notused",guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id)
        AppendMessageToServer(json.dumps(req))


@bot.command(name='myEtoro')
async def myEtoro(ctx,profile):
    if not connectedToServer:
        await ctx.send(mesageNotConnectedToServer)
        return
    #alertsdb(alertsdb.FollowProfile(profile,channelid,owner_id)
    #Request("cat", name="Yoko")
    #{'jsonrpc': '2.0', 'method': 'cat', 'params': {'name': 'Yoko'}, 'id': 1}
    key=str(ctx.guild.id)+str(ctx.channel.id)
    """if key in existingRequests:
        await ctx.send("Please wait, we are still working on your previous command!")
        return
    else:"""
    await ctx.send("Command Received! One moment please :blush:  ")
    req=jsonrpcclient.Request("SetEtoroProfile",etoroProfile=profile,guild_id=ctx.guild.id,channel_id=ctx.channel.id,owner_id=ctx.guild.owner_id)
    AppendMessageToServer(json.dumps(req))
    existingRequests.add(str(ctx.guild.id)+str(ctx.channel.id))



socketthread=Thread(target=startThrerads,)
socketthread.start()

""" 

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    for function in AvailableFunctions:
        if function in message.content:
            await bot.process_commands(message)
            return  # the message is a command
    await message.channel.send(GetHelpMessage())  """
    

#run event loop for the bot
bot.run('ODA3NTQ0Mzg5OTMyMDIzODA4.YB5iUg.8dfPfP6tiaKEwzAN3Of4XL0zUH4')
#test
#bot.run('NzkzNTE4NjEyMzAzNzA4MTYw.X-tbzA.Sgmzw2TPeWWksz5pc08RpH48Hls')
#only for rapid
#bot.run('ODIwMzAzNTg4ODAxOTA0NzAy.YEzNQA.IF9bTJHjb6AAbU-xQjO4zYR3ewI')