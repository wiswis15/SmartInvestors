from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
import time
import sys
import os
import urllib.request, json


debugCheckProfiles=False
NotFound="Not Found"
chrome_driver_path=""
if  sys.platform=="win32":
    chrome_driver_path =os.path.join(os.path.dirname(os.path.realpath(__file__)),'chromedriver.exe')  
else:#link
    chrome_driver_path ='/usr/bin/chromedriver'
    

chrome_options = Options()
chrome_options.add_argument('--headless')

webdriver = webdriver.Chrome(  executable_path=chrome_driver_path, options=chrome_options)
WebDriverWait(webdriver,10) # wait 10 seconds


def IsPrivateProfile(url):
    """
    This function will check if the url is a Private ETORO profile or not.
    return True if Private profile
    return False,'Not Found'  if the profile has not been found
    """
    try:
        webdriver.get(url)
        soup=BeautifulSoup(webdriver.page_source,'lxml') #transform it into beautiful soup
        result=soup.get_text().find('Private Profile') 
        print("checking{}".format(url))
        if result > 0:#is a private profile
            if debugCheckProfiles:
                print(url+" is Private profile")
            return (True,"")
        else: 
            if  debugCheckProfiles:
                print(url+" is Open profile")
            return (False,"")
    except Exception as ex:
        print("Exception in IsPrivateProfile, details= {}".format(ex))
        return (False,NotFound)


def GetNumberOfCopiers(etoroProfile):
    """
    This function will get the number of copiers.
    The profile must be NON private.
    """
    try:
        #example
        link="https://www.etoro.com/sapi/userstats/copiers/userName/{}/history?".format(etoroProfile)
        url=urllib.request.urlopen(link)
        data = json.loads(url.read().decode())#data is a dictionary with key =dailyCopiers
        if len(data) == 0:
            return 0
        else:
            content=data['dailyCopiers']# return a list
            if len(content)==0:
                return 0  # 0 copiers
            lastElement=content[-1] #example {'timestamp': '2020-12-07T00:00:00Z', 'copiers': 6}
            numberOfCopiers=lastElement['copiers']
            print("EtoroProfile: {} has {} copiers".format(etoroProfile,numberOfCopiers))
            return numberOfCopiers
    except Exception as ex:
        print("Exception in GetNumberOfCopiers, details= {}".format(ex))
        


#just for testing
""""
openProfilewithNoCopier='https://www.etoro.com/people/wislina'
openProfileWithcopier='https://www.etoro.com/people/fcastel'
closedProfile='https://www.etoro.com/people/pascalartmeier'

IsPrivateProfile(openProfilewithNoCopier)
print(GetNumberOfCopiers("wislina"))
IsPrivateProfile(openProfileWithcopier)
print(GetNumberOfCopiers("fcastel"))
IsPrivateProfile(closedProfile) 
print(GetNumberOfCopiers("pascalartmeier"))
"""

