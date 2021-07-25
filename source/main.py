import discord
from discord.ext import commands
import checkProfiles
import member
import database
import threading
from datetime import datetime





# set it to true just for testing
test=False


AllMembers=set()
numberIgnoredMembers=0  # could not add them to AllMembers

CommandsList=set() # container for all possible commandsList

CommandsList.add("CheckMembers")  # this command will run the check user's ETORO profiles



intents = discord.Intents(messages=True, guilds=True)
intents.members = True

#client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix="!",intents=intents)



@bot.event
async def on_ready() :
    print('Bot is ready')

""" @client.event
async def on_message(message):
    print(message.type)
    print(message.content)
    print('Message from {0.author}: {0.content}'.format(message))
    await message.channel.send('Thank you for your message, we will get back to you soon!') """


@bot.event
async def on_guild_available(guild):
    print("Hello !! RapidSpy is Active on guild {}".format(guild.name))
    # TestTranslateServer  RapidStock
    if guild.name!= "RapidStock":
        return
    intents.members = True
    x = await guild.chunk()
    print("Discord {}  has : {} members".format(guild.name,len(x)))
    localNickName=""
    localDisplayName=""
    AllMembers.clear()  # clear the memory
    

    for memberFromDiscord in x :
        Newmember =member.Member(0)
        if memberFromDiscord.id==0:
            print("!warning, received a member with 0 Id\n")
            continue
        else:
            Newmember.id=memberFromDiscord.id

        if not isinstance(memberFromDiscord.nick,str) :#has type NONE--> not filled
            if not memberFromDiscord.display_name:# try the display_name instead of the nickname
                print("!Warning, User id: {} has  NO nickName and NO display_name".format(memberFromDiscord.id)) 
                numberIgnoredMembers+=1
                continue
            else:  # memberFromDiscord.id is valid
                localDisplayName=memberFromDiscord.display_name
                if not localDisplayName:
                    print("Warning!! Also empty display name \n")
                    continue
        else:# memberFromDiscord.nick is a valid non empty string
            localNickName=memberFromDiscord.nick
            if memberFromDiscord.display_name:
                localDisplayName=memberFromDiscord.display_name


        #extract etoro name
        localnameToUse=""
        if localNickName: #nickName is not empty
            localnameToUse=localNickName
        else :#use display name
            localnameToUse=localDisplayName
        position=localnameToUse.find("(")   #wissem(wislina)
        if (position>0):
            Newmember.etoroProfile=localnameToUse[position+1:-1] #extract the name inside parenthesis wissem(wislina)
        else:  # no ()  inside the name
            Newmember.etoroProfile=localnameToUse

        #print("Adding member with nickname= {} and displayName= {} ".format(localNickName,localDisplayName))
        Newmember.nickName = localNickName 
        Newmember.display_name=localDisplayName

        #now adding ETORO profile    
        AllMembers.add(Newmember)  # add the member object

        database.InsertNewMember(Newmember)#added new members to the database
    
    print("Total number of members= {} ".format(len(AllMembers)))
    database.UpdateNumberOfMembers(len(AllMembers))#add the members number into the database


