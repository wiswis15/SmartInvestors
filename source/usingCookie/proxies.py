from loglib import logger as log 
from threading import Lock
import sys
import os

ip_addresses = {"2.59.22.190:12330",
    "2.59.22.197:12330",
    "5.157.12.24:33224",
    "23.236.130.172:9800",
    "45.224.252.137:12333",
    "103.139.48.123:54440",
    "151.237.191.102:22333",
    "151.237.191.147:22333",
    "168.196.236.236:10009",
    "196.247.236.199:17888"}




class ProxiesProvider:
    """
    This class is the ip address providers, shall be common to all modules, so that all use the same ipaddress pool
    
    """
    listOfProxies=[]
    proxiescount=0
    numberOfProxies=0
    proxyLock=Lock()
    def __init__(self):
        self.name="Proxies Provider class"
        self.listOfProxies.extend(ip_addresses)
        ProxiesProvider.numberOfProxies=len(ProxiesProvider.listOfProxies)

    @staticmethod
    def GetOneProxy():  
        """
        Provides the next available proxy
        """      
        try:
            ProxiesProvider.proxyLock.acquire()
            ProxiesProvider.proxiescount+=1
            
            if ProxiesProvider.proxiescount >= ProxiesProvider.numberOfProxies:
                ProxiesProvider.proxiescount=0
            
            return ProxiesProvider.listOfProxies[ProxiesProvider.proxiescount]
        except Exception as ex: # pylint: disable=broad-except
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error("Exception in GetOneProxy {}:{} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
        finally:
            if (ProxiesProvider.proxyLock.locked()):
                ProxiesProvider.proxyLock.release()



