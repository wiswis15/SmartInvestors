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
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from alertsdatabase import AlertDatabase as alertsdb
import requests


chrome_driver_path=""
if  sys.platform=="win32":
    chrome_driver_path =os.path.join(os.path.dirname(os.path.realpath(__file__)),'chromedriver.exe')  
else:#link
    chrome_driver_path ='/usr/bin/chromedriver'
    

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument("--no-sandbox")
webdriver = webdriver.Chrome(  executable_path=chrome_driver_path, options=chrome_options)




#WebDriverWait(webdriver,10) # wait 10 seconds

mydb=alertsdb("mainThread")

mycursor = mydb.alertConnection.cursor()
mycursor.execute("SELECT * FROM etoroprofiles where image ='';")
records=mycursor.fetchall()
# gets the number of rows affected by the command executed
row_count = mycursor.rowcount


for record in records:
    try:
        name=record[1]
        path="https://www.etoro.com/people/{}".format(name.lower())
        webdriver.get(path)
        avatarNomProfile=webdriver.find_element_by_xpath("//img[@class='avatar']")
        #avatarNomProfile=webdriver.find_element_by_class_name("content-avatar-ph")
        image=avatarNomProfile.get_attribute('src')
        sql = "UPDATE etoroprofiles SET image = %s WHERE profile = %s"
        args=(image,name, )
        mycursor.execute(sql,args)
        mydb.alertConnection.commit()
        time.sleep(10)
        print("done with {} \n".format(name))


    except Exception as ex: # pylint: disable=broad-except
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Exception while searching profile image {} {} {} {}".format(exc_type, fname, exc_tb.tb_lineno,ex))
        time.sleep(10)
        continue




print("done")

