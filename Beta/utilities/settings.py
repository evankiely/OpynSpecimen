import os
import pandas as pd


class Settings:
    def __init__(self):

        #  ---------------------------------------------------------------------
        #  NOTE Things most users will want/need to change -- OpS profile details, file paths, etc.
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

        self.translatorInputDir = "./input/translate/"
        self.pathReportInputDir = "./pathReports/"

        # eventually, below input dir should supplant the above for translator
        # NOTE when that happens, remember to update the requiredPaths below
        self.inputDir = "./input/"
        self.outputDir = "./output/"

        self.formOutPath = "./resources/universalForms.csv"
        self.fieldOutPath = "./resources/universalFields.csv"
        self.cpOutPath = "./resources/universalCPs.csv"
        self.dropdownOutpath = "./resources/dropdowns/_.csv"

        # for more info on date formats, see here: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

        self.dateFormat = "%m/%d/%Y"
        self.datetimeFormat = "%m/%d/%Y %H:%M:%S"
        self.timezone = "US/Eastern"
        self.fillerDate = "01/01/1900"  #  date to be used when one is missing and it needs to be obviously fake

        # number of async requests sent to the server at a time
        self.asyncChunkSize = 5
        # number of records passed to query look up -- limit to 2500 and below
        self.lookUpChunkSize = 2500

        self.participanteMPIMatchAQL = 'select CollectionProtocol.shortTitle as "Participant Original CP", Participant.empi as "eMPI", Participant.participantId as "Participant ID", Participant.id as "CPR ID" where Participant.empi in (_)'
        self.participantMRNMatchAQL = 'select CollectionProtocol.shortTitle as "Participant Original CP", Participant.medicalRecord.medicalRecordNumber as "$", Participant.participantId as "Participant ID", Participant.id as "CPR ID" where Participant.medicalRecord.mrnSiteName = "*" and Participant.medicalRecord.medicalRecordNumber in (_)'
        self.participantPPIDMatchAQL = 'select CollectionProtocol.shortTitle as "Participant Original CP", Participant.ppid as "PPID", Participant.participantId as "Participant ID", Participant.id as "CPR ID" where Participant.ppid in (_)'

        # used to populate PPIDs in cases where data omits them but includes another value like MRN, etc., which can be used to match profile and get Participant ID
        self.participantIDMatchAQL = 'select CollectionProtocol.shortTitle as "Participant Original CP", Participant.ppid as "PPID", Participant.participantId as "Participant ID", Participant.id as "CPR ID" where Participant.participantId in (_)'

        self.visitNameMatchAQL = 'select CollectionProtocol.shortTitle as "Visit Original CP", SpecimenCollectionGroup.name as "Visit Name", SpecimenCollectionGroup.id as "Visit ID" where SpecimenCollectionGroup.name in (_)'
        # below currently used only for uploading path reports, but could be used to match visits in general as well
        self.visitSurgicalAccessionNumberMatchAQL = 'select CollectionProtocol.shortTitle as "Visit Original CP", SpecimenCollectionGroup.name as "Visit Name", SpecimenCollectionGroup.id as "Visit ID", SpecimenCollectionGroup.surgicalPathologyNo as "Path. Number" where SpecimenCollectionGroup.surgicalPathologyNo in (_)'

        self.specimenMatchAQL = 'select CollectionProtocol.shortTitle as "Specimen Original CP", Specimen.label as "Specimen Label", Specimen.id as "Specimen ID" where Specimen.label in (_)'
        self.parentMatchAQL = (
            'select Specimen.label as "Parent Specimen Label", Specimen.id as "Parent ID" where Specimen.label in (_)'
        )

        self.participantAuditAQL = 'select Participant.participantId as "Participant ID", CollectionProtocol.shortTitle as "CP Short Title", Participant.ppid as "PPID", Participant.regDate as "Registration Date", Participant.site as "Registration Site", Participant.externalSubjectId as "External Subject ID", Participant.firstName as "First Name", Participant.lastName as "Last Name", Participant.middleName as "Middle Name", Participant.dateOfBirth as "Date Of Birth", Participant.deathDate as "Death Date", Participant.gender as "Gender", Participant.race as "Race#^", Participant.vitalStatus as "Vital Status", Participant.ethnicity as "Ethnicity#^", Participant.ssn as "SSN", Participant.empi as "eMPI", Participant.medicalRecord.mrnSiteName as "PMI#^#Site Name", Participant.medicalRecord.medicalRecordNumber as "PMI#^#MRN"$ where Participant.participantId in (*)'
        self.visitAuditAQL = 'select SpecimenCollectionGroup.id as "Visit ID", CollectionProtocol.shortTitle as "CP Short Title", Participant.ppid as "PPID", SpecimenCollectionGroup.collectionProtocolEvent.collectionPointLabel as "Event Label", SpecimenCollectionGroup.collectionProtocolEvent.eventPoint as "Event Point", SpecimenCollectionGroup.name as "Visit Name", SpecimenCollectionGroup.collectionDate as "Visit Date", SpecimenCollectionGroup.site as "Collection Site", SpecimenCollectionGroup.collectionStatus as "Visit Status", SpecimenCollectionGroup.clinicalDiagnoses.value as "Clinical Diagnosis", SpecimenCollectionGroup.clinicalStatus as "Clinical Status", SpecimenCollectionGroup.cohort as "Cohort", SpecimenCollectionGroup.surgicalPathologyNo as "Path. Number", SpecimenCollectionGroup.missedReason as "Missed/Not Collected Reason", SpecimenCollectionGroup.missedBy as "Missed/Not Collected By#Email Address", SpecimenCollectionGroup.activityStatus as "Visit Activity Status", SpecimenCollectionGroup.comments as "Visit Comments"$ where SpecimenCollectionGroup.id in (*)'
        self.specimenAuditAQL = 'select Specimen.id as "Specimen ID", CollectionProtocol.shortTitle as "CP Short Title", SpecimenCollectionGroup.name as "Visit Name", Specimen.requirement.code as "Specimen Requirement Code", Specimen.label as "Specimen Label", Specimen.barcode as "Barcode", Specimen.class as "Class", Specimen.type as "Type", Specimen.lineage as "Lineage", Specimen.parentSpecimen.parentLabel as "Parent Specimen Label", Specimen.tissueSite as "Anatomic Site", Specimen.tissueSide as "Laterality", Specimen.pathologicalStatus as "Pathological Status", Specimen.initialQty as "Initial Quantity", Specimen.availableQty as "Available Quantity", Specimen.concentration as "Concentration", Specimen.biohazards as "Biohazard", Specimen.freezeThawCycles as "Freeze/Thaw Cycles", Specimen.createdOn as "Created On", Specimen.comments as "Specimen Comments", Specimen.activityStatus as "Specimen Activity Status", Specimen.collectionStatus as "Collection Status", Specimen.specimenPosition.containerName as "Container", Specimen.specimenPosition.positionDimensionTwoString as "Row", Specimen.specimenPosition.positionDimensionOneString as "Column", Specimen.extensions.SpecimenCollectionEvent.time as "Collection Date", Specimen.extensions.SpecimenCollectionEvent.procedure as "Collection Procedure", Specimen.extensions.SpecimenCollectionEvent.container as "Collection Container", Specimen.extensions.SpecimenCollectionEvent.user as "Collector", Specimen.extensions.SpecimenCollectionEvent.comments as "Collection Comments", Specimen.extensions.SpecimenReceivedEvent.time as "Received Date", Specimen.extensions.SpecimenReceivedEvent.quality as "Received Quality", Specimen.extensions.SpecimenReceivedEvent.user as "Receiver", Specimen.extensions.SpecimenReceivedEvent.comments as "Received Comments"$ where Specimen.id in (*)'

        # templateTypes included here in case a user doesn't like the key reference vals (used in naming file for genericBulkUpload)
        # could replace "specimenaliquot": "specimenaliquot" with "aliquot": "specimenaliquot" for example, which would make file naming for uploads, etc. cleaner
        # sourced from: https://docs.google.com/spreadsheets/d/1fFcL91jSoTxusoBdxM_sr6TkLt65f25YPgfV-AYps4g/edit#gid=0
        # which can be found here: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/440434702/Bulk+Import+via+API

        # files supported by the below are not always csv or json, sometimes they are zip, pdf, jpg, etc.
        # which may require some additional validation and handling logic when selecting from folder/testing of function's ability to handle them
        # see here:https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/83899598/Bulk+Import+for+files+data+type+e.g.+pdf+images
        self.templateTypes = {
            "cp": "cp",  # Collection Protocol
            "specimen": "specimen",
            "cpr": "cpr",  # Collection Protocol Registration
            "user": "user",
            "userroles": "userRoles",
            "site": "site",
            "shipment": "shipment",
            "institute": "institute",
            "dprequirement": "dpRequirement",  # Distribution Protocol Requirement
            "distributionprotocol": "distributionProtocol",
            "distributionorder": "distributionOrder",
            "storagecontainer": "storageContainer",
            "storagecontainertype": "storageContainerType",
            "containershipment": "containerShipment",
            "cpe": "cpe",  # Collection Protocol Event
            "masterspecimen": "masterSpecimen",
            "participant": "participant",
            "sr": "sr",  # Specimen Requirement
            "visit": "visit",
            "specimenaliquot": "specimenAliquot",
            "specimenderivative": "specimenDerivative",
            "specimendisposal": "specimenDisposal",
            "consent": "consent",
        }

        self.requiredPaths = [
            "./resources",
            "./resources/dropdowns",
            self.translatorInputDir,
            self.pathReportInputDir,
            self.inputDir,
            self.outputDir,
        ] + [f"./workflows/{env}" for env in self.envs.keys()]

        self.buildEnv()

        #  ---------------------------------------------------------------------
        #  NOTE Things that will only change if OpS changes -- API endpoints, internal reference values, etc.
        #  ---------------------------------------------------------------------

        self.authExtension = "sessions"
        self.uploadExtension = "import-jobs/"
        self.uploadPathReportExtension = "visits/_/spr-file"
        self.formListExtension = "forms"
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
        self.specimenExtension = "specimens/_"
        self.aliquotExtension = "specimens/collect"
        self.arrayExtension = "specimen-arrays/"
        self.coreExtension = "specimen-arrays/_/cores"  # where _ is {arrayDetails['id']}
        self.queryExtension = "query"

        # see here for more info on below: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/71598083/Updating+value+as+blank+using+bulk+import
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
                    "listName": "cp-list-view",  #  could be left off, but defaults to returning only 100
                    "maxResults": "100000",
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
        """Constructs the environment required for this package to function"""

        for path in self.requiredPaths:

            if not os.path.exists(path):
                os.makedirs(path)

        if not os.path.exists(self.cpOutPath):
            columns = ["cpShortTitle", "cpTitle"] + [env for env in self.envs.keys()]
            cpDF = pd.DataFrame(columns=columns)
            cpDF.to_csv(self.cpOutPath, index=False)

        if not os.path.exists(self.formOutPath):
            columns = ["formName"]
            for env in self.envs.keys():
                columns += [f"{env}ShortName", env, f"{env}UpdateRecord"]

            formDF = pd.DataFrame(columns=columns)
            formDF.to_csv(self.formOutPath, index=False)

        if not os.path.exists(self.fieldOutPath):
            columns = (
                ["formName", "isSubForm", "fieldName", "isSubField"]
                + [env for env in self.envs.keys()]
                + [f"{env}UDN" for env in self.envs.keys()]
                + [f"{env}SubFormUDN" for env in self.envs.keys()]
                + [f"{env}SubFormName" for env in self.envs.keys()]
            )
            fieldDF = pd.DataFrame(columns=columns, dtype=str)
            fieldDF.to_csv(self.fieldOutPath, index=False)

    #  ---------------------------------------------------------------------

    def getEnVar(self, reference):
        """Accesses and retrieves the environmental variables specified in self.envs"""

        enVar = os.environ.get(f"{reference}")

        if enVar is not None:
            return enVar

        raise KeyError(f"Provided key, [{reference}], not found.")
