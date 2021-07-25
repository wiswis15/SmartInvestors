from trade import Trade as position
from datetime import datetime


rateSLalert =0.07  # this is the percentage for triggering Cautious alert about SL is about to get hit
timeBetweenTwoAlerts=60*2  # 2 minutes
SLAlerts={} #keep all active alerts

class DiscordAlert:
    def __init__(self,originTrade):
        self.trade=originTrade
    def NewPositionAlertMessage(self, trader):
        #send the Alert
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
        message ="{} has opened a new {} position on {} with leverage  {} \n".format(trader,self.trade.direction,self.trade.displayName,self.trade.leverage)

        #add common text
        if(self.trade.id):
            link="Trade: https://www.etoro.com/posts/"
            link+=str(self.trade.id)
            link+="\n"
            message+=link
        marketlink="Market: https://www.etoro.com/markets/"
        marketlink+=self.trade.displayName
        message+=marketlink
        message+="\n"
        message+="@everyone"
        return message
    

    def ClosedAlertMessage(self, trader):
        #send the Alert
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
        #beautify the text a bit
        if self.trade.NetProfit>0.0:
            self.trade.NetProfit=str(self.trade.NetProfit)+ " % "
        elif self.trade.NetProfit<0.0:
            self.trade.NetProfit=str(self.trade.NetProfit)+ " % "

        message=""
        if self.trade.order:
            message+="{} placed the following order: \n ".format(trader)

        message ="{} has closed a {} position on {} with leverage  {}  with Profit = {}\n".format(trader,self.trade.direction,self.trade.displayName,self.trade.leverage,self.trade.NetProfit)

        if(self.trade.id):
            link="Trade: https://www.etoro.com/posts/"
            link+=str(self.trade.id)
            link+="\n"
            message+=link
        marketlink="Market: https://www.etoro.com/markets/"
        marketlink+=self.trade.displayName
        message+=marketlink
        message+="\n"
        message+="@everyone"
        return message

    def DetectChangeInSLTP(self,trader,newPosition,oldPosition):
        """
        detect change in SL/TP and alert if the SL is about to be hit
        return (changeALert,SLAlert)
        """
        #send the Alert
        changeMessage=""
        SLCautionMessage=""
        if oldPosition.stoploss != newPosition.stoploss:
            changeMessage="Position ID: {} SL old rate: {} -->   SL new rate: {} \n"\
                .format(oldPosition.positionID,oldPosition.stoploss,newPosition.stoploss)
        if oldPosition.takeprofit != newPosition.takeprofit:
            changeMessage="Position ID: {} TP old rate: {} -->   TP new rate: {} \n"\
                .format(oldPosition.positionID,oldPosition.stoploss,newPosition.stoploss)
        

        #Long position check SL
        if newPosition.direction=="long":
            alertRate=newPosition.currentRate*(1-rateSLalert)
            if newPosition.currentRate < alertRate:
                firstAlert=False
                if not newPosition.positionID in  SLAlerts:
                    firstAlert=True
                timeSinceLastAlert=0
                if not firstAlert  :
                    timeSinceLastAlert= (datetime.now()-SLAlerts[newPosition.positionID]).seconds 
                if firstAlert or (timeSinceLastAlert > timeBetweenTwoAlerts):
                    SLCautionMessage="Position ID: {} current rate: {}  your SL: {}  \n"\
                    .format(newPosition.positionID,newPosition.currentRate,newPosition.stoploss)
                    SLAlerts[newPosition.positionID]=datetime.now()  #
        else:
            alertRate=newPosition.currentRate*(1+rateSLalert)
            if newPosition.currentRate > alertRate:
                firstAlert=False
                if not newPosition.positionID in  SLAlerts:
                    firstAlert=True
                timeSinceLastAlert=0
                if not firstAlert  :
                    timeSinceLastAlert= (datetime.now()-SLAlerts[newPosition.positionID]).seconds 
                if firstAlert or (timeSinceLastAlert > timeBetweenTwoAlerts):
                    SLCautionMessage="Position ID: {} current rate: {}  your SL: {}  \n"\
                    .format(newPosition.positionID,newPosition.currentRate,newPosition.stoploss)
                    SLAlerts[newPosition.positionID]=datetime.now()  #
        return (changeMessage,SLCautionMessage)