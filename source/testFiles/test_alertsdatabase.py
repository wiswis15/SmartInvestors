import json
import sys

import urllib.request
import threading
import discord
from discord.ext import commands
import asyncio
from datetime import datetime,time,timedelta
import datetime as dt
import logging
import argparse
import os.path
import unittest
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import alertsdatabase as alertsdb



guild_id=5
guild_name="wissem"
owner_id=1515
channelid=100
etoroProfile="wisLina"




class TestStringMethods(unittest.TestCase):

    def test_AddDiscordUser(self):
        self.assertTrue(alertsdb.AddDiscordUser(owner_id))

    def test_AddDiscordGuild(self):
        self.assertTrue(alertsdb.AddDiscordGuild(guild_id,guild_name,owner_id))

    def test_NormalUseFlow(self):

        self.assertTrue(alertsdb.GetListOfFollowedProfiles(channelid,owner_id))
        self.assertTrue(alertsdb.FollowProfile(etoroProfile,channelid,owner_id))
        self.assertTrue(alertsdb.GetListOfFollowedProfiles(channelid,owner_id))
        self.assertTrue(alertsdb.FollowProfile(etoroProfile,channelid,owner_id))
        self.assertTrue(alertsdb.StopFollowingProfile(etoroProfile,channelid,owner_id))
        self.assertTrue(alertsdb.GetListOfFollowedProfiles(channelid,owner_id))

 

if __name__ == '__main__':
    unittest.main()