@bot.command(name='CheckMembers')
async def CheckMembers(ctx):
    import member
    await ctx.send('Will check {} Members!, This may take some Time!.'.format(len(AllMembers)))
    returnMessage=""
    failed=False  # flag for an exception
    totalNumberOfCopiers=0
    totalPrivateProfiles=0


    if test:# can be used on test, shorter list
        AllMembers.clear()
        test1 =member.Member('wislina') 
        AllMembers.add(test1)  # add the member object
        test2 =member.Member('fcastel') 
        AllMembers.add(test2)  # add the member object
        test3 =member.Member('BurcinBu') 
        AllMembers.add(test3)  # add the member object

    try:
        for trader in AllMembers :
            # example of Urls
            #https://www.etoro.com/people/wislina'
            #if name is of syntax wissem(wislina)
            if not trader.etoroProfile.strip():# if empty string-->continue
                print("Watchout! member {} etoroProfile field is empty".format(trader.nickName))
                continue
            memberpath='https://www.etoro.com/people/'+trader.etoroProfile
            try:
                result,error= checkProfiles.IsPrivateProfile(memberpath)  # check all profiles
                if (error==checkProfiles.NotFound) :# errow while checking the profile--> most likely profile DOES not exist
                    trader.notFound = True
                elif  result==True:#  private Profile
                    trader.private= True
                    totalPrivateProfiles+=1
                    database.RecordPrivateProfile(str(trader.id))#add it to the database with date
                else:
                    trader.numberOfCopiers=checkProfiles.GetNumberOfCopiers(trader.etoroProfile)
                    database.UpdateMember(trader) #update the databse record 
                    totalNumberOfCopiers+=trader.numberOfCopiers
            except Exception as ex:
                print("exception : {} while checking the name {}".format(ex,memberpath))
                continue
        
        firstTime=True
        for trader in AllMembers:
            if trader.private:
                if firstTime:
                    returnMessage= " yahoooo :grin: :grin: "
                    returnMessage+= " @Ali(AliGhan) you have new customers  :partying_face: :partying_face: \n" 
                    firstTime=False
                returnMessage+="```css\n[Alert! Member with displayName={} and etrr ={} has a private Profile {}".format(trader.display_name,trader.etoroProfile,"]```")
            elif isinstance(trader.numberOfCopiers, int) and (trader.numberOfCopiers > member.Conditions.MaxNumberOfCpiers) :
                returnMessage+="```css\n[Alert! Member {} exceeded number of Copiers with {} Copiers {}".format(trader.nickName,trader.numberOfCopiers," ]```")


    except Exception as ex:
        failed=True
        print("Exception caught!={}".format(ex))

    #Send the result
    #print("output={}".format(returnMessage))
    #print("number of All members= {}".format(len(AllMembers)))
    #print("number of private profiles= {}".format(totalPrivateProfiles))
    #print("number of ignored  profiles= {}".format(numberIgnoredMembers))
    totalNumberOfMembersAndCopiers=totalNumberOfCopiers+len(AllMembers)
    #print("number of members+copiers = {}".format(totalNumberOfMembersAndCopiers))
 
    if failed:
        text= str("""```css\n[Bot got an Error!! wislina is on it]```""")
        embed = discord.Embed(title="Results")
        embed.add_field(name="Bot Error!",value=text)
        await ctx.send(embed=embed)


    elif not returnMessage and not failed:# results are ALL good
            returnMessage=str("Damn it :weary: :weary: !  No one will go to Jail Today haha")
            analysisMessage=database.GetDataAnalysis(AllMembers)
            returnMessage+=analysisMessage
            await ctx.send(returnMessage)
    else:
        analysisMessage=database.GetDataAnalysis(AllMembers)
        returnMessage+=analysisMessage
        await ctx.send(returnMessage)#send result message


    
            

#example of colors
@bot.command(name='listOfCommands')
async def listOfCommands(ctx):
    checkcommand= str("""```css\n!CheckMembers```""")
    embed = discord.Embed(title="List of Commands:")
    embed.add_field(name="1- To check all member's ETRRR profiles :",value=checkcommand)
    await ctx.send(embed=embed)


@bot.command(name='TestMessageLayout')
async def CheckMembers(ctx):
    alert="Market= natgas, Direction =long,  Leverage =10 :gun: , Rate =150, gain= 10.2 "
    alert+="https://www.etoro.com/posts/0__entry__7fd51907-3582-498e-85f8-b66b837bea9d\n"
    alert+="https://www.etoro.com/markets/00981.hk\n"
    await ctx.send(alert)



@bot.command(name='rapidspyStatus')
async def listOfCommands(ctx):
    returnMessage= str("Thanks god im alive :blush:  :blush: ")
    await ctx.send(returnMessage)
    
                    

#run event loop for the bot
bot.run('Nzc4OTIyMTIyODc3MjA2NTc5.X7ZBwQ.aqtYoL9F5iMV82TRVJJ3fqaVJEc')
