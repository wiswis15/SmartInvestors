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
from alertsdatabase import AlertDatabase as alertsdb
import requests



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




#WebDriverWait(webdriver,10) # wait 10 seconds

mydb=alertsdb("mainThread")

mycursor = mydb.alertConnection.cursor()
mycursor.execute("SELECT * FROM instrumentidnamemap")
records=mycursor.fetchall()
# gets the number of rows affected by the command executed
row_count = mycursor.rowcount


for record in records:
    try:
        if record[2]:
            continue
        name=record[1]
        path="https://www.etoro.com/markets/{}".format(name.lower())
        webdriver.get(path)
        avatarNomProfile=webdriver.find_element_by_xpath("//img[@class='avatar']")
        #avatarNomProfile=webdriver.find_element_by_class_name("content-avatar-ph")
        image=avatarNomProfile.get_attribute('src')
        sql = "UPDATE instrumentidnamemap SET image = %s WHERE name = %s"
        args=(image,name, )
        mycursor.execute(sql,args)
        mydb.alertConnection.commit()
        time.sleep(10)
        print("done with {} \n".format(name))


    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Exception in ReloadDatabase {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
        sql = "UPDATE instrumentidnamemap SET image = %s WHERE name = %s"
        args=("",name, )
        mycursor.execute(sql,args)
        mydb.alertConnection.commit()
        time.sleep(10)
        continue




print("done")

