import mysql.connector
from datetime import datetime
import trade
from loglib import logger as log



#connect to local database
mydb = mysql.connector.connect( host="localhost",  user="root",  password="root",  database="rapidstock")

if not mydb:
    log.info("Warning, no connection to database rapidstock")
else:
    log.info("successfully connected to local database rapidstock")



def InsertNewMember(member):
    """
    This function will check if the member exists in the database, if yes, update it.
    If not, create it.
    return true if a member has been created/updated
    else return false
    """
    mycursor = mydb.cursor()
    mycursor.execute(
        "SELECT id FROM member WHERE id = '%s'"%((member.id))
    )
    mycursor.fetchall()
    # gets the number of rows affected by the command executed
    row_count = mycursor.rowcount
    if row_count == 0:
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
        mycursor = mydb.cursor()
        sql = "INSERT INTO member (id, nickName,displayName,numberOfCopiers,etoroProfile,memberSince) VALUES (%s, %s,%s,%s,%s,%s)"
        val = (str(member.id), member.nickName, member.display_name,member.numberOfCopiers,member.etoroProfile,formatted_date)
        mycursor.execute(sql, val)

        mydb.commit()
        log.info(mycursor.rowcount, "member with etoro name {} added into the database".format(member.etoroProfile))
        return True
    else:
        return False

def UpdateMember(member):
    mycursor = mydb.cursor()

    sql = "UPDATE member SET numberOfCopiers = %s WHERE id = %s"

    mycursor.execute(sql,(member.numberOfCopiers,str(member.id)))

    mydb.commit()

    log.info("{} Database update, member {} has {} copiers".format(mycursor.rowcount,member.etoroProfile,member.numberOfCopiers))



def UpdateNumberOfMembers(number):
    now = datetime.now()
    formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
    mycursor = mydb.cursor()
    query = "SELECT * FROM number_members WHERE id = ( SELECT MAX(id) FROM number_members ) " 
    mycursor.execute(query)
    records= mycursor.fetchall()
    previousCount=records[0][0]
    if previousCount==number:#same members's number-->no need to add a record
        return
    query = "INSERT INTO number_members(number,date) " \
            "VALUES(%s,%s)"
    args = (number, formatted_date)

    mycursor.execute(query, args)

    mydb.commit()

    log.info("{} inserted into the table number_members:{} ".format(mycursor.rowcount,number))


def RecordPrivateProfile(memberId):
    now = datetime.now()
    formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
    mycursor = mydb.cursor()
    query = "INSERT INTO privateprofile(id,date) " \
            "VALUES(%s,%s)"
    args = (memberId, formatted_date)

    mycursor.execute(query, args)

    mydb.commit()

    log.info("{} inserted into the table privateprofile:{} ".format(mycursor.rowcount,memberId))

def GetDataAnalysis(memberList):
    result=""
    mycursor = mydb.cursor()
    query = "SELECT number,date FROM number_members WHERE id = (( SELECT MAX(id) FROM number_members ) -1)" 
    mycursor.execute(query)
    records= mycursor.fetchall()
    previousCount=records[0][0]
    if previousCount==len(memberList):
        result+=" No new members in our Discord!\n"
    elif previousCount<len(memberList): # number of members increased
        result+=" ```css\nNice! we have {} new members since {} !\n```".format(len(memberList)-previousCount,records[0][1])
    else:
        result+=" ```css [We have {} less members since {} !]\n```".format(previousCount-len(memberList),records[0][1])
    #return last result
    log.info("GetDataAnalysis=  {}".format(result))    
    return result

def GetLastTradeId(id):
    """
    will return the last trade id
    """
    result=""
    mycursor = mydb.cursor()
    query = "SELECT * FROM tradeshistory WHERE tradeId = %s " 
    args=(id,)
    mycursor.execute(query,args)
    records= mycursor.fetchall()
    if (len(records)>0): #trade already exists
        #print("last trade has  id ={} and market ={} ".format(previousId,records[0][2]))    
        #trade foud --> true
        return True
    else:
        log.info("GetLastTradeId(): New Trade detected with id = {} ".format(id))
        return False

def InsertTradeIntoDatabase(newTrade):
    """
    insert trade id into database
    """
    mycursor = mydb.cursor()
    query = "SELECT * FROM tradeshistory WHERE tradeId = %s " 
    args=(newTrade.id,)
    mycursor.execute(query,args)
    records= mycursor.fetchall()
    row_count = mycursor.rowcount
    if row_count == 0:  #new trade-->insert it into the database
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
        mycursor = mydb.cursor()
        sql = "INSERT INTO tradeshistory (tradeId,market,direction,leverage,rate,openClose,date,gainLoss) VALUES (%s, %s,%s,%s,%s,%s,%s,%s)"
        val = (newTrade.id, newTrade.market, newTrade.direction, newTrade.leverage, newTrade.rate, newTrade.openClose,formatted_date,newTrade.gainLoss)
        mycursor.execute(sql, val)

        mydb.commit()
        log.info(mycursor.rowcount, "trade with Id: {} and market : {} added into the database".format(newTrade.id,newTrade.market))

    else:# trade already exists
        log.info("trade with id ={} exists already".format(newTrade.id))

def AddGetInstrumentId(instrumentName,instrumentId):
    """
    insert instrument id in the table instrumentidmap if it does not exist.
    If the instrument exists, it will return its instrumentId
    """
    mycursor = mydb.cursor()
    query = "SELECT * FROM instrumentidnamemap WHERE name = %s " 
    args=(instrumentName,)
    mycursor.execute(query,args)
    records= mycursor.fetchall()
    row_count = mycursor.rowcount
    if row_count == 0:  #instrucmnet does not exists --> add it
        sql = "INSERT INTO instrumentidnamemap (instrumentId,name) VALUES (%s, %s)"
        val = (instrumentId,instrumentName)
        mycursor.execute(sql, val)
        mydb.commit()
        log.info("AddInstrumentId with name= {} and id ={}".format(instrumentId,instrumentName))
        return instrumentId
    else:#instruments exists
        return records[0][0]

instrumentIdNameMap={} #dictiory containing the mapping between the name and the instrucmnet id
def FillnameInstrumentIdMap():
    """
    Fill the map instrumentId-->name
    """
    global instrumentIdNameMap
    mycursor = mydb.cursor()
    query = "SELECT * FROM instrumentidnamemap " 
    mycursor.execute(query)
    records= mycursor.fetchall()
    for record in records:
        instrumentIdNameMap[record[0]]=record[1] # record[0]:id, record[1]=name
    log.info("instrumentIdNameMap size= {}".format(len(instrumentIdNameMap)))
# fill the dictionary 
FillnameInstrumentIdMap()


def GetInstrumentName(id):
    """
    return the name of the instrucmentId id
    """
    global instrumentIdNameMap
    return instrumentIdNameMap[id]



   
    