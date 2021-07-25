import mysql.connector
from datetime import datetime
import sys
import os

import trade
import alertsClient as client
from loglib import logger as log 
from threading import RLock



    
errorMessageToDiscordUsers="Server Error! We will fix it very soon! :face_with_monocle:  :face_with_monocle: "



class AlertDatabase():

    #static variables
    instrumentIdNameMap={} #dictiory containing the mapping between the name and the instrucmnet id
    instrumentIdNameMapLock = RLock()
    instrumentNameImageMap={} #dictiory containing the mapping between the instrument name and its icon image
    instrumentNameImageMapLock = RLock()

    def __init__(self,name):
        self.name=name
        self.connected=False
        #connect to local database
        self.alertConnection = mysql.connector.connect( host="localhost",  user="root",  password="root",  database="alerts",autocommit=True)
        if not self.alertConnection:
            log.critical("alerts_database failed to connect")
            connected=False
        else:
            log.info("AlertDatabase with name= {} is connected!".format(name))
            connected=True
        


    def AddDiscordUser(self,Owner_id):# 
        """
        This function will add a Discord User(owner) to the database. 
        if it exists already, it will return its ID
        return a tuple(status,owner_id)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM diccord_users WHERE DiscordId = '%s'"%((Owner_id)) )
            mycursor.fetchall()
            # gets the number of rows affected by the command executed
            row_count = mycursor.rowcount
            if row_count == 0:
                now = datetime.now()
                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
                sql = "INSERT INTO diccord_users (DiscordId,date) VALUES (%s, %s)"
                val = (Owner_id,formatted_date)
                mycursor.execute(sql, val)
                self.alertConnection.commit()
                log.info("New Discord user  with id ={} added into diccord_users".format(Owner_id))
                return (True,Owner_id)
            else:#already existing
                return (True,Owner_id)
        except Exception as ex:
            log.error("Exception {} in AddDiscordUser() while adding new discord user AddDiscordUser={}".format(ex.message,Owner_id))
            return (False,0)
        finally:
            mycursor.close()




    def AddDiscordGuild(self,guild_id,guild_name,owner_id):# add new discord
        """
        This function will add a Discord Guild(what we call a Server) to the database. 
        if it exists already, it will return its ID
        return the (status,id)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM discordservers WHERE guildId = %s",(guild_id,))
            mycursor.fetchall()
            # gets the number of rows affected by the command executed
            row_count = mycursor.rowcount
            if row_count == 0:
                now = datetime.now()
                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
                sql = "INSERT INTO discordservers (guildId,guildName,guildOwnerId,date) VALUES (%s, %s,%s,%s)"
                val = (guild_id,guild_name,owner_id,formatted_date)
                mycursor.execute(sql, val)
                self.alertConnection.commit()
                log.info("New DiscordGuildAdded into discordservers with id ={} ".format(guild_id))
                return (True,guild_id)
            else:#guild already exists
                return (True,guild_id)

        except Exception as ex:
            log.error("Exception {} in AddDiscordUser() while adding new discord user id={}".format(ex,owner_id))
            return (False,0)


    def DoesEtoroProfileExists(self,EtoroProfile):# add new discord
        try:
            mycursor = self.alertConnection.cursor()
            sql = "SELECT * FROM etoroprofiles WHERE profile = %s"
            val = (EtoroProfile, )
            mycursor.execute(sql, val)
            records=mycursor.fetchall()
            if (len(records)>0): #trade already exists
                return True
            else:
                return False
        except Exception as ex:
            log.error("Exception DoesEtoroProfileExists() while adding new discord user name ={} {}".format(EtoroProfile,ex))
            return False
        finally:
            mycursor.close()

    def RemoveEtoroProfile(self,EtoroProfile):# add new discord
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("DELETE FROM etoroprofiles WHERE profile = %s  ",(EtoroProfile,))
            self.alertConnection.commit()
            log.debug("RemoveEtoroProfile removed {} ".format(EtoroProfile))
 
        except Exception as ex:
            log.error("Exception RemoveEtoroProfile() while removing{} {}".format(EtoroProfile))
        finally:
            mycursor.close()


    def AddEtoroProfile(self,EtoroProfile,cid,profilePhtoPath=""):# add new discord
        """
        This function will add an etoroProfile 
        if it exists already, it will return its ID
        return the (status,id)
        """
        try:
            mycursor = self.alertConnection.cursor()
            records=mycursor.execute("SELECT * FROM etoroprofiles WHERE profile = %s",(EtoroProfile,))
            mycursor.fetchall()
            # gets the number of rows affected by the command executed
            row_count = mycursor.rowcount
            if row_count == 0:
                now = datetime.now()
                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
                sql = "INSERT INTO etoroprofiles (profile,cid,date,image) VALUES (%s,%s, %s,%s)"
                val = (EtoroProfile,cid,formatted_date,profilePhtoPath)
                records=mycursor.execute(sql, val)
                self.alertConnection.commit()
                log.info("New etoro profile added ={} ".format(records[0][1]))
                return (True,"Congrats!! You are now following {}".format(EtoroProfile))
            else:#etoro already exists
                return (False,"You are already following {}".format(EtoroProfile))

        except Exception as ex:
            log.error("Exception {} in AddEtoroProfile() while adding new etoroPrfile{}".format(ex,EtoroProfile))
            return (False,0)
        finally:
            mycursor.close()

    def FollowProfile(self,etoroProfile,guild_id,channel_id,owner_id):# add new follow rule
        """
        This function will add a follow rule
        if it exists already, it will return its ID
        return the (status,id)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM map_etoroprofiles_channels WHERE etoroProfile = %s AND guildId= %s AND channelId= %s AND \
            channel_owner = %s", (etoroProfile,str(guild_id),str(channel_id),str(owner_id)))
            records=mycursor.fetchall()
            # gets the number of rows affected by the command executed
            row_count = mycursor.rowcount
            if row_count == 0:
                now = datetime.now()
                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
                sql = "INSERT INTO map_etoroprofiles_channels (etoroProfile,guildId,channelId,channel_owner,date,filterMode,filterValue) \
                    VALUES (%s,%s, %s,%s,%s,%s,%s)"
                val = (etoroProfile,guild_id,channel_id,owner_id,formatted_date,0,0)
                mycursor.execute(sql, val)
                self.alertConnection.commit()
                log.info("New followRule has been added into discordservers with id ={} ".format(id))
                return (True,"Congrats! you started following {} :muscle: ".format(etoroProfile))
            else:#rule exiss --> return its id
                return (True,"You are already following {}!".format(etoroProfile))

        except Exception as ex:
            log.error("Exception {} in FollowProfile() while adding new rule etoro  profile= {} and guild_id={}".format(ex,owner_id,etoroProfile,guild_id))
            return (False,errorMessageToDiscordUsers )
        finally:
            mycursor.close()

    def StopFollowingProfile(self,etoroProfile,guild_id,channel_id,owner_id):# add new follow rule
        """
        This function will remove a follow rule
        return the (status,message)
        """
        try:
            if not etoroProfile in self.GetMyListFollowedProfiles(str(guild_id),str(channel_id),str(owner_id))[1]:
                return (True,"You were already not following {}!".format(etoroProfile))
            mycursor = self.alertConnection.cursor()
            mycursor.execute("DELETE FROM map_etoroprofiles_channels WHERE etoroProfile = %s AND guildId = %s AND channelId= %s AND channel_owner = %s",(etoroProfile,guild_id,channel_id,owner_id))
            self.alertConnection.commit()
            return (True,"You stopped following {} :rolling_eyes: ".format(etoroProfile))

        except Exception as ex:
            log.error("Exception {} in StopFollowingProfile() while deleting rule etoro  profile= {} and guildId={}".format(ex,owner_id,etoroProfile,guild_id))
            return (False,errorMessageToDiscordUsers)


    def RemoveSubscription(self,etoroProfile,guild_id,channel_id,owner_id):# add new follow rule
            """
            This function will remove a follow channel, as it may have blocked the access of the bot t the channel
            """
            try:
                mycursor = self.alertConnection.cursor()
                mycursor.execute("DELETE FROM map_etoroprofiles_channels WHERE guildId = %s AND channelId = %s ",(guild_id,channel_id))
                self.alertConnection.commit()
                log.debug("RemoveSubscription removed {} channels".format(mycursor.rowcount))
                return (True,"")

            except Exception as ex:
                log.error("Exception {} in RemoveSubscription() while deleting rule owner_id= {} and guildId={}".format(ex,owner_id,guild_id))
                return (False,"")

    def GetMyListFollowedProfiles(self,guild_id,channel_id,owner_id):# add new follow rule
        """
        This function will  return a list of the followed profiles
        return the (status,list)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM map_etoroprofiles_channels WHERE guildId=%s AND channelId = %s AND channel_owner = %s",(str(guild_id),str(channel_id),str(owner_id)))
            rules=mycursor.fetchall()
            # gets the number of rows affected by the command executed
            followedProfiles=[]
            for rule in rules:
                followedProfiles.append(rule[1])
            return (True,followedProfiles)

        except Exception as ex:
            log.error("Exception {} in GetMyListFollowedProfiles() for channelId={} AND ownerId={}".format(ex,channel_id,owner_id))
            return (False,"Sorry!, An Error occurred!")

        finally:
            mycursor.close()

    def GetAllFollowedProfiles(self):
        """
        This function will  return a list of the all the followed profiles
        return the (status,list) list is composed of (id,profile,cid,date)
        """
        # id, profile, cid, date, sltpchangenotifications, slalerts, slalertlevel, image
        #'1', 'rapidstock', '13735765', '2021-02-17', NULL, NULL, NULL, 'https://etoro-cdn.etorostatic.com/avatars/150X150/13735765/6.jpg'

        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM etoroprofiles")
            rules=mycursor.fetchall()
            # gets the number of rows affected by the command executed
            return (True,rules)  

        except Exception as ex:
            log.error("Exception {} in GetListOfFGetAllFollowedProfiles ".format(ex))
            return (False,[])

    def GetDiscordListOfSubscribers(self,etoroProfileInput) :
        """
        This function will add return a list of the discord channel following etoroProfile
        return the records (status,list)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM map_etoroprofiles_channels WHERE etoroProfile = %s",(etoroProfileInput,))
            subscribers=mycursor.fetchall()
            return (True,subscribers)
        except Exception as ex:
            log.error("Exception {} in GetDiscordListOfSubscribers() for etoroProfile={} ".format(ex,etoroProfileInput))
            return (False,[])

    def GetAllDiscordClients(self) :
        """
        This function will add return a list of all the clients using discord
        return the records (status,list)
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM map_etoroprofiles_channels")
            subscribers=mycursor.fetchall()
            return (True,subscribers)
        except Exception as ex:
            log.error("Exception {} in GetAllDiscordClients()  ".format(ex))
            return (False,[])


    def DoesTradeExists(self,id):
        """
        will return the  trade with tradeId=id
        will return false if trade does not exist, otherwise true
        """
        result=""
        mycursor = self.alertConnection.cursor()
        query = "SELECT * FROM tradeshistory WHERE tradeId = %s " 
        args=(id,)
        mycursor.execute(query,args)
        records= mycursor.fetchall()
        if (len(records)>0): #trade already exists
            #print("last trade has  id ={} and market ={} ".format(previousId,records[0][2]))    
            #trade foud --> true
            return (True,records[0])
        else:
            return (False,[])

    def InsertTradeIntoDatabase(self,etoroProfileName,newTrade):
        """
        insert trade id into database
        """
        try:
            formatted_date=""
            if newTrade.OpenDateTime:
                openTime=newTrade.OpenDateTime#2021-02-13T21:02:48.3800000Z
                time=openTime[0:19]
                formatted_date=time.replace('T',' ')  #2021-02-13 21:02:48
            else:
                now = datetime.now()
                formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

            mycursor = self.alertConnection.cursor()
            sql = "INSERT INTO tradeshistory (etoroProfile,tradeId,market,direction,leverage,rate,openClose,date,gainLoss,stopLoss,takeprofit,NetProfit) VALUES (%s,%s,%s, %s,%s,%s,%s,%s,%s,%s,%s,%s)"
            val = (etoroProfileName,newTrade.positionID, newTrade.market, newTrade.direction, newTrade.leverage, newTrade.rate,\
                newTrade.openClose,formatted_date,newTrade.NetProfit,newTrade.stoploss,newTrade.takeprofit,newTrade.NetProfit)
            mycursor.execute(sql, val)
            self.alertConnection.commit()
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in currentPositionsUpdate :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))

    def ReplaceTradeIntoDatabase(self,etoroProfileName,newTrade):
        """
        update  trade  into database
        """
        mycursor = self.alertConnection.cursor()
        sql = "DELETE FROM tradeshistory WHERE tradeId = %s " 
        args=(newTrade.positionID,)
        mycursor.execute(sql, args)
        self.alertConnection.commit()
        self.InsertTradeIntoDatabase(etoroProfileName,newTrade)

    def RemoveTradeFromDatabase(self,trade):
        """
       Remove a trade from the database
        """
        mycursor = self.alertConnection.cursor()
        sql = "DELETE FROM tradeshistory WHERE tradeId = %s " 
        args=(trade.positionID,)
        mycursor.execute(sql, args)
        self.alertConnection.commit()


    def UpdateEtoroNameChannelUser(self,etoroProfileName,guild_id,channel_id,owner_id):
        """
        update  etoro
        """
        try:
            mycursor = self.alertConnection.cursor()

            sql = "UPDATE map_etoroprofiles_channels SET myEtoroProfile = %s  WHERE guildId=%s AND channelId = %s AND channel_owner = %s"
            args=(etoroProfileName,str(guild_id),str(channel_id),str(owner_id),)
            mycursor.execute(sql,args)

            self.alertConnection.commit()
            return (True,"etoroProfile is set to {}".format(etoroProfileName))
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in UpdateEtoroNameChannelUser :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            return (False,"Something Went wrong!")

    @staticmethod
    def FillnameInstrumentIdMap():
        """
        Fill the map instrumentId-->name
        """
        with  mysql.connector.connect( host="localhost",  user="root",  password="root",  database="alerts") as localConnection:
            mycursor = localConnection.cursor()
            query = "SELECT * FROM instrumentidnamemap " 
            mycursor.execute(query)
            records= mycursor.fetchall()
            with AlertDatabase.instrumentIdNameMapLock:
                for record in records:
                    AlertDatabase.instrumentIdNameMap[record[0]]=record[1] # record[0]:id, record[1]=name
                    AlertDatabase.instrumentNameImageMap[record[1]]=record[2]  #image
            log.info("instrumentIdNameMap size= {}".format(len(AlertDatabase.instrumentIdNameMap)))

    @staticmethod
    def GetInstrumentName(id):
        """
        return the name of the instrucmentId id
        """
        try:
            if not AlertDatabase.instrumentIdNameMap:
                AlertDatabase.FillnameInstrumentIdMap()
            with AlertDatabase.instrumentIdNameMapLock:
                return AlertDatabase.instrumentIdNameMap[id]
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetInstrumentName :id= {} {} {} {} {}".format(id,exc_type, fname, exc_tb.tb_lineno,ex))
            return ""

    @staticmethod
    def GetInstrumentIconImage(name):
        """
        return the image path  of the instrucment name
        """
        try:
            if not AlertDatabase.instrumentNameImageMap:
                AlertDatabase.FillnameInstrumentIdMap()
            with AlertDatabase.instrumentNameImageMapLock:
                return AlertDatabase.instrumentNameImageMap[name]
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetInstrumentIconImage :name= {} {} {} {} {}".format(name,exc_type, fname, exc_tb.tb_lineno,ex))
            return ""


    def Average(self,lst): 
        return sum(lst) / len(lst) 

    def GetTradersWhoHaveSuchPosition(self,market,direction):
        """
        get a list of traders who have the same position
        """
        try:
            mycursor = self.alertConnection.cursor()
            #id, etoroProfile, tradeId, market, direction, leverage, rate, openClose, date, gainLoss, stopLoss, takeprofit, NetProfit
            mycursor.execute("SELECT * FROM tradeshistory WHERE market = %s and direction=%s and openClose=%s",(market,direction,"open"))
            trades=mycursor.fetchall()
            tradeRateDict={} #dictionary
      
            for trade in trades:
                if not trade[1] in tradeRateDict:
                    tradeRateDict[trade[1]]=[] #empty list  
                    tradeRateDict[trade[1]].append(trade[6])# add price of each trade
                else:
                    tradeRateDict[trade[1]].append(trade[6])# add price of each trade
            
            AverageRate={} 
            for trader in tradeRateDict:
                allrates=tradeRateDict[trader]
                average=self.Average(allrates)
                limitedDecimal="{:.2f}".format(average)
                AverageRate[trader]=limitedDecimal

            return (True,AverageRate)# return dictionary with average
        except Exception as ex:
            log.error("Exception {} in GetTradersWhoHaveSuchPosition()  ".format(ex))
            return (False,[])

    def SetFilter(self,guild_id,channel_id,owner_id,value):
        """
        set Filter values 
        """
        try:
            mycursor = self.alertConnection.cursor()
            #id, etoroProfile, guildId, channelId, channel_owner, date, filterMode, filterValue
            filterValue=value
            filterMode=0
            if filterValue>0:
                filterMode=1

            sql = "UPDATE map_etoroprofiles_channels SET filterMode =%s, filterValue =%s  WHERE guildId=%s AND channelId = %s AND channel_owner = %s"
            args=(filterMode,filterValue,str(guild_id),str(channel_id),str(owner_id),)
            mycursor.execute(sql,args)

            self.alertConnection.commit()
            return (True,"SelectedAlerts is set to {}".format(value))
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in SetFilter :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            return (False,"Something Went wrong!")

    def GetOpenPositions(self,etoroProfileName) :
        """Return list of open positions"""
        try:
            mycursor = self.alertConnection.cursor()
            #id, etoroProfile, tradeId, market, direction, leverage, rate, openClose, date, gainLoss, stopLoss, takeprofit, NetProfit
            mycursor.execute("SELECT * FROM tradeshistory WHERE etoroProfile = %s  and openClose=%s and direction=%s",(etoroProfileName,"open","long"))
            trades=mycursor.fetchall()
            #listOfStocks=set()
            #id, etoroProfile, tradeId, market, direction, leverage, rate, openClose, date, gainLoss, stopLoss, takeprofit, NetProfit
            #for trade in trades:
            #    listOfStocks.add(trade[3].upper())
            return (True,trades)
        except Exception as ex:
            log.error("Exception {} in GetOpenPosition()  ".format(ex))
            return (False,[])
        

    def GetSLTPSubscriptioons(self) :
        """Return disctionary of discord subscriiptions to SL/TP
        Example slAlertsSubscribers['wislina']=[(guildId,chanelID),....]
        """
        try:
            mycursor = self.alertConnection.cursor()
            mycursor.execute("SELECT * FROM discordsltpsubscribers")
            records= mycursor.fetchall()
            slAlertsSubscribers=dict()
            #id, channelId, guildId, etoroprofile
            for subscription in records:
                key=(subscription[2],subscription[1])  # key is a tuple(channelId,guildId)
                if key in slAlertsSubscribers:
                    slAlertsSubscribers[key].append(subscription[3])
                else:
                    slAlertsSubscribers[key]=[]
                    slAlertsSubscribers[key].append(subscription[3])
            return slAlertsSubscribers
        except Exception as ex: 
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetSLTPSubscriptioons :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            return dict()

    def GetSLAlertsSbscribers(self) :
        """Return list of discordChannels subscribed to SL alerts
        Example DiscordSubsciptions['810503408544251905']=['wislina','rapidstock']
        """
        try:
            mycursor = self.alertConnection.cursor()
            #id, etoroProfile, guildId, channelId, channel_owner, date, filterMode, filterValue, myEtoroProfile, mySLAlert
            mycursor.execute("SELECT * FROM map_etoroprofiles_channels where mySLAlert=%s",(1,))
            records= mycursor.fetchall()
            DiscordSLSubsribers=dict()
            for record in records:
                key=(record[8])  # key is a tuple(channelId,guildId)
                value=(record[2],record[3])
                if key in DiscordSLSubsribers:
                    DiscordSLSubsribers[key].append(value)
                else:
                    DiscordSLSubsribers[key]=[]
                    DiscordSLSubsribers[key].append(value)
            return DiscordSLSubsribers
                
        except Exception as ex: 
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetSLAlertsSbscribers :{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
            return []
        

    





