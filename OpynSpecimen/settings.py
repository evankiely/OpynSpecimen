import os

import requests


class Settings:
    def __init__(self):

        self.baseURL = "https://openspecimen_.domain.domain.domain/rest/ng/"
        self.authExtension = "sessions"

        self.envs = {
            "test": {
                "loginName": self.getEnVar("Test_Env_User"),
                "password": self.getEnVar("Test_Env_Pass"),
                "domainName": self.getEnVar("Test_Env_Domain"),
            },
            "dev": {
                "loginName": self.getEnVar("Dev_Env_User"),
                "password": self.getEnVar("Dev_Env__Pass"),
                "domainName": self.getEnVar("Dev_Env__Domain"),
            },
            "prod": {
                "loginName": self.getEnVar("Prod_Env_User"),
                "password": self.getEnVar("Prod_Env_Pass"),
                "domainName": self.getEnVar("Prod_Env_Domain"),
            },
        }

        self.uploadExtension = "import-jobs/"
        self.templateTypes = {
            "cp": "cp",
            "specimen": "specimen",
            "cpr": "cpr",
            "user": "user",
            "userroles": "userRoles",
            "site": "site",
            "shipment": "shipment",
            "institute": "institute",
            "dprequirement": "dpRequirement",
            "distributionprotocol": "distributionProtocol",
            "distributionorder": "distributionOrder",
            "storagecontainer": "storageContainer",
            "storagecontainertype": "storageContainerType",
            "containershipment": "containerShipment",
            "cpe": "cpe",
            "masterspecimen": "masterSpecimen",
            "participant": "participant",
            "sr": "sr",
            "visit": "visit",
            "specimenaliquot": "specimenAliquot",
            "specimenderivative": "specimenDerivative",
            "specimendisposal": "specimenDisposal",
            "consent": "consent",
        }  #  sourced from: https://docs.google.com/spreadsheets/d/1fFcL91jSoTxusoBdxM_sr6TkLt65f25YPgfV-AYps4g/edit#gid=0 which can be found here: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/440434702/Bulk+Import+via+API

        self.formListExtension = "forms"
        self.formExtension = "de-forms/"
        self.formOutPath = "./resources/universalForms.csv"
        self.fieldOutPath = "./resources/universalFields.csv"

        self.cpOutPath = "./resources/universalCPs.csv"
        self.cpWorkflowListExtension = "collection-protocols/"
        self.cpWorkflowExtension = "_/workflows"
        self.groupWorkflowListExtension = "collection-protocol-groups/"
        self.groupWorkflowExtension = "_/workflows-file"

        self.dropdownExtension = "permissible-values/attributes"
        self.dropdownOutpath = "./resources/universalDropdowns.csv"

        self.findMatchExtension = "participants/match"
        self.registerParticipantExtension = "collection-protocol-registrations/"

        self.pvExtensionDetails = {
            "pvExtension": "permissible-values/",
            "params": {
                "attribute": "",  #  set this at the time of calling the URL like self.pvExtensionDetails["params"]["attribute"] = DROPDOWN NAME
                "maxResults": "100000",
            },
        }

        self.workflowListDetails = [
            {
                "listExtension": self.cpWorkflowListExtension,
                "shortTitleKey": "shortTitle",
                "params": {
                    "listName": "cp-list-view",  #  could be left off, but defaults to returning only like 100
                    "maxResults": "1000",
                },
            },
            {
                "listExtension": self.groupWorkflowListExtension,
                "shortTitleKey": "name",
                "params": None,
            },
        ]

        self.translatorInputDir = "./input/translate/"
        self.translatorOutputDir = "./output/"  #  only need output for now because uploads won't have output, so no need to distinguish between that and translator
        self.uploadInputDir = "./input/upload/"

        self.requiredPaths = [
            "./resources",
            "./dropdowns",
            self.translatorInputDir,
            self.uploadInputDir,
            self.translatorOutputDir,
        ] + [f"./workflows/{env}" for env in self.envs.keys()]
        self.buildEnv()

    #  ---------------------------------------------------------------------

    def buildEnv(self):

        for path in self.requiredPaths:

            if not os.path.exists(path):
                os.makedirs(path)

    #  ---------------------------------------------------------------------

    def getEnVar(self, reference):

        enVar = os.environ.get(f"{reference}")

        if enVar is not None:
            return enVar

        else:
            raise NameError(f"Provided key, [{reference}], not found.")
