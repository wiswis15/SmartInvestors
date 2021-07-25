
class Conditions:
    MaxNumberOfCpiers=50

class Member:
    def __init__(self,id):
        self.id=id           #id of the member in discord, must be unique
        self.private = False
        self.notFound= False # if the profile is missing on ETORO
        self.numberOfCopiers = 0
        self.display_name=""  #Discord display name
        self.nickName=""
        self.etoroProfile=""



