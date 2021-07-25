import enum
import sys
import os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from loglib import logger as log 


class Trade:
    def __init__(self,positionID):
        self.positionID= positionID # this is different than id  example: 925116338
        self.id= ""  #example 0__entry__a7ee66e3-5443-421e-a85d-95732c622f51
        self.market=""
        self.displayName=""
        self.direction=""
        self.leverage= 1
        self.rate= 0.0        
        self.messageBody= ""
        self.openClose=""
        self.gainLoss=0.0 #shall not be used anymore
        self.occuredAt=0
        self.order=False
        self.percentage="XX"
        self.stoploss=0.0
        self.takeprofit=0.0
        self.currentRate=0.0
        self.CloseRate=0.0
        self.NetProfit=0.0
        self.OpenDateTime=""
        self.image=""
 
        

    def ExtractAllData(self,actualTrade):
        """
        This will extract all the data from a trade
        return true if the data are successfully extracted
        """
        try:
            if 'id' in actualTrade :
                self.id=actualTrade['id']
            if 'type' in actualTrade:  # contains type
                if actualTrade['type']=="OpenTrade":
                    self.openClose="open"
                elif actualTrade['type']=='CloseTrade':
                    self.openClose="close"
                else:# type could be Discussion for example -->continue
                    return False
            symbol=actualTrade['symbol']
            self.market=symbol['name'].upper()
            if 'displayName' in symbol:
                self.displayName=symbol['displayName'].upper()
            if 'images' in symbol:
                if '50X50' in symbol['images']:
                    self.image=symbol['images']['50X50']
                else:
                    self.image=symbol['images'][list(symbol['images'].keys())[0]]
            if 'direction' in actualTrade:
                self.direction=actualTrade['direction']
            if 'leverage' in actualTrade:
                self.leverage=actualTrade['leverage']
            if 'rate' in actualTrade:
                self.rate=actualTrade['rate']
            if 'occurredAt' in actualTrade:
                self.occuredAt=actualTrade['occurredAt']
            if 'orderID' in actualTrade :
                self.order=True
            if 'OpenDateTime' in  actualTrade :
                self.OpenDateTime=actualTrade['OpenDateTime']
            if 'CloseDateTime' in  actualTrade :
                self.CloseDateTime=actualTrade['CloseDateTime'] #2021-02-13T21:02:48.3800000Z
            


            #extract message body:
            if 'messageBody' in actualTrade and  self.messageBody and self.openClose=="open" :
                #get the percentage of the open position
                usingposition=self.messageBody.find("using")+len("using ")
                endusingposition=self.messageBody.find("of")
                self.percentage=self.messageBody[usingposition:endusingposition]
                self.messageBody=actualTrade['messageBody']
            
            if 'gain' in actualTrade :
                if actualTrade['gain']!=0.0:
                    self.openClose="close"
                self.NetProfit=actualTrade['gain']


            if 'orderID' in actualTrade :
                self.order=True
 
                
            #get instrument id
            if 'instrumentID' in actualTrade["symbol"] :
                id=actualTrade["symbol"]['instrumentID']      
            return True
 
        except Exception as ex:
            log.error(" Exception in ExtractDetails() {}".format(ex))

    def ExtractDetails(self,actualTrade):
        """
        This will extract details of the  actualTrade
        return true if the data are successfully extracted
        """
        try:
            #self.market=""
            #self.displayName=""
            if not "IsBuy" in actualTrade:
                return
            if actualTrade["IsBuy"]:
                self.direction="long"
            else :
                self.direction="short"
            if "Leverage" in actualTrade:
                self.leverage= actualTrade["Leverage"]
            if "OpenRate" in actualTrade:
                self.rate= actualTrade["OpenRate"]
            if "OpenDateTime" in actualTrade:
                self.occuredAt= actualTrade["OpenDateTime"]
            if "StopLossRate" in actualTrade:
                self.stoploss= actualTrade["StopLossRate"]
            if "TakeProfitRate" in actualTrade:
                self.takeprofit= actualTrade["TakeProfitRate"]
            if "CurrentRate" in actualTrade:
                self.currentRate= actualTrade["CurrentRate"]
            if "CurrentRate" in actualTrade:
                self.currentRate= actualTrade["CurrentRate"]
            self.openClose="open"
            if "CloseRate" in actualTrade:
                self.CloseRate=actualTrade["CloseRate"]
            if "NetProfit" in actualTrade:
                self.NetProfit=actualTrade["NetProfit"]
            if "CloseDateTime" in actualTrade:
                self.CloseDateTime=actualTrade["CloseDateTime"]
            if "OpenDateTime" in actualTrade:
                self.OpenDateTime= actualTrade["OpenDateTime"]
        except Exception as ex:
            log.error(" Exception in ExtractDetails() {}".format(ex))
            return False

