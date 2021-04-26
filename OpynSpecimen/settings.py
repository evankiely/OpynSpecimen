import os

import requests


class Settings:
    def __init__(self):

        #  ---------------------------------------------------------------------
        # Things most users will want/need to change -- OpS profile details, file paths, etc.
        #  ---------------------------------------------------------------------
        
        self.baseURL = "https://openspecimen_.domain.domain.domain/rest/ng/"

        self.envs = {
            "test": {
                "loginName": self.getEnVar("Test_Env_User"),
                "password": self.getEnVar("Test_Env_Pass"),
                "domainName": self.getEnVar("Test_Env_Domain"),
            },
            "dev": {
                "loginName": self.getEnVar("Dev_Env_User"),
                "password": self.getEnVar("Dev_Env_Pass"),
                "domainName": self.getEnVar("Dev_Env_Domain"),
            },
            "prod": {
                "loginName": self.getEnVar("Prod_Env_User"),
                "password": self.getEnVar("Prod_Env_Pass"),
                "domainName": self.getEnVar("Prod_Env_Domain"),
            },
        }

        self.formOutPath = "./resources/universalForms.csv"
        self.fieldOutPath = "./resources/universalFields.csv"
        self.cpOutPath = "./resources/universalCPs.csv"
        self.dropdownOutpath = "./resources/universalDropdowns.csv"
        self.translatorInputDir = "./input/translate/"
        self.translatorOutputDir = "./output/"  #  only need output for now because uploads won't have output, so no need to distinguish between that and translator
        self.uploadInputDir = "./input/upload/"

        # for more info on date formats, see here: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

        self.dateFormat = "%m/%d/%Y"
        self.datetimeFormat = "%m/%d/%Y %H:%M:%S"
        self.timezone = "America/New_York"
        self.fillerDate = "01/01/1900"  #  date to be used when one is missing and it needs to be obviously fake

        # templateTypes included here in case a user doesn't like the key reference vals (used in naming file for genericBulkUpload)
        # could replace "specimenaliquot": "specimenaliquot" with "aliquot": "specimenaliquot" for example, which would make file naming for uploads, etc. cleaner
        # sourced from: https://docs.google.com/spreadsheets/d/1fFcL91jSoTxusoBdxM_sr6TkLt65f25YPgfV-AYps4g/edit#gid=0
        # which can be found here: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/440434702/Bulk+Import+via+API

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
        }

        self.requiredPaths = [
            "./resources",
            "./dropdowns",
            self.translatorInputDir,
            self.uploadInputDir,
            self.translatorOutputDir,
        ] + [f"./workflows/{env}" for env in self.envs.keys()]

        self.buildEnv()

        #  ---------------------------------------------------------------------
        # Things that will only change if OpS changes -- API endpoints, internal reference values, etc.
        #  ---------------------------------------------------------------------

        self.authExtension = "sessions"
        self.uploadExtension = "import-jobs/"
        self.formListExtension = "forms"
        self.formExtension = "de-forms/"
        self.cpWorkflowListExtension = "collection-protocols/"
        self.cpWorkflowExtension = "collection-protocols/_/workflows"
        self.cpDefExtension = "collection-protocols/definition"
        self.groupWorkflowListExtension = "collection-protocol-groups/"
        self.groupWorkflowExtension = "collection-protocol-groups/_/workflows-file"
        self.dropdownExtension = "permissible-values/attributes"
        self.findMatchExtension = "participants/match"
        self.registerParticipantExtension = "collection-protocol-registrations/"
        self.pafExtension = "/participants/extension-form"  # paf = participant additional fields
        self.vafExtension = "/visits/extension-form"
        self.safExtension = "/specimens/extension-form"
        self.matchVisitExtension = "visits/bynamespr"
        self.visitExtension = "visits/_"
        self.specimenExtension = "specimens/"
        self.aliquotExtension = "specimens/collect"
        self.arrayExtension = "specimen-arrays/"
        self.coreExtension = "specimen-arrays/_/cores"  # where _ is {arrayDetails['id']}

        self.setBlankCode = "##set_to_blank##"

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

        self.unitMap = {
            "fluid": {"quantity": "ml"},
            #  technically grams should be just g, but the docs say gm...
            "tissue": {"quantity": "gm", "concentration": "ug/ml"},
            "cell": {"quantity": "cells", "concentration": "cells"},
            "molecular": {"quantity": "ug", "concentration": "ug/ml"},
        }

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
