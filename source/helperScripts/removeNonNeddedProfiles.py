import sys
import os

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from alertsdatabase import AlertDatabase as alertsdb

mydb=alertsdb("removeNonNeddedProfiles")


AllFollowedProfiles=set()

mycursor = mydb.alertConnection.cursor()
mycursor.execute("SELECT * FROM map_etoroprofiles_channels")
records=mycursor.fetchall()
for record in records:
    AllFollowedProfiles.add(record[1])

listOfProfilesToRemove=set()

success,allEtoroProfiles=mydb.GetAllFollowedProfiles()
for profile in allEtoroProfiles:
    if profile[1] not in AllFollowedProfiles:
        listOfProfilesToRemove.add(profile[1])

for toremove in listOfProfilesToRemove:
    mydb.RemoveEtoroProfile(toremove)
    print('removing {}'.format(toremove))


print("Done")