import os
import json
import time
import pytz
import shutil
import random
from datetime import datetime

import requests
import numpy as np
import pandas as pd

from tqdm import tqdm
import jsonpickle as jp

from uploadClasses import *
from settings import Settings

# from utilities.uploadClasses import *
# from utilities.settings import Settings


class Integration(Settings):
    def __init__(self):

        super().__init__()
        self.currentEnv = None
        self.isUniversal = False
        self.authTokens = self.getTokens()

    #  ---------------------------------------------------------------------

    def renewTokens(self):
        self.authTokens = self.getTokens()

    #  ---------------------------------------------------------------------

    def getTokens(self):

        authTokens = {}

        for env, data in self.envs.items():

            if env == "prod":
                url = self.baseURL.replace("_", "") + self.authExtension

            else:
                url = self.baseURL.replace("_", env) + self.authExtension

            response = requests.post(url, json=data)
            response.raise_for_status()

            authTokens.update({env: response.json()["token"]})

        return authTokens

    #  ---------------------------------------------------------------------

    def syncAll(self, envs=None):

        self.syncWorkflowList(envs)
        self.syncWorkflows(envs)
        self.syncFormList(envs)
        self.syncFieldList(envs)
        self.syncDropdownList(envs)
        self.syncDropdownPVs(envs)

    #  ---------------------------------------------------------------------

    def getResponse(self, extension, params=None):

        if self.currentEnv == "prod":
            url = self.baseURL.replace("_", "")

        else:
            url = self.baseURL.replace("_", self.currentEnv)

        url += extension
        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token}

        if params is not None:
            response = requests.get(url, headers=headers, params=params)

        else:
            response = requests.get(url, headers=headers)

        if not response.ok and response.json()[0]["code"] == "VISIT_NOT_FOUND":
            return None

        elif not response.ok:
            response.raise_for_status()

        #  .text turns an empty list into "[]" which returns 2 when len applied
        if len(response.text) <= 2:
            return None

        try:

            initialDict = json.loads(response.text)
            return initialDict

        except:
            return response.text

    #  ---------------------------------------------------------------------  Maybe combine these response functions with the method kwarg determining function? maybe pull matchPPID into its own function?

    def postResponse(self, extension, data, method="POST", matchPPID=False):

        if self.currentEnv == "prod":
            url = self.baseURL.replace("_", "")

        else:
            url = self.baseURL.replace("_", self.currentEnv)

        url += extension
        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        obj = data
        data = jp.encode(data, unpicklable=False)

        response = requests.request(method, url, headers=headers, data=data)

        #  if there's a participant with the same PPID in the cp already, see if they match the participant being uploaded
        ppidErrors = ["CPR_DUP_PPID", "CPR_MANUAL_PPID_NOT_ALLOWED"]

        if not response.ok and matchPPID and response.json()[0]["code"] in ppidErrors:

            #  documentation was incorrect here -- use "birthDate" instead of "DOB"
            matchData = {
                "cpId": obj.cpId,
                "name": obj.participant.lastName,
                "ppid": obj.ppid,
                "birthDate": obj.participant.birthDate,
                "maxResults": 1,
                "exactMatch": True,
            }

            matchExtension = extension + "list"
            response = self.postResponse(matchExtension, matchData)

            #  if there is a match, get the match's cprId and use that to update the info associated with that participant
            if response:

                #  extension needs to be CPR ID for participant who matched PPID in the CP of interest
                extension += str(response[0]["id"])
                response = self.postResponse(extension, obj, method="PUT")

            else:

                print(response.text)
                response.raise_for_status()

        elif not response.ok:

            print(response.text)
            response.raise_for_status()

        else:

            initialDict = json.loads(response.text)
            return initialDict

    #  ---------------------------------------------------------------------

    def postFile(self, extension, files):

        if self.currentEnv == "prod":
            url = self.baseURL.replace("_", "")

        else:
            url = self.baseURL.replace("_", self.currentEnv)

        url += extension
        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token}
        response = requests.request("POST", url, headers=headers, files=files)

        if not response.ok:

            print(response.text)
            response.raise_for_status()

        else:

            response = json.loads(response.text)
            return response

    #  ---------------------------------------------------------------------
    #  should enable standard bulk uploads as per the gui -- TESTED WITH ONLY SMALL SAMPLE OF SPECIMENS AS OF 03/11/2021
    def genericBulkUpload(self, importType="CREATE", checkStatus=False):

        inputItems = [item for item in os.listdir(self.uploadInputDir) if item.split("_")[0].lower() == "genericbulk"]

        for item in inputItems:

            if not item.endswith(".csv"):
                raise TypeError("Input files must be of type .CSV")

            if item.split("_")[1].lower() in self.envs.keys():
                self.currentEnv = item.split("_")[1].lower()

            else:
                raise KeyError(
                    "Upload file names must be in the following format: [Category]_[Environment Key]_[Template Type]_[Additional Misc. Content].CSV"
                )
            #  DOES NOT ACCOUNT FOR .CSV IF IND[2] IS NOT FOLLOWED BY ADDITIONAL INFO
            if item.split("_")[2].lower() in self.templateTypes.keys():
                templateType = item.split("_")[2].lower()

            else:
                raise KeyError(
                    "Upload file names must be in the following format: [Category]_[Environment Key]_[Template Type]_[Additional Misc. Content].CSV"
                )

            inputItemLoc = self.uploadInputDir + item
            formatDF = pd.read_csv(inputItemLoc)
            cols = [col for col in formatDF.columns.values]

            for col in cols:

                #  format to something OpS will accept
                if "date" in col.lower() or "created" in col.lower():
                    formatDF[col] = formatDF[col].apply(self.cleanDateForBulk)

            #  maybe add check column headers against the template column headers based on the importType
            formatDF.to_csv(inputItemLoc, index=False)
            extension = self.uploadExtension + "input-file"
            files = [("file", (".csv", open(inputItemLoc, "rb"), "application/octet-stream"))]
            fileID = self.postFile(extension, files)
            fileID = fileID["fileId"]

            data = {
                "objectType": self.templateTypes[templateType],
                "importType": importType,
                "inputFileId": fileID,
            }

            uploadResponse = self.postResponse(self.uploadExtension, data)
            uploadID = uploadResponse["id"]

            if checkStatus:

                status = None
                statusList = ["completed", "stopped", "failed"]
                extension = self.uploadExtension + str(uploadID)

                while status is None:
                    uploadStatus = self.getResponse(extension)

                    if uploadStatus and "status" in uploadStatus.keys():

                        if uploadStatus["status"].lower() in statusList:
                            status = uploadStatus["status"].lower()

                            if status == "failed":

                                extension += "/output"
                                uploadStatus = self.getResponse(extension)

                                with open(
                                    f"{self.translatorOutputDir}/Failed Upload {uploadID} Report.csv",
                                    "w",
                                ) as f:
                                    f.write(uploadStatus)

                    else:
                        time.sleep(5)

                print(f"Status of job {uploadID} is {status}!")

            shutil.move(inputItemLoc, self.translatorOutputDir)

    #  ---------------------------------------------------------------------

    def uploadCPJSON(self):

        inputItems = [item for item in os.listdir(self.uploadInputDir) if item.split("_")[0].lower() == "cpdef"]

        for item in inputItems:

            if not item.endswith(".json"):
                raise TypeError("Input files must be of type .JSON")

            if item.split("_")[1].lower() in self.envs.keys():
                self.currentEnv = item.split("_")[1].lower()

            else:
                raise KeyError(
                    "Upload file names must be in the following format: [Category]_[Environment Key]_[Additional Misc. Content].CSV"
                )

            inputItemLoc = self.uploadInputDir + item
            files = [("file", (".json", open(inputItemLoc, "rb"), "application/octet-stream"))]
            response = self.postFile(self.cpDefExtension, files)

            shutil.move(inputItemLoc, self.translatorOutputDir)

    #  ---------------------------------------------------------------------
    #  combine these date cleaning functions with forBulk or forAPI flags to change the ordering -- pass args/kwargs to pd.apply()
    def cleanDateForBulk(self, date):

        if pd.isna(date):
            return None

        if " " in date:
            date = date.split(" ")[0]

        if "/" in date:
            date = date.split("/")

            if len(date[0]) == 1:
                date[0] = "0" + date[0]

            if len(date[1]) == 1:
                date[1] = "0" + date[1]

            if len(date[2]) == 2:
                raise ValueError(
                    "Looks like there is an issue with date formatting. Perhaps your years are abbreviated?"
                )

            date = "-".join([date[0], date[1], date[2]])

        return date

    #  ---------------------------------------------------------------------

    def padDates(self, date):

        if pd.isna(date) or len(date) == 10:
            return date

        else:

            date = date.split("/")

            if len(date[0]) == 1:
                date[0] = "0" + date[0]

            if len(date[1]) == 1:
                date[1] = "0" + date[1]

            date = "/".join(date)

            return date

    #  ---------------------------------------------------------------------

    def fillQuantities(self, item):

        df = pd.read_csv(item, dtype=str)

        parentFilt = (pd.isna(df["Parent Specimen Label"])) & (pd.notna(df["Initial Quantity"]))
        parentDF = df.loc[parentFilt]

        for ind, data in parentDF.iterrows():

            parentQuantity = data["Initial Quantity"]

            filt = df["Parent Specimen Label"] == data["Specimen Label"]
            children = df.loc[filt]

            # If no aliquots from a parent, do nothing
            if not children.empty:

                df.loc[ind, "Available Quantity"] = "0"

                if children["Initial Quantity"].empty:

                    numChildren = children["Specimen Label"].count()
                    childLabels = children["Specimen Label"].values

                    for label in childLabels:

                        childFilt = df["Specimen Label"] == label

                        df.loc[childFilt, ["Initial Quantity", "Available Quantity"]] = str(
                            float(parentQuantity) / numChildren
                        )

        # for derived specimens that started with some available quantity, and were ignored above as a result
        # just populating from intial to available if there is an initial but no available
        derivativeFilt = (
            (pd.notna(df["Lineage"]))
            & (df["Lineage"] != "New")
            & (pd.notna(df["Initial Quantity"]))
            & (pd.isna(df["Available Quantity"]))
        )

        derivativeDF = df.loc[derivativeFilt]

        for ind, val in derivativeDF.iterrows():
            df.loc[ind, "Available Quantity"] = df.loc[ind, "Initial Quantity"]

        df.to_csv(item, index=False)

        # return df

    #  ---------------------------------------------------------------------
    #  uses system-wide ids to match an existing participant profile
    def matchParticipants(self, pmis=None, empi=None):

        if isinstance(pmis, dict):
            passVals = ["pmi", pmis]

        elif isinstance(empi, str) or isinstance(empi, int):
            passVals = ["empi", empi]

        else:

            if pmis is not None:
                raise KeyError("pmis must be passed as a dict")

            elif empi is not None:
                raise KeyError("empi must be passed as a string or integer")

            else:
                raise KeyError("must pass non-None type pmis (dict) or empi (string or integer)")

        indentifier = {passVals[0]: passVals[1], "reqRegInfo": True}
        details = self.postResponse(self.findMatchExtension, indentifier)

        if details:

            vals = {record["cpShortTitle"]: record["cprId"] for record in details[0]["participant"]["registeredCps"]}
            vals["IDVal"] = details[0]["participant"]["id"]
            return vals

        else:
            return None

    #  ---------------------------------------------------------------------

    def makeParticipants(self, matchPPID=False):

        cols = self.participantDF.columns.values
        self.setCPDF(envs=self.currentEnv)

        for ind, data in tqdm(self.participantDF.iterrows(), desc="Participant Uploads", unit=" Participants"):

            extension = self.registerParticipantExtension

            cpShortTitle = data["CP Short Title"]
            formExten = self.formExtensions[data["CP Short Title"]]

            exten = Extension()

            #  if so, we should account for that in our data source as well as in our upload, so we get the required form id and name, and set the form data frame
            if formExten:
                exten = self.buildExtensionDetail(formExten, data)

            #  now we define all the remaining variables
            data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}

            #  putting mrn sites and vals into lists
            siteNames = [
                data[site]
                for site in data.keys()
                if "#site" in site.lower() and "pmi#" in site.lower() and site is not None
            ]
            mrnVals = [
                data[mrnVal]
                for mrnVal in data.keys()
                if "#mrn" in mrnVal.lower() and "pmi#" in mrnVal.lower() and mrnVal is not None
            ]

            #  making individual dicts for each mrn site and corresponding val
            pmis = [
                {"siteName": site, "mrn": int(mrnVal)}
                for site, mrnVal in zip(siteNames, mrnVals)
                if len(siteNames) > 0 and len(mrnVals) > 0 and mrnVal is not None
            ]

            #  putting races and ethnicities into lists
            races = [data.get(col) for col in cols if "race" in col.lower() and data.get(col) is not None]
            ethnicities = [data.get(col) for col in cols if "ethnicity" in col.lower() and data.get(col) is not None]

            firstName, middleName = data.get("First Name"), data.get("Middle Name")
            lastName, uid = data.get("Last Name"), data.get("SSN")
            birthDate, vitalStatus = data.get("Date Of Birth"), data.get("Vital Status")
            deathDate, gender = data.get("Death Date"), data.get("Gender")
            sexGenotype, externalSubjectId = None, data.get("External Subject ID")
            empi, activityStatus = data.get("eMPI"), data.get("Activity Status")
            ppid, registrationDate = data.get("PPID"), data.get("Registration Date")
            idVal = None

            #  rather than structuring them as nested dicts, just pass them into an object and let jsonPickle handle the rest

            participant = Registration(
                Participant(
                    idVal,
                    firstName,
                    middleName,
                    lastName,
                    uid,
                    birthDate,
                    vitalStatus,
                    deathDate,
                    gender,
                    races,
                    ethnicities,
                    activityStatus,
                    sexGenotype,
                    pmis,
                    empi,
                    exten,
                ),
                cpShortTitle,
                activityStatus,
                ppid,
                registrationDate,
                externalSubjectId,
            )

            matchedVals = None

            #  will be skipped if len == 0, otherwise it will check every PMI val for match until a match is found or there are no more PMIs to check
            for pmi in pmis:
                if matchedVals is None:
                    matchedVals = self.matchParticipants(pmis=pmi)

                else:
                    break

            #  if there are no PMIs above, or no matches to them, and there is a value for empi, try that instead
            if matchedVals is None and empi is not None:
                matchedVals = self.matchParticipants(empi=empi)

            #  otherwise, regardless of matched from PMIs or empi, as long as there is a match, we can move forward with using the existing profile
            if matchedVals is not None:

                participant.participant.id = str(matchedVals["IDVal"])
                registeredCPs = [key for key in matchedVals.keys() if key is not "IDVal"]

                #  if already in the cp we are uploading to, do it as an update using their CP Registration ID
                if cpShortTitle in registeredCPs:

                    extension += str(matchedVals[cpShortTitle])
                    response = self.postResponse(extension, participant, method="PUT")

                #  otherwise, since they exist in some other cp, do it as register existing participant to new cp
                #  matchPPID allows the function to look for cases where PPID matches to a participant in the CP, even if the MRN/EMPI was absent/failed to match
                else:
                    response = self.postResponse(extension, participant, matchPPID=matchPPID)

            # finally, if they don't exist in openspecimen at all, just make them a new profile, unless their activity status is disabled, in which case no need
            # elif activityStatus is None or activityStatus.lower() != "disabled":
            else:
                response = self.postResponse(extension, participant, matchPPID=matchPPID)

            # Below is intended as a way to capture and write new PPIDs created when uploading data which excludes them
            if response and ppid is None:

                # included for universal separately since it could continue on to making specimens, and visit name is critical info for that
                if self.isUniversal:
                    filt = (
                        (self.universalDF["First Name"] == firstName)
                        & (self.universalDF["Last Name"] == lastName)
                        & (self.universalDF["Registration Date"] == registrationDate)
                    )
                    self.universalDF.loc[filt, "PPID"] = response["ppid"]

                filt = (
                    (self.recordDF["First Name"] == firstName)
                    & (self.recordDF["Last Name"] == lastName)
                    & (self.recordDF["Registration Date"] == registrationDate)
                )
                self.recordDF.loc[filt, "PPID"] = response["ppid"]
                self.recordDF.to_csv(
                    f"{self.translatorOutputDir}/records_{' '.join(self.currentItem.split('_')[1:])}", index=False
                )

    #  ---------------------------------------------------------------------
    #  This is a confusing function because OpS relies very heavily on generic attribute names. In this case, what is meant by "id" in the docs varies by context
    def uploadParticipants(self, matchPPID=False):

        #  matchPPID is used when the participant may not have a system level ID (like PMI/mrn or empi) associated with their profile in the CP of interest, but does already have a profile in that CP
        #  In that case, the participant won't show up as a match in that CP, since there is no way to link that profile to their system-wide profile via mrn/empi
        #  if that happens, and the PPID being uploaded is the same as their existing profile, there will be a conflict
        #  it will appear to OpS as if there is a profile with that PPID already, and which is independent of the info being uploaded, since the profile failed to match on PMIs/empi
        #  so matchPPID attempts to get the CP level ID for the profile in order to modify it with the new data, including linking them with the system level IDs
        #  in this implimentation, we narrow our pool of matches to only profiles in the CP of interest, then pass the PPID (with the exactMatch flag set to true), as well as last name and date of birth
        #  it is possible to pass other values, like registration date (but this is potentially variable vs. DOB), and participantID (which is what is missing from the profile in the first place, so not useful here)
        #
        #  note that this is distinct from the matchParticipants function, which uses a system-wide id (like PMI/mrn or empi) to identify that high level participant profile with certainty.
        #  this implementation is specific to a particular CP
        #
        #  TODO: change dict indexing from .get() when the value is required or check required to make sure they're not None and raise error if they are
        #  TODO: add criticalCols/criticalErrors check, as in auditData function, if above todo is insufficient
        #  TODO: if a participant matches, check their details -- if all details match what is to be uploaded, no need to do anything and can skip to the next person

        inputItems = self.validateInputFiles(self.uploadInputDir, "participants")

        for item, env in inputItems.items():

            self.currentEnv = env
            self.currentItem = item
            self.participantDF = pd.read_csv(item)
            self.preuploadAudit("participants")
            self.recordDF = self.participantDF.copy()

            cols = self.participantDF.columns.values

            for col in cols:
                self.participantDF[col] = self.participantDF[col].apply(self.toUTC, args=[col])

            self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            cpIDs = self.participantDF["CP Short Title"].unique()
            cpIDs = {
                cpShortTitle: self.cpDF.loc[(self.cpDF["cpShortTitle"] == cpShortTitle), env].astype(
                    int, errors="ignore"
                )
                for cpShortTitle in cpIDs
            }

            #  getting all visit additional field form info and making a dict as above
            self.formExtensions = {
                cpShortTitle: self.getResponse(self.pafExtension, params={"cpId": cpId})
                for cpShortTitle, cpId in cpIDs.items()
            }

            self.makeParticipants(matchPPID=matchPPID)

            shutil.move(item, self.translatorOutputDir)

    #  ---------------------------------------------------------------------

    def toUTC(self, data, col):

        tz = pytz.timezone(self.timezone)
        dtVals = ["date", "time", "created on"]
        isDTCol = [(True if val in col.lower() else False) for val in dtVals]

        if True in isDTCol and pd.notna(data):

            if "birth" in col.lower() or "death" in col.lower():

                data = data.split(" ")[0].split("/")
                data = "-".join([data[2], data[0], data[1]])

                return data

            else:

                try:
                    dt = datetime.strptime(data, self.datetimeFormat)

                except:
                    dt = datetime.strptime(data, self.dateFormat)

        # considered returning filler date even if birth or death in col, but probably best not to
        elif True in isDTCol[:1] and "death" not in col.lower() and "birth" not in col.lower():
            dt = datetime.strptime(self.fillerDate, self.dateFormat)

        else:
            return data

        converted = tz.localize(dt)
        timestamp = str(int(converted.timestamp()) * 1000)

        return timestamp

    #  ---------------------------------------------------------------------

    def fromUTC(self, utcVal):

        if utcVal is None:
            return None

        elif isinstance(utcVal, str):
            utcVal = int(utcVal)

        data = datetime.utcfromtimestamp(utcVal / 1000).strftime("%m/%d/%Y")
        return data

    #  ---------------------------------------------------------------------

    def universalUpload(self, matchPPID=False):

        self.isUniversal = True
        inputItems = self.validateInputFiles(self.uploadInputDir, "universal")

        for item, env in inputItems.items():

            self.currentEnv = env
            self.currentItem = item
            item = item.lower()
            self.universalDF = pd.read_csv(item, dtype=str).dropna(axis=0, how="all").dropna(axis=1, how="all")
            self.recordDF = self.universalDF.copy()

            self.universalCols = self.universalDF.columns.values

            for col in tqdm(self.universalCols, desc="Columns Processed", unit=" Columns"):
                self.universalDF[col] = self.universalDF[col].apply(self.toUTC, args=[col])

            self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            cpIDs = self.universalDF["CP Short Title"].unique()
            cpIDs = {
                cpShortTitle: self.cpDF.loc[(self.cpDF["cpShortTitle"] == cpShortTitle), env].astype(
                    int, errors="ignore"
                )
                for cpShortTitle in cpIDs
            }

            if "universal" in item or "participants" in item:

                self.validateAndAuditUpload("participants", matchPPID=matchPPID)

                #  getting all visit additional field form info and making a dict as above
                self.formExtensions = {
                    cpShortTitle: self.getResponse(self.pafExtension, params={"cpId": cpId})
                    for cpShortTitle, cpId in cpIDs.items()
                }

                self.makeParticipants(matchPPID=matchPPID)

            if "universal" in item or "visits" in item:

                self.validateAndAuditUpload("visits")

                #  getting all visit additional field form info and making a dict as above
                self.formExtensions = {
                    cpShortTitle: self.getResponse(self.vafExtension, params={"cpId": cpId})
                    for cpShortTitle, cpId in cpIDs.items()
                }

                self.makeVisits()

            if "universal" in item or "specimens" in item:

                self.validateAndAuditUpload("specimens")

                #  getting all specimen additional field form info and making a dict as above
                self.formExtensions = {
                    cpShortTitle: self.getResponse(self.safExtension, params={"cpId": cpId})
                    for cpShortTitle, cpId in cpIDs.items()
                }

                self.recursiveSpecimens()

            shutil.move(item, self.translatorOutputDir)

        self.isUniversal = False

    #  ---------------------------------------------------------------------

    def matchVisit(self, visitName):

        params = {"visitName": visitName, "exactMatch": True}
        visitId = self.getResponse(self.matchVisitExtension, params=params)

        if visitId:

            visitId = visitId[0]["id"]
            return visitId

        else:
            return None

    #  ---------------------------------------------------------------------

    def makeVisits(self):

        cols = self.visitDF.columns.values

        for ind, data in tqdm(self.visitDF.iterrows(), desc="Visit Uploads", unit=" Visits"):

            formExten = self.formExtensions[data["CP Short Title"]]

            if formExten:
                extensionDetail = self.buildExtensionDetail(formExten, data)

            #  since it's required for specimen class, and attrsMap defaults to an empty dict, go ahead and make an empty Extension instance
            else:
                extensionDetail = Extension()

            data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}

            if self.isUniversal:
                comments, name = data.get("Visit Comments"), data.get("Visit Name")
                site = data.get("Collection Site")

            else:
                comments, name = data.get("Comments"), data.get("Name")
                site = data.get("Visit Site")

            eventLabel = data.get("Event Label")

            if name is None and eventLabel is None:
                raise Exception("A Visit Name or Event Label is required")

            eventId, status = data.get("Event Id"), data.get("Visit Status")
            ppid, cpTitle = data.get("PPID"), data.get("CP Title")
            cpShortTitle = data.get("CP Short Title")
            clinicalStatus, activityStatus = data.get("Clinical Status"), data.get("Activity Status")
            missedReason = data.get("Missed/Not Collected Reason")
            missedBy = data.get("Missed/Not Collected By#Email Address")
            surgicalPathologyNumber = data.get("Path. Number")
            cohort, visitDate = data.get("Cohort"), data.get("Visit Date")
            cprId, eventPoint = None, data.get("Event Point")

            clinicalDiagnoses = [
                data.get(col) for col in cols if "clinical diagnosis#" in col.lower() and data.get(col) is not None
            ]

            visit = Visit(
                eventId,
                eventLabel,
                ppid,
                cpTitle,
                cpShortTitle,
                name,
                clinicalStatus,
                activityStatus,
                site,
                status,
                extensionDetail,
                missedReason,
                missedBy,
                comments,
                surgicalPathologyNumber,
                cohort,
                visitDate,
                clinicalDiagnoses,
                eventPoint,
                cprId,
            )

            visit.code = self.matchVisit(name)

            if visit.code:

                extension = self.visitExtension.replace("_", str(visit.code))
                response = self.postResponse(extension, visit, method="PUT")

            else:
                extension = self.visitExtension.replace("_", "")
                response = self.postResponse(extension, visit)

            # Below captures and writes new Visit Names created when uploading data which excludes them
            if response and name is None:

                # included for universal separately since it could continue on to making specimens, and visit name is critical info for that
                if self.isUniversal:
                    filt = (
                        (self.universalDF["PPID"] == ppid)
                        & (self.universalDF["Event Label"] == eventLabel)
                        & (self.universalDF["Visit Date"] == visitDate)
                    )
                    self.universalDF.loc[filt, "Visit Name"] = response["name"]

                filt = (
                    (self.recordDF["PPID"] == ppid)
                    & (self.recordDF["Event Label"] == eventLabel)
                    & (self.recordDF["Visit Date"] == visitDate)
                )
                self.recordDF.loc[filt, "Visit Name"] = response["name"]
                self.recordDF.to_csv(
                    f"{self.translatorOutputDir}/records_{' '.join(self.currentItem.split('_')[1:])}", index=False
                )

    #  ---------------------------------------------------------------------
    #  still need to account for logging failures, etc.
    def uploadVisits(self):

        inputItems = self.validateInputFiles(self.uploadInputDir, "visits")

        for item, env in inputItems.items():

            self.currentEnv = env
            self.currentItem = item
            self.visitDF = pd.read_csv(item, dtype=str)
            self.preuploadAudit("visits")
            self.recordDF = self.visitDF.copy()

            cols = self.visitDF.columns.values

            for col in cols:
                self.visitDF[col] = self.visitDF[col].apply(self.toUTC, args=[col])

            self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            cpIDs = self.visitDF["CP Short Title"].unique()
            cpIDs = {
                cpShortTitle: int(self.cpDF.loc[(self.cpDF["cpShortTitle"] == cpShortTitle), env])
                for cpShortTitle in cpIDs
            }

            #  getting all visit additional field form info and making a dict as above
            self.formExtensions = {
                cpShortTitle: self.getResponse(self.vafExtension, params={"cpId": cpId})
                for cpShortTitle, cpId in cpIDs.items()
            }

            self.makeVisits()

            shutil.move(item, self.translatorOutputDir)

    #  ---------------------------------------------------------------------

    def recursiveSpecimens(self, parentSpecimen=None):

        #  simple way of avoiding dealing with lists of aliquots for now, since there is unlikely to actually be a case where an aliquot is the parent of anything in the near term
        if isinstance(parentSpecimen, list):
            return

        if parentSpecimen:
            filt = (self.specimenDF["Parent Specimen Label"] == parentSpecimen["label"]) & (
                self.specimenDF["Lineage"].str.lower() != "new"
            )

        # if no parentSpecimen provided, find all parents and start with them
        else:
            filt = (self.specimenDF["Parent Specimen Label"].isnull()) & (
                self.specimenDF["Lineage"].str.lower() == "new"
            )

        if self.specimenDF.loc[filt].empty:

            # NOTE -- leaving out a whole class of derivative/aliquot specimens that have a label but no parent label, since they exist in OpS already (i.e. in the case of pushing updates to them)
            # that is, if there are no parents in the specimenDF, we should check for derivatives/aliquots and attempt to match and update, instead of defaulting to return (see last else statement in func)
            return

        else:

            for ind, data in tqdm(self.specimenDF.loc[filt].iterrows(), desc="Recursive Specimens", unit=" Specimens"):

                #  aliquot label format may be set at system level, so better to allow aliquots with no label to pass this checkpoint
                if pd.notna(data["Specimen Label"]) or data["Lineage"].lower() == "aliquot":

                    specimenLabel = data["Specimen Label"]
                    extension = self.specimenExtension
                    params = {"label": specimenLabel, "exactMatch": True}
                    matchedSpecimen = self.getResponse(extension, params=params)

                    if matchedSpecimen:

                        matchedSpecimen = matchedSpecimen[0]
                        extension += str(matchedSpecimen["id"])

                        if data["Lineage"].lower() != "aliquot":

                            ref = {"Matched": matchedSpecimen}
                            specimen = self.makeSpecimen(data, referenceSpec=ref)

                        else:

                            extension = self.aliquotExtension
                            ref = {"Matched": matchedSpecimen}
                            specimen = self.makeAliquot(data, referenceSpec=ref)

                        response = self.postResponse(extension, specimen, method="PUT")
                        self.recursiveSpecimens(parentSpecimen=response)

                    elif parentSpecimen:

                        if data["Lineage"].lower() != "aliquot":

                            ref = {"Parent": parentSpecimen}
                            specimen = self.makeSpecimen(data, referenceSpec=ref)

                        else:

                            extension = self.aliquotExtension
                            ref = {"Parent": parentSpecimen}
                            specimen = self.makeAliquot(data, referenceSpec=ref)

                        response = self.postResponse(extension, specimen)
                        self.recursiveSpecimens(parentSpecimen=response)

                    else:

                        if data["Lineage"].lower() != "aliquot":
                            specimen = self.makeSpecimen(data)

                        else:

                            extension = self.aliquotExtension
                            specimen = self.makeAliquot(data)

                        response = self.postResponse(extension, specimen)
                        self.recursiveSpecimens(parentSpecimen=response)

                else:

                    # try to match against existing and then update -- if no match, add to log

                    pass  # add to log since these will be derivatives/aliquots that don't have parents

            # Below captures and writes new Specimen Labels created when uploading data which excludes them
            # Not yet tested as of 6/30/2021
            if response and pd.isna(data["Specimen Label"]):

                # included for universal separately since it could continue on to making specimens, and visit name is critical info for that
                if self.isUniversal:
                    filt = (
                        (self.universalDF["Visit Name"] == specimen.visitName)
                        & (self.universalDF["Type"] == specimen.type)
                        & (self.universalDF["Lineage"] == specimen.lineage)
                    )
                    self.universalDF.loc[filt, "Specimen Label"] = response["label"]
                    self.universalDF.loc[filt, "Parent Specimen Label"] = response["parentLabel"]

                filt = (
                    (self.recordDF["Visit Name"] == specimen.visitName)
                    & (self.recordDF["Type"] == specimen.type)
                    & (self.recordDF["Lineage"] == specimen.lineage)
                )
                self.recordDF.loc[filt, "Specimen Label"] = response["label"]
                self.recordDF.loc[filt, "Parent Specimen Label"] = response["parentLabel"]
                self.recordDF.to_csv(
                    f"{self.translatorOutputDir}/records_{' '.join(self.currentItem.split('_')[1:])}", index=False
                )

    #  ---------------------------------------------------------------------

    def uploadSpecimens(self):
        #  TODO -- NEED TO ACCOUNT FOR USE OF SPECIMEN REQUIREMENT CODE (here and in universal, or in both by fitting it into recursiveSpecimens somehow)

        inputItems = self.validateInputFiles(self.uploadInputDir, "specimens")

        for item, env in inputItems.items():

            self.currentEnv = env
            self.currentItem = item
            self.specimenDF = pd.read_csv(item, dtype=str)
            self.preuploadAudit("specimens")
            self.recordDF = self.specimenDF.copy()

            cols = self.specimenDF.columns.values

            for col in cols:
                self.specimenDF[col] = self.specimenDF[col].apply(self.toUTC, args=[col])

            self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            cpIDs = self.specimenDF["CP Short Title"].unique()
            cpIDs = {
                cpShortTitle: int(self.cpDF.loc[(self.cpDF["cpShortTitle"] == cpShortTitle), env])
                for cpShortTitle in cpIDs
            }

            #  getting all specimen additional field form info and making a dict as above
            self.formExtensions = {
                cpShortTitle: self.getResponse(self.safExtension, params={"cpId": cpId})
                for cpShortTitle, cpId in cpIDs.items()
            }

            self.recursiveSpecimens()

            shutil.move(item, self.translatorOutputDir)

    #  ---------------------------------------------------------------------

    def makeSpecimen(self, data, referenceSpec={}):

        formExten = self.formExtensions[data["CP Short Title"]]

        if formExten:
            extensionDetail = self.buildExtensionDetail(formExten, data)

        #  since it's required for specimen class, and attrsMap defaults to an empty dict, go ahead and make an empty Extension instance
        else:
            extensionDetail = Extension()

        lineage = data["Lineage"]
        cols = data.index
        data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}

        specimenClass, specimenType = data.get("Class"), data.get("Type")
        anatomicSite, pathology = data.get("Anatomic Site"), data.get("Pathological Status")
        initialQty, availableQty = data.get("Initial Quantity"), data.get("Available Quantity")
        laterality, collectionStatus = data.get("Laterality"), data.get("Collection Status")
        concentration, label = data.get("Concentration"), data["Specimen Label"]
        comments = data.get("Comments")

        biohazards = [data.get(col) for col in cols if "biohazard" in col.lower() and data.get(col) is not None]

        if self.isUniversal:

            storageLocation = {
                "name": data.get("Container"),
                "positionX": data.get("Row"),
                "positionY": data.get("Column"),
            }

        else:

            storageLocation = {
                "name": data.get("Location#Container"),
                "positionX": data.get("Location#Row"),
                "positionY": data.get("Location#Column"),
            }

        #  dealing with pandas converting mixed int and Nones to floats again... TODO: instead, use .astype() above when sourcing the vals, combined with .notna() to avoid errors cause by failure to cast type
        storageLocation = {key: int(val) for key, val in storageLocation.items() if isinstance(val, float)}

        if referenceSpec.get("Matched"):

            activityStatus, createdOn = data.get("Activity Status"), data.get("Created On")
            barcode = data.get("Barcode")

            specimen = UpdateSpecimen(
                label,
                specimenClass,
                specimenType,
                anatomicSite,
                pathology,
                lineage,
                initialQty,
                availableQty,
                laterality,
                collectionStatus,
                extensionDetail,
                activityStatus,
                createdOn,
                biohazards,
                concentration,
                storageLocation,
                barcode,
                comments,
            )

            specimen.storageType = referenceSpec["Matched"].get("storageType")
            specimen.parentId = referenceSpec["Matched"].get("parentId")
            specimen.visitId = referenceSpec["Matched"].get("visitId")
            specimen.visitName = referenceSpec["Matched"].get("visitName")

            return specimen

        elif referenceSpec.get("Parent"):

            activityStatus, createdOn = data.get("Activity Status"), data.get("Created On")
            barcode = data.get("Barcode")

            specimen = UpdateSpecimen(
                label,
                specimenClass,
                specimenType,
                anatomicSite,
                pathology,
                lineage,
                initialQty,
                availableQty,
                laterality,
                collectionStatus,
                extensionDetail,
                activityStatus,
                createdOn,
                biohazards,
                concentration,
                storageLocation,
                barcode,
                comments,
            )

            specimen.storageType = referenceSpec["Parent"].get("storageType")
            specimen.parentId = referenceSpec["Parent"].get("id")
            specimen.visitId = referenceSpec["Parent"].get("visitId")
            specimen.visitName = referenceSpec["Parent"].get("visitName")

            return specimen

        else:

            visitName = data.get("Visit Name")
            visitId = self.matchVisit(visitName)

            if visitId:

                comments = data.get("Comments")

                collectionEvent = {
                    "user": data.get("Collection Event#User#Email Address"),
                    "time": data.get("Collection Event#Date and Time"),
                    "container": data.get("Collection Event#Container"),
                    "procedure": data.get("Collection Event#Procedure"),
                    "comments": data.get("Collection Event#Comments"),
                }

                receivedEvent = {
                    "user": data.get("Received Event#User#Email Address"),
                    "time": data.get("Received Event#Date and Time"),
                    "receivedQuality": data.get("Received Event#Quality"),
                    "comments": data.get("Received Event#Comments"),
                }

                specimen = Specimen(
                    label,
                    specimenClass,
                    specimenType,
                    anatomicSite,
                    pathology,
                    visitId,
                    lineage,
                    initialQty,
                    availableQty,
                    laterality,
                    collectionStatus,
                    extensionDetail,
                    comments,
                    collectionEvent,
                    receivedEvent,
                    biohazards,
                    concentration,
                    storageLocation,
                )

                return specimen

            else:
                raise ValueError(
                    f"Visits must already exist and be specified in the upload. Failed on {label}. To make visits and specimens at the same time, use the 'Master' template."
                )

    #  ---------------------------------------------------------------------

    def makeAliquot(self, data, referenceSpec={}):

        formExten = self.formExtensions[data["CP Short Title"]]

        if formExten:
            extensionDetail = self.buildExtensionDetail(formExten, data)

        else:
            extensionDetail = Extension()

        cols = data.index
        data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}

        initialQty, availableQty = data.get("Initial Quantity"), data.get("Available Quantity")
        collectionStatus, createdOn = data.get("Collection Status"), data.get("Created On")
        comments, specimenLabel = data.get("Comments"), data.get("Specimen Label")

        aliquot = Aliquot(
            specimenLabel,
            initialQty,
            availableQty,
            collectionStatus,
            createdOn,
            extensionDetail,
            comments,
        )

        if referenceSpec.get("Matched"):

            aliquot.parentId = referenceSpec["Matched"].get("parentId")
            aliquot.visitId = referenceSpec["Matched"].get("visitId")

        elif referenceSpec.get("Parent"):

            aliquot.parentId = referenceSpec["Parent"].get("id")
            aliquot.visitId = referenceSpec["Parent"].get("visitId")

        if data.get("Quantity"):
            aliquot = [aliquot for val in range(data.get("Quantity"))]

        else:
            aliquot = [aliquot]

        return aliquot

    #  ---------------------------------------------------------------------

    def matchArray(self, arrayName):

        params = {"name": arrayName, "exactMatch": True}
        arrayInfo = self.getResponse(self.arrayExtension, params=params)

        if arrayInfo:

            arrayId = arrayInfo[0]["id"]
            return arrayId

        else:
            return None

    #  ---------------------------------------------------------------------

    def populateArray(self, arrayDetails={}):

        extension = self.coreExtension.replace("_", str(arrayDetails["id"]))
        cols = self.coreDF.columns.values
        cores = Cores()

        filt = self.coreDF["Name"] == arrayDetails["name"]

        for ind, data in tqdm(self.coreDF.loc[filt].iterrows(), desc="Core Uploads", unit=" Cores"):

            data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}
            row = data.get("Cores Detail#Row")
            column = data.get("Cores Detail#Column")

            specimen = {
                "specimen": {
                    "label": data.get("Cores Detail#Specimen#Specimen Label"),
                    "cpShortTitle": data.get("Cores Detail#Specimen#CP Short Title"),
                },
                "rowStr": row,
                "columnStr": column,
            }

            cores.cores.append(specimen)

        self.postResponse(extension, cores, method="PUT")

    #  ---------------------------------------------------------------------

    def makeArray(self, forcePending=False):

        cols = self.coreDF.columns.values

        self.arrayDF = self.coreDF.drop_duplicates(subset=["Name"])

        for ind, data in tqdm(self.arrayDF.iterrows(), desc="Array Uploads", unit=" Arrays"):

            extension = self.arrayExtension
            setComplete = False

            data = {col: (data[col] if pd.notna(data[col]) else None) for col in cols}

            name, length = data.get("Name"), data.get("Length (mm)")
            width, thickness = data.get("Width (mm)"), data.get("Thickness (mm)")
            numberOfRows, rowLabelingScheme = data.get("Rows"), data.get("Row Labeling Scheme").upper()
            numberOfColumns, columnLabelingScheme = data.get("Columns"), data.get("Column Labeling Scheme").upper()
            coreDiameter, creationDate = data.get("Core Diameter (mm)"), data.get("Creation Date")
            status, qualityControl = data.get("Status"), data.get("Quality")
            comments = data.get("Comments")

            array = Array(
                name,
                length,
                width,
                thickness,
                numberOfRows,
                rowLabelingScheme,
                numberOfColumns,
                columnLabelingScheme,
                coreDiameter,
                creationDate,
                status,
                qualityControl,
                comments,
            )

            if forcePending and array.status.lower() == "completed":
                setComplete = True
                array.status = "PENDING"

            array.id = self.matchArray(name)

            if array.id:

                extension += str(array.id)
                self.postResponse(extension, array, method="PUT")

            else:

                response = self.postResponse(extension, array)
                array.id = response["id"]

            arrayDetails = {"name": array.name, "id": array.id}
            self.populateArray(arrayDetails=arrayDetails)

            if setComplete:

                array.status = "COMPLETED"
                self.postResponse(extension, array, method="PUT")

    #  ---------------------------------------------------------------------

    def uploadArrays(self, forcePending=False):

        inputItems = self.validateInputFiles(self.uploadInputDir, "arrays")

        for item, env in inputItems.items():

            self.currentEnv = env
            self.coreDF = pd.read_csv(item, dtype=str)

            cols = self.coreDF.columns.values

            for col in cols:
                self.coreDF[col] = self.coreDF[col].apply(self.toUTC, args=[col])

            self.setCPDF()

            self.makeArray(forcePending)

            shutil.move(item, self.translatorOutputDir)

    #  ---------------------------------------------------------------------

    def buildExtensionDetail(self, formExten, data):
        #  TODO: accomodate specimenEvents (these are env-wide; stainingEvent, qualityAssuranceAndControl, etc.) --> https://openspecimendev.winship.emory.edu/rest/ng/forms?formType=specimenEvent

        formId = formExten["formId"]
        formName = formExten["formName"]
        self.setFormDF()

        #  if there are none vals mixed in, we account for their under the hood float type, which forces ints to be represented as floats in the DF too
        formFilt = (self.formDF[f"{self.currentEnv}ShortName"] == formName) & (
            self.formDF[self.currentEnv].astype(int, errors="ignore") == formId
        )
        formName = self.formDF.loc[formFilt, "formName"].item()

        dropList = [val for val in data.index.to_list() if formName not in val]
        cleanedData = data.drop(labels=dropList).copy()
        cleanedData = cleanedData.dropna()

        #  set the field DF and then establish filters
        self.setFieldDF()
        fieldFilt = (self.fieldDF["formName"] == formName) & (self.fieldDF[self.currentEnv] != pd.NA)
        fieldDF = self.fieldDF.loc[fieldFilt, ["fieldName", self.currentEnv]]

        attrsDict = {}

        for ind, data in cleanedData.iteritems():

            if len(ind.split("#")) < 4:

                filt = fieldDF["fieldName"] == ind.split("#")[1]
                keyVal = fieldDF.loc[filt, self.currentEnv].item()
                attrsDict[keyVal] = data

            elif len(ind.split("#")) == 4:

                filt = fieldDF["fieldName"] == ind.split("#")[1]
                parentVal = fieldDF.loc[filt, self.currentEnv].item()

                if attrsDict.get(parentVal) is None:
                    attrsDict[parentVal] = {}

                filt = fieldDF["fieldName"] == ind.split("#")[3]
                keyVal = fieldDF.loc[filt, self.currentEnv].item()

                instanceKey = ind.split("#")[2]

                if attrsDict[parentVal].get(instanceKey) is None:
                    attrsDict[parentVal][instanceKey] = {keyVal: data}

                elif attrsDict[parentVal][instanceKey].get(keyVal) is None:
                    attrsDict[parentVal][instanceKey][keyVal] = data

        for key, val in attrsDict.items():

            if isinstance(val, dict):
                attrsDict[key] = [subFields for subFields in attrsDict[key].values()]

        if attrsDict:

            extensionDetail = Extension(attrsMap=attrsDict)
            return extensionDetail

        else:

            extensionDetail = Extension()
            return extensionDetail

    #  ---------------------------------------------------------------------
    #  a generic function for pulling files specific to a given function based on keyword and returning relevant info
    def validateInputFiles(self, location, keyword):

        inputItems = [item for item in os.listdir(location) if item.split("_")[0].lower() == keyword]
        validatedItems = {}

        for item in inputItems:

            if item.split("_")[1].lower() in self.envs.keys():
                env = item.split("_")[1].lower()

            elif not item.endswith(".csv"):
                raise TypeError("Input files must be of type .CSV")

            else:
                raise KeyError(
                    "Upload file names must be in the following format: [Category]_[Environment Key]_[Additional Misc. Content].CSV"
                )

            validatedItems[location + item] = env

        return validatedItems

    #  ---------------------------------------------------------------------

    def validateAndAuditUpload(self, keyword, matchPPID=False):
        self.validatePreupload(keyword, matchPPID=matchPPID)
        self.preuploadAudit(keyword)

    #  ---------------------------------------------------------------------
    #  Only ensures that the data being validated will go into OpS -- does not audit the data itself
    def validatePreupload(self, keyword, matchPPID=False):

        fileName = " ".join(self.currentItem.split("_")[1:])

        if keyword == "participants":

            if self.isUniversal:
                df = self.universalDF
            else:
                df = self.participantDF

            participantCritical = ["CP Short Title", "Registration Date"]  # required for upload

            if matchPPID:
                participantCritical += ["PPID"]

            criticalFilt = df[participantCritical].isna().any(axis=1)
            criticalErrors = df[criticalFilt].copy()

            if criticalErrors.size:
                criticalErrors.to_csv(f"./output/participant_records_with_critical_errors_{fileName}", index=False)

                errorFilt = df.index.isin(criticalErrors.index)
                df = df.loc[~errorFilt].copy()

        elif keyword == "visits":

            if self.isUniversal:
                df = self.universalDF
            else:
                df = self.visitDF

            visitCritical = ["CP Short Title", "PPID"]  # required for upload

            criticalFilt = df[visitCritical].isna().any(axis=1)
            criticalErrors = df[criticalFilt].copy()

            if criticalErrors.size:
                criticalErrors.to_csv(f"./output/visit_records_with_critical_errors_{fileName}", index=False)

                errorFilt = df.index.isin(criticalErrors.index)
                df = df.loc[~errorFilt].copy()

        elif keyword == "specimens":

            if self.isUniversal:
                df = self.universalDF
            else:
                df = self.specimenDF

            specimenCritical = [
                "CP Short Title",
                "Visit Name",
                "Type",
            ]  # required for upload

            # looks different than other cases because have to account for instances where Type == "not specified" and the Class field is empty, as it is required in that case
            # also need to account for cases where specimen label is missing and lineage is aliquot, because that is permissible
            # and when parent specimen label is missing but lineage is new, since that is also permissible
            criticalFilt = (
                df[specimenCritical].isna().any(axis=1)
                | ((df["Type"].str.lower() == "not specified") & (df["Class"].isna()))
                | ((df["Specimen Label"].isna()) & (df["Lineage"] != "Aliquot"))
                | ((df["Parent Specimen Label"].isna()) & (df["Lineage"] != "New"))
            )
            criticalErrors = df[criticalFilt].copy()

            if criticalErrors.size:
                criticalErrors.to_csv(f"./output/specimen_records_with_critical_errors_{fileName}", index=False)

                errorFilt = df.index.isin(criticalErrors.index)
                df = df.loc[~errorFilt].copy()

    #  ---------------------------------------------------------------------
    #  Only audits data, does not necessarily validate that it will go in to OpS
    def preuploadAudit(self, keyword):

        fileName = " ".join(self.currentItem.split("_")[1:])

        if keyword == "participants":

            # logic of below is as follows:
            # screen broadly for duplicates in order to narrow to unique cases -- this should be a list of unique participant records that is ideal for upload
            # however, if we know that each participant record should be unique, we can then reason that if the first, last, dob, etc. match inside this supposedly unique set of participants
            # then we have an issue where data elsewhere in the record varied and made the "duplicate" record appear as a unique case, since it didn't match perfectly when looking for duplicates across all columns

            # with universal, one challenge is that everything will almost certainly appear as a duplicate at least once, since it includes visits/specimens, each of which will also have participant info
            # meaning only this second screen is super relevant for universal, and the first duplicate detection should not be written into a file if isUniversal

            # one potential issue with this approach is the ordering of multi-instance columns
            # such as those for Race, Ethnicity, etc., where one participant may have multiple, but the order of them could vary between records, thus giving false positive

            participantSub = [
                "CP Short Title",
                "PPID",
                "Registration Date",
                "Registration Site",
                "External Subject ID",
                "First Name",
                "Last Name",
                "Middle Name",
                "Date Of Birth",
                "Death Date",
                "Gender",
                "Vital Status",
                "SSN",
                "eMPI",
            ]

            if self.isUniversal:
                df = self.universalDF
                participantSub = [
                    col
                    for col in df.columns.values
                    if col in participantSub
                    or "PMI" in col
                    or "Race" in col
                    or "Ethnicity" in col
                    or "Participant" in col
                ]

            else:
                df = self.participantDF
                participantSub = df.columns.values

            self.participantDF = df.drop_duplicates(subset=participantSub)

            participantSub = ["CP Short Title", "First Name", "Last Name", "Date Of Birth"]
            duplicateFilt = self.participantDF.duplicated(subset=participantSub, keep=False)
            duplicatedRecords = self.participantDF.loc[duplicateFilt].copy()

            if duplicatedRecords.size:
                duplicatedRecords.to_csv(f"./output/conflicting_participants_in_original_{fileName}", index=False)

                self.participantDF = self.participantDF.loc[~duplicateFilt]

                # below keeps first instance of the duplicate, so may not be ideal, as we can't be certain that the first is the correct one...
                # the above should retain only records which do not have any duplicates
                # self.participantDF = self.participantDF.drop_duplicates(subset=participantSub)

        elif keyword == "visits":

            visitSub = [
                "CP Short Title",
                "PPID",
                "Event Label",
                "Visit Name",
                "Visit Date",
                "Collection Site",
                "Visit Status",
                "Clinical Status",
                "Cohort",
                "Path. Number",
                "Visit Comments",
            ]

            if self.isUniversal:
                df = self.universalDF
                visitSub = [col for col in df.columns.values if col in visitSub or "Visit" in col or "Clinical" in col]

            else:
                df = self.visitDF
                visitSub = df.columns.values

            self.visitDF = df.drop_duplicates(subset=visitSub)

            visitSub = ["CP Short Title", "PPID", "Event Label", "Visit Date"]
            visitSub += ["Visit Name"] if self.isUniversal else ["Name"]

            duplicateFilt = self.visitDF.duplicated(subset=visitSub, keep=False)
            duplicatedRecords = self.visitDF.loc[duplicateFilt].copy()

            if duplicatedRecords.size:
                duplicatedRecords.to_csv(f"./output/conflicting_visits_in_original_{fileName}", index=False)

                self.visitDF = self.visitDF.loc[~duplicateFilt]

                # below keeps first instance of the duplicate, so may not be ideal, as we can't be certain that the first is the correct one...
                # the above should retain only records which do not have any duplicates
                # self.visitDF = self.visitDF.drop_duplicates(subset=visitSub)

        elif keyword == "specimens":

            # technically this is as easy as filtering for duplicate specimen labels, but that misses two things
            # first thing is the case where there are no specimen labels (i.e. are OpS generated)
            # second thing is that it doesn't narrow the search to cases where the duplicates conflict
            # technically this implementation isn't great for point 1 either, since it uses specimen label in the second filter

            specimenSub = [
                "CP Short Title",
                "Visit Name",
                "Specimen Requirement Code",
                "Specimen Label",
                "Barcode",
                "Class",
                "Type",
                "Lineage",
                "Parent Specimen Label",
                "Anatomic Site",
                "Laterality",
                "Pathological Status",
                "Quantity",
                "Concentration",
                "Freeze/Thaw Cycles",
                "Created On",
                "Comments",
                "Collection Status",
                "Container",
                "Row",
                "Column",
                "Position",
                "Collection Date",
                "Collection Proceedure",
                "Collection Container",
                "Collector",
                "Received Date",
                "Received Quality",
                "Receiver",
            ]

            if self.isUniversal:
                df = self.universalDF
                specimenSub = [
                    col for col in df.columns.values if col in specimenSub or "External" in col or "Specimen" in col
                ]

            else:
                df = self.specimenDF
                specimenSub = df.columns.values

            self.specimenDF = df.drop_duplicates(subset=specimenSub)

            specimenSub = ["CP Short Title", "Visit Name", "Specimen Label"]
            duplicateFilt = self.specimenDF.duplicated(subset=specimenSub, keep=False)
            duplicatedRecords = self.specimenDF.loc[duplicateFilt].copy()

            if duplicatedRecords.size:
                duplicatedRecords.to_csv(f"./output/conflicting_specimens_in_original_{fileName}", index=False)

                self.specimenDF = self.specimenDF.loc[~duplicateFilt]

                # below keeps first instance of the duplicate, so may not be ideal, as we can't be certain that the first is the correct one...
                # the above should retain only records which do not have any duplicates
                # self.specimenDF = self.specimenDF.drop_duplicates(subset=specimenSub)

    #  ---------------------------------------------------------------------
    # PARTICIPANTS ONLY AS OF 06/25/2021 -- probably need a separate universal audit that has a unified criticalCols list, puts out a unified duplicateRecords file, etc.
    def auditData(self, keyword, wantRandSample=False):

        inputItems = self.validateInputFiles(self.auditInputDir, keyword.lower())

        for item, env in tqdm(inputItems.items(), desc="Files Processed", unit=" Files"):

            fileName = " ".join(item.split("_")[1:])

            self.currentEnv = env
            self.auditDF = pd.read_csv(item, dtype=str)
            cols = self.auditDF.columns.values

            self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            cpIDs = self.auditDF["CP Short Title"].unique()
            cpIDs = {
                cpShortTitle: self.cpDF.loc[(self.cpDF["cpShortTitle"] == cpShortTitle), env]
                .astype(int, errors="ignore")
                .item()
                for cpShortTitle in cpIDs
            }

            if keyword.lower() == "participants" or keyword.lower() == "universal":

                comparedDF = pd.DataFrame(columns=cols)

                criticalCols = ["CP Short Title", "PPID", "Last Name", "Date Of Birth"]
                criticalErrors = self.auditDF[self.auditDF[criticalCols].isna().any(axis=1)].copy()
                criticalErrors.to_csv(f"./output/records_with_critical_errors_{fileName}", index=False)

                errorFilt = self.auditDF.index.isin(criticalErrors.index)
                self.participantDF = self.auditDF.loc[~errorFilt].copy()

                participantSub = [
                    "CP Short Title",
                    "PPID",
                    "First Name",
                    "Last Name",
                    "Date Of Birth",
                    "Registration Date",
                ]
                self.participantDF = self.participantDF.drop_duplicates(subset=participantSub)

                # keep = false marks all duplicates as true for filtering, otherwise options are mark only first or last instance of duplicate
                duplicatedRecords = self.auditDF.loc[self.auditDF.duplicated(subset=participantSub, keep=False)].copy()
                duplicatedRecords.to_csv(f"./output/duplicate_records_in_original_{fileName}", index=False)

                # done using these, so might as well clear up some memory, etc.
                del duplicatedRecords, criticalErrors

                dateList = ["Registration Date", "Date Of Birth", "Death Date"]

                for col in dateList:

                    self.participantDF[col] = self.participantDF[col].apply(self.padDates)

                numRecords = len(self.participantDF.index)

                if wantRandSample and numRecords > 30:

                    checkInds = self.generateRandomSample(numRecords)
                    filt = self.participantDF.index.isin(checkInds)
                    self.participantAuditDF = self.participantDF.iloc[filt].copy()

                else:
                    self.participantAuditDF = self.participantDF.copy()

                for ind, data in tqdm(self.participantAuditDF.iterrows(), desc="Records Audited", unit=" Records"):

                    # puts data in alphabetical order by row label
                    data.sort_index(inplace=True)

                    # putting pmis in alphabetical order by site name so that there are not false positives when doing 1:1 comparison of data vs. OpS records
                    pmiCols = [col for col in data.index if "site name" in col.lower() and pd.notna(data[col])]
                    newPMIs = {data[col]: data[f"PMI#{col.split('#')[1]}#MRN"] for col in pmiCols}
                    sortedPMIs = sorted(newPMIs.items(), key=(lambda x: x[0]))
                    sortedPMIs = {pmi[0]: pmi[1] for pmi in sortedPMIs}

                    # this may leave a duplicate pmi entry if there had been a column skipped during data entry (i.e. if pmis were entered in #1, #2, and #4 instead of #1, #2, #3)
                    for i, vals in enumerate(sortedPMIs.items()):
                        data[f"PMI#{i+1}#Site Name"] = vals[0]
                        data[f"PMI#{i+1}#MRN"] = vals[1]

                    matchData = {
                        "cpId": cpIDs[data["CP Short Title"]],
                        "name": data["Last Name"],
                        "ppid": data["PPID"],
                        "birthDate": data["Date Of Birth"],
                        "maxResults": 1,
                        "exactMatch": True,
                    }

                    matchExtension = self.registerParticipantExtension + "list"
                    response = self.postResponse(matchExtension, matchData)

                    if response:

                        matchExtension = self.registerParticipantExtension + str(response[0]["id"])
                        participantData = self.getResponse(matchExtension)

                        compareDict = {}

                        # could do something like the following
                        # compareDict = {
                        #     "CP Short Title": "cpShortTitle",
                        #     "PPID": "ppid",
                        #     "Registration Site": "site",
                        #     "External Subject ID": "externalSubjectId",
                        #     "Activity Status": "activityStatus",
                        #     "First Name": "firstName",
                        #     "Last Name": "lastName",
                        #     "Middle Name": "middleName",
                        #     "Gender": "gender",
                        #     "Vital Status": "vitalStatus",
                        #     "eMPI": "empi"
                        # }

                        # compareDict = {key, participantData.get(val) for key, val in compareDict.items()}

                        # compareDict["SSN"] = participantData["participant"].get("")
                        # compareDict["Email Address"] = participantData["participant"].get("")
                        # compareDict["Reason"] = participantData.get("")

                        compareDict["CP Short Title"] = participantData.get("cpShortTitle")
                        compareDict["PPID"] = participantData.get("ppid")
                        compareDict["Registration Date"] = (
                            self.fromUTC(participantData.get("registrationDate"))
                            if participantData.get("registrationDate") > 0
                            else self.fillerDate  # this is generally used in the case where a date is required but missing and indicates that it is likely fabricated to enable upload to proceed
                            if participantData.get("registrationDate") == -2208970800000
                            else f"Could not convert: {participantData.get('registrationDate')}"
                        )
                        compareDict["Registration Site"] = participantData.get("site")
                        compareDict["External Subject ID"] = participantData.get("externalSubjectId")
                        compareDict["Activity Status"] = participantData.get("activityStatus")
                        compareDict["First Name"] = participantData["participant"].get("firstName")
                        compareDict["Last Name"] = participantData["participant"].get("lastName")
                        compareDict["Middle Name"] = participantData["participant"].get("middleName")
                        compareDict["Gender"] = participantData["participant"].get("gender")
                        compareDict["Vital Status"] = participantData["participant"].get("vitalStatus")
                        compareDict["eMPI"] = participantData["participant"].get("empi")

                        dob = participantData["participant"].get("birthDateStr")
                        dod = participantData["participant"].get("deathDateStr")

                        if dob:
                            dob = dob.split("-")
                            dob = "/".join([dob[1], dob[2], dob[0]])

                        if dod:
                            dod = dod.split("-")
                            dod = "/".join([dod[1], dod[2], dod[0]])

                        compareDict["Date Of Birth"] = dob
                        compareDict["Death Date"] = dod

                        races = participantData["participant"].get("races")
                        ethnicities = participantData["participant"].get("ethnicities")

                        if races:
                            for num, race in enumerate(races):
                                compareDict[f"Race#{num+1}"] = race

                        if ethnicities:
                            for num, ethnicity in enumerate(ethnicities):
                                compareDict[f"Ethnicity#{num+1}"] = ethnicity

                        pmis = participantData["participant"].get("pmis")

                        if pmis:
                            # putting pmis in order by site name so that there are not false positives when doing 1:1 comparison of data vs. OpS records
                            newPMIs = {pmi["siteName"]: pmi["mrn"] for pmi in pmis}
                            sortedPMIs = sorted(newPMIs.items(), key=(lambda x: x[0]))
                            sortedPMIs = {item[0]: item[1] for item in sortedPMIs}

                            for num, pmi in enumerate(sortedPMIs.items()):
                                compareDict[f"PMI#{num+1}#Site Name"] = pmi[0]
                                compareDict[f"PMI#{num+1}#MRN"] = pmi[1]

                        if participantData["participant"].get("extensionDetail") is not None:
                            pafForm = participantData["participant"]["extensionDetail"]["formCaption"]
                            pafVals = participantData["participant"]["extensionDetail"]["attrs"]
                            pafDict = {}

                            for field in pafVals:

                                if "SF" not in field["name"]:
                                    pafDict[f"{pafForm}#{field['caption']}"] = field["value"]

                                else:

                                    for num, val in enumerate(field["value"]):

                                        for subField in val:
                                            key = f"{pafForm}#{field['caption']}#{num+1}#{subField['caption']}"
                                            pafDict[key] = subField["value"]

                            compareDict.update(pafDict)

                        for col in cols:
                            if col not in compareDict.keys():
                                compareDict[col] = None

                        compareSeries = pd.Series(compareDict)
                        compareSeries.sort_index(inplace=True)

                        # below in case form fields changed between upload and audit, in which case there may be be additional columns in compareSeries
                        extras = [item for item in compareSeries.index.values if item not in data.index.values]
                        compareSeries.drop(index=extras, inplace=True)

                        compared = data.compare(compareSeries).T
                        compared.insert(0, "PPID", compareDict["PPID"])
                        comparedDF = comparedDF.append(compared)

                    else:
                        comparedDF.append(data)
                        filt = comparedDF["PPID"] == data["PPID"]
                        comparedDF.loc[filt, "Identifier"] = "Record for this participant not found in OpS"

                    # added this for cases where there are many records and one issue therein means the entire script breaks and needs to run again -- at least this keeps partial records
                    comparedDF.to_csv(f"./output/audited_{fileName}", index=False)

                # side effect of below is that places where a record has something OpS doesn't have (or vice versa) results in only a single entry and is not clear if the entry is from OpS or from the original data
                subset = [col for col in comparedDF.columns if col != "PPID"]
                comparedDF.dropna(subset=subset, how="all", inplace=True)
                comparedDF.to_csv(f"./output/audited_{fileName}", index=False)

    #  ---------------------------------------------------------------------

    def generateRandomSample(self, numRecords):

        if numRecords <= 100:
            checkNum = int(numRecords * 0.33)

        elif numRecords > 100:
            checkNum = int(numRecords * 0.1)

        checkInds = random.sample(range(numRecords), checkNum)
        return checkInds

    #  ---------------------------------------------------------------------

    def setCPDF(self, envs=None):

        if os.path.exists(self.cpOutPath):
            self.cpDF = pd.read_csv(self.cpOutPath)

        else:
            self.cpDF = self.syncWorkflowList(envs, wantDF=True)

    #  ---------------------------------------------------------------------
    #  generates a dataframe of all CPs and their internal reference codes
    def syncWorkflowList(self, envs=None, wantDF=False):

        if os.path.exists(self.cpOutPath):
            cpDF = pd.read_csv(self.cpOutPath)

        else:

            columns = ["cpShortTitle", "cpTitle"] + [env for env in self.authTokens.keys()]
            cpDF = pd.DataFrame(columns=columns)

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            for reqVals in self.workflowListDetails:

                initialDict = self.getResponse(reqVals["listExtension"], reqVals["params"])
                shortTitleKey = reqVals["shortTitleKey"]

                for cp in initialDict:

                    if cp[shortTitleKey] in cpDF["cpShortTitle"].values:

                        filt = cpDF["cpShortTitle"] == cp[shortTitleKey]
                        cpDF.loc[filt, env] = cp["id"]

                    else:

                        if shortTitleKey == "name":
                            cpTitle = "N/A -- Group Workflow"

                        else:
                            cpTitle = cp["title"]

                        data = {
                            "cpShortTitle": cp[shortTitleKey],
                            "cpTitle": cpTitle,
                            env: cp["id"],
                        }
                        cpDF = cpDF.append(data, ignore_index=True, sort=False)

        cpDF.to_csv(self.cpOutPath, index=False)

        if wantDF:
            return cpDF

    #  ---------------------------------------------------------------------
    #  pulls down the workflows associated with the CPs in the dataframe generated by syncWorkflowList
    def syncWorkflows(self, envs=None):

        self.setCPDF()

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            for cp, shortTitle, title in zip(self.cpDF[env], self.cpDF["cpShortTitle"], self.cpDF["cpTitle"]):

                if pd.notna(cp):

                    if title != "N/A -- Group Workflow":

                        extension = self.cpWorkflowExtension.replace("_", f"{int(cp)}")

                        workflow = self.getResponse(extension)

                        if len(workflow["workflows"]) != 0:

                            shortTitle = shortTitle.replace("/", "_")
                            writable = [section for section in workflow["workflows"].values()]

                            with open(f"./workflows/{env}/{shortTitle}.json", "w") as f:
                                json.dump(writable, f, indent=2)
                    else:

                        extension = self.groupWorkflowExtension.replace("_", f"{int(cp)}")

                        workflow = self.getResponse(extension)

                        with open(f"./workflows/{env}/{shortTitle} Group Workflows.json", "w") as f:
                            json.dump(workflow, f, indent=2)

    #  ---------------------------------------------------------------------

    def setFormDF(self, envs=None):

        if os.path.exists(self.formOutPath):
            self.formDF = pd.read_csv(self.formOutPath)

        else:
            self.formDF = self.syncFormList(envs, wantDF=True)

    #  ---------------------------------------------------------------------
    #  generates a dataframe of all forms, their internal reference codes, and when they were last modified/updated
    def syncFormList(self, envs=None, wantDF=False):

        if os.path.exists(self.formOutPath):
            formDF = pd.read_csv(self.formOutPath)

        else:
            columns = ["formName"]

            for env in self.authTokens.keys():
                columns += [f"{env}ShortName", env, f"{env}UpdateRecord"]

            formDF = pd.DataFrame(columns=columns)

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env
            initialDict = self.getResponse(self.formListExtension)

            for form in initialDict:

                if "modificationTime" in form.keys():
                    updateRecord = form["modificationTime"]

                else:
                    updateRecord = form["creationTime"]

                if form["caption"] in formDF["formName"].values:

                    filt = formDF["formName"] == form["caption"]
                    formDF.loc[filt, env] = form["formId"]
                    formDF.loc[filt, f"{env}ShortName"] = form["name"]
                    formDF.loc[filt, f"{env}UpdateRecord"] = updateRecord

                else:

                    data = {
                        "formName": form["caption"],
                        f"{env}ShortName": form["name"],
                        env: form["formId"],
                        f"{env}UpdateRecord": updateRecord,
                    }
                    formDF = formDF.append(data, ignore_index=True, sort=False)

        formDF.to_csv(self.formOutPath, index=False)

        if wantDF:
            return formDF

    #  ---------------------------------------------------------------------

    def setFieldDF(self, envs=None):

        if os.path.exists(self.fieldOutPath):
            self.fieldDF = pd.read_csv(self.fieldOutPath)

        else:
            self.fieldDF = self.syncFieldList(envs, wantDF=True)

    #  ---------------------------------------------------------------------
    #  generates a dataframe of all fields and subfields, as well as their internal reference codes, associated with the forms in the dataframe generated by syncFormList
    def syncFieldList(self, envs=None, wantDF=False):

        self.setFormDF()

        universalColumns = ["formName", "isSubForm", "fieldName", "isSubField"] + [
            env for env in self.authTokens.keys()
        ]
        universalDF = pd.DataFrame(columns=universalColumns)

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            for formName, val in zip(self.formDF["formName"], self.formDF[env]):

                #  needed because nan in pandas is a float, so it's not sufficient to just convert to int -- throws error when trying to convert float nan
                if pd.notna(val):

                    extension = f"{self.formListExtension}/{int(val)}/definition"
                    fieldList = self.getResponse(extension)

                    fieldList = fieldList["rows"]
                    #  nested list comprehension pulls rows from fieldList, then the items for that row, and unifies all into a single list
                    #  can be understood as: for row in fieldList, for item in row, item
                    #  or item for item in row for row in fieldList
                    fieldList = [item for row in fieldList for item in row]

                    for fieldItem in fieldList:

                        isSubForm = fieldItem["type"] == "subForm"

                        filt = (universalDF["formName"] == formName) & (
                            universalDF["fieldName"] == fieldItem["caption"]
                        )

                        if not universalDF.loc[filt, env].empty:
                            universalDF.loc[filt, env] = fieldItem["name"]

                        else:

                            data = {
                                "formName": formName,
                                "isSubForm": isSubForm,
                                "fieldName": fieldItem["caption"],
                                "isSubField": False,
                                env: fieldItem["name"],
                            }
                            universalDF = universalDF.append(data, ignore_index=True, sort=False)

                        if isSubForm:
                            subFieldList = fieldItem["rows"]
                            subFieldList = [item for row in subFieldList for item in row]

                            for subFieldItem in subFieldList:

                                filt = (universalDF["formName"] == formName) & (
                                    universalDF["fieldName"] == subFieldItem["caption"]
                                )

                                if not universalDF.loc[filt, env].empty:

                                    universalDF.loc[filt, env] = subFieldItem["name"]

                                else:

                                    data = {
                                        "formName": formName,
                                        "isSubForm": isSubForm,
                                        "fieldName": subFieldItem["caption"],
                                        "isSubField": True,
                                        env: subFieldItem["name"],
                                    }
                                    universalDF = universalDF.append(data, ignore_index=True, sort=False)

        universalDF.to_csv(self.fieldOutPath, index=False)

        if wantDF:
            return universalDF

    #  ---------------------------------------------------------------------

    def setDropdownDF(self, envs=None):

        if os.path.exists(self.dropdownOutpath):
            self.dropdownDF = pd.read_csv(self.dropdownOutpath)

        else:
            self.dropdownDF = self.syncDropdownList(envs, wantDF=True)

    #  ---------------------------------------------------------------------
    #  generates a dataframe of all dropdowns and their env specific names
    def syncDropdownList(self, envs=None, wantDF=False):

        if os.path.exists(self.dropdownOutpath):
            ddDF = pd.read_csv(self.dropdownOutpath)

        else:

            columns = ["dropdownName"] + [env for env in self.authTokens.keys()]
            ddDF = pd.DataFrame(columns=columns)

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            initialDict = self.getResponse(self.dropdownExtension)

            for dropdown in initialDict:

                #  why even record the presence of a dropdown with no values in it?
                if dropdown["pvCount"] is not None:

                    if (
                        dropdown["name"] in ddDF["dropdownName"].values
                        and dropdown["attribute"] not in ddDF[env].values
                    ):

                        filt = ddDF["dropdownName"] == dropdown["name"]
                        ddDF.loc[filt, env] = dropdown["attribute"]

                    elif dropdown["name"] not in ddDF["dropdownName"].values:

                        data = {
                            "dropdownName": dropdown["name"],
                            env: dropdown["attribute"],
                        }
                        ddDF = ddDF.append(data, ignore_index=True, sort=False)

        ddDF.to_csv(self.dropdownOutpath, index=False)

        if wantDF:
            return ddDF

    #  ---------------------------------------------------------------------
    #  pulls all the dropdown values associated with the dropdown lists in the dataframe generated by syncDropdownList
    def syncDropdownPVs(self, envs=None):

        self.setDropdownDF()

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            for ddList in self.dropdownDF[env].values:

                pvOutpath = f"./dropdowns/{ddList}.csv"
                self.pvExtensionDetails["params"]["attribute"] = ddList

                if os.path.exists(pvOutpath):
                    pvDF = pd.read_csv(pvOutpath)

                else:

                    columns = ["permissibleValue"] + [env for env in self.authTokens.keys()]
                    pvDF = pd.DataFrame(columns=columns)

                pvDF.set_index("permissibleValue", inplace=True)
                initialDict = self.getResponse(
                    self.pvExtensionDetails["pvExtension"],
                    self.pvExtensionDetails["params"],
                )

                if initialDict:

                    for val in initialDict:

                        val = val["value"]

                        if not pvDF.index.isin([val]).any():

                            pvDF.index.append(pd.Index([val]))
                            pvDF.loc[val, env] = True

                        elif pvDF.loc[val, env] is not True:
                            pvDF.loc[val, env] = True

                pvDF.fillna(False, inplace=True)
                pvDF.to_csv(pvOutpath)

    #  ---------------------------------------------------------------------

    def updateAll(self, envs=None):

        self.updateWorkflows(envs)
        self.updateForms(envs)

    #  ---------------------------------------------------------------------
    #  Updates workflow list and workflow records (i.e. workflow jsons), including removing any no longer in use
    def updateWorkflows(self, envs=None):

        #  Note that OpenSpecimen only provides values for when Forms have been updated, so there is no way to know if workflows have changed
        #  Thus, this function can only pull workflows for CPs it does not have a record of, and remove those that are no longer in use
        #  It CANNOT pull the most recent workflows, since it has no easy/direct way of knowing if something has changed since last time
        #  Hypothetically, could directly compare stored vs. current, but that would likely be time and resource intensive
        #
        #  In the future, syncWorkflowList may be updated to track the last time a given workflow were synced down by a user and this function
        #  updated to check against that date, which, if outside a specified range, would trigger this function to pull a new copy just in case

        if not os.path.exists(self.cpOutPath):
            raise Exception("universalCPs.csv not found. There must be an existing record to update.")

        else:
            self.cpDF = pd.read_csv(self.cpOutPath)

        if envs is None:
            envs = self.authTokens.keys()

        elif not isinstance(envs, list):
            envs = [envs.lower()]

        for env in envs:

            self.currentEnv = env

            #  Allows sync of group and cp level workflows with the same function -- see settings for more details
            for reqVals in self.workflowListDetails:

                initialDict = self.getResponse(reqVals["listExtension"], reqVals["params"])
                shortTitleKey = reqVals["shortTitleKey"]
                shortTitles = [val[shortTitleKey] for val in initialDict]

                for cp in initialDict:

                    cpID = cp["id"]

                    if cp[shortTitleKey] in self.cpDF["cpShortTitle"].values:

                        filt = self.cpDF["cpShortTitle"] == cp[shortTitleKey]

                        if pd.isna(self.cpDF.loc[filt, env].item()) or self.cpDF.loc[filt, env].item() != cpID:
                            self.cpDF.loc[filt, env] = cpID

                            if shortTitleKey != "name":

                                extension = self.cpWorkflowExtension.replace("_", str(cpID))
                                workflow = self.getResponse(extension)

                                #  if 0, no need to keep a record
                                if len(workflow["workflows"]) != 0:

                                    #  removing / because it can interfere with file pathing on save
                                    shortTitle = cp[shortTitleKey].replace("/", "_")
                                    writable = [section for section in workflow["workflows"].values()]

                                    with open(f"./workflows/{env}/{shortTitle}.json", "w") as f:
                                        json.dump(writable, f, indent=2)

                            else:

                                extension = self.groupWorkflowExtension.replace("_", str(cpID))
                                workflow = self.getResponse(extension)

                                with open(
                                    f"./workflows/{env}/{cp[shortTitleKey]} Group Workflows.json",
                                    "w",
                                ) as f:
                                    json.dump(workflow, f, indent=2)

                    else:

                        if shortTitleKey == "name":

                            cpTitle = "N/A -- Group Workflow"
                            extension = self.groupWorkflowExtension.replace("_", str(cpID))
                            workflow = self.getResponse(extension)

                            with open(
                                f"./workflows/{env}/{cp[shortTitleKey]} Group Workflows.json",
                                "w",
                            ) as f:
                                json.dump(workflow, f, indent=2)

                        else:

                            cpTitle = cp["title"]
                            extension = self.cpWorkflowExtension.replace("_", str(cpID))
                            workflow = self.getResponse(extension)

                            #  if 0, no need to keep a record
                            if len(workflow["workflows"]) != 0:

                                #  removing / because it can interfere with file pathing on save
                                shortTitle = cp[shortTitleKey].replace("/", "_")
                                writable = [section for section in workflow["workflows"].values()]

                                with open(f"./workflows/{env}/{shortTitle}.json", "w") as f:
                                    json.dump(writable, f, indent=2)

                        data = {
                            "cpShortTitle": cp[shortTitleKey],
                            "cpTitle": cpTitle,
                            env: cpID,
                        }
                        self.cpDF = self.cpDF.append(data, ignore_index=True, sort=False)

                for cpShortTitle, cpTitle in zip(self.cpDF["cpShortTitle"], self.cpDF["cpTitle"]):

                    filt = self.cpDF["cpShortTitle"] == cpShortTitle

                    #  Important -- don't want to delete a normal CP workflow because you're looking at group workflows
                    if shortTitleKey != "name" and cpTitle != "N/A -- Group Workflow":

                        #  If the short title from the DF is not in the list, and there is a non-None val for the code
                        if cpShortTitle not in shortTitles and pd.notna(self.cpDF.loc[filt, env].item()):

                            self.cpDF.loc[filt, env] = None
                            workflowLocation = f"./workflows/{env}/{cpShortTitle}.json"

                            if os.path.exists(workflowLocation):
                                os.remove(workflowLocation)

                    elif shortTitleKey == "name" and cpTitle == "N/A -- Group Workflow":

                        if cpShortTitle not in shortTitles and pd.notna(self.cpDF.loc[filt, env].item()):

                            self.cpDF.loc[filt, env] = None
                            workflowLocation = f"./workflows/{env}/{cpShortTitle}.json"

                            if os.path.exists(workflowLocation):
                                os.remove(workflowLocation)

        #  Removing all rows that have None vals for all Envs (i.e. don't exist anywhere)
        self.cpDF.dropna(how="all", subset=[env for env in self.envs.keys()], inplace=True)
        self.cpDF.to_csv(self.cpOutPath, index=False)

    #  ---------------------------------------------------------------------
    #  updates forms and fields, including removing any that are no longer in use
    def updateForms(self, envs=None):

        if not os.path.exists(self.formOutPath):
            raise Exception("universalForms.csv not found. There must be an existing record to update.")

        else:

            if not os.path.exists(self.fieldOutPath):
                raise Exception("universalFields.csv not found. There must be an existing record to update.")

            else:
                self.fieldDF = pd.read_csv(self.fieldOutPath)

            self.formDF = pd.read_csv(self.formOutPath)

            if envs is None:
                envs = self.authTokens.keys()

            elif not isinstance(envs, list):
                envs = [envs.lower()]

            for env in envs:

                self.currentEnv = env

                initialDict = self.getResponse(self.formListExtension)
                forms = [form["caption"] for form in initialDict]
                formIDs = []

                for form in initialDict:

                    if form["caption"] in self.formDF["formName"].values and "modificationTime" in form.keys():

                        updateRecord = form["modificationTime"]
                        filt = self.formDF["formName"] == form["caption"]

                        if self.formDF.loc[filt, f"{env}UpdateRecord"].item() != updateRecord:

                            formIDs.append(form["formId"])
                            self.formDF.loc[filt, f"{env}UpdateRecord"] = updateRecord

                    elif form["caption"] not in self.formDF["formName"].values:

                        #  could be the case that the form name isn't there because it was altered, rather than being a new form, so we check with formId, which is static
                        if form["formId"] in self.formDF[env].values:

                            #  this may not be the best way of handling this kind of case, since it loses the linkage of this form across envs, though it does encourage consistent naming and updates across envs
                            noneList = [env, f"{env}ShortName", f"{env}UpdateRecord"]
                            filt = self.formDF[env] == form["formId"]

                            for val in noneList:

                                self.formDF.loc[filt, val] = None

                        if "modificationTime" in form.keys():
                            updateRecord = form["modificationTime"]

                        else:
                            updateRecord = form["creationTime"]

                        formIDs.append(form["formId"])
                        data = {
                            "formName": form["caption"],
                            f"{env}ShortName": form["name"],
                            env: form["formId"],
                            f"{env}UpdateRecord": updateRecord,
                        }
                        self.formDF = self.formDF.append(data, ignore_index=True, sort=False)

                for formID in formIDs:

                    extension = f"{self.formListExtension}/{formID}/definition"
                    fieldList = self.getResponse(extension)
                    fieldList = fieldList["rows"]
                    #  nested list comprehension pulls rows from fieldList, then the items for that row, and unifies all into a single list
                    fieldList = [item for row in fieldList for item in row]

                    filt = self.formDF[env] == formID

                    #  needed because it seems this will start indexing with the series/column name...
                    if not self.formDF.loc[filt, "formName"].empty:

                        #  have to get form name because not included in form json
                        formName = self.formDF.loc[filt, "formName"].item()
                        allFields = [fieldItem["caption"] for fieldItem in fieldList]

                        for fieldItem in fieldList:

                            isSubForm = fieldItem["type"] == "subForm"

                            #  confirm both are present, but need to check that these are also in the same row
                            if (formName in self.fieldDF["formName"].values) and (
                                fieldItem["caption"] in self.fieldDF["fieldName"].values
                            ):

                                #  so we get all locations where that field appears, and the formName associated with those locations
                                fieldInstances = self.fieldDF.loc[
                                    self.fieldDF.fieldName == fieldItem["caption"],
                                    "formName",
                                ]

                                #  turn them into a dict where the formName is the key and the index of that row is the value
                                fieldInstances = dict(zip(fieldInstances.values, fieldInstances.index))

                                #  if the formName of interest is in the dict, we are good to go -- recall we already filtered by fieldName to create fieldInstances
                                if formName in fieldInstances.keys():

                                    #  so now we just grab the index of the field by referencing the specific form we want, since there can be multiple forms with the same field
                                    ind = fieldInstances[formName]

                                    if self.fieldDF.loc[ind, env] != fieldItem["name"]:
                                        self.fieldDF.loc[ind, env] = fieldItem["name"]

                                #  otherwise, make a new entry for that form and field -- this occurs when the form and field exist but the form of interest doesn't actually have that field
                                else:

                                    data = {
                                        "formName": formName,
                                        "isSubForm": isSubForm,
                                        "fieldName": fieldItem["caption"],
                                        "isSubField": False,
                                        env: fieldItem["name"],
                                    }
                                    self.fieldDF = self.fieldDF.append(data, ignore_index=True, sort=False)

                            else:

                                data = {
                                    "formName": formName,
                                    "isSubForm": isSubForm,
                                    "fieldName": fieldItem["caption"],
                                    "isSubField": False,
                                    env: fieldItem["name"],
                                }
                                self.fieldDF = self.fieldDF.append(data, ignore_index=True, sort=False)

                            if isSubForm:

                                subFieldList = fieldItem["rows"]
                                subFieldList = [item for row in subFieldList for item in row]
                                allFields += [subFieldItem["caption"] for subFieldItem in subFieldList]

                                for subFieldItem in subFieldList:

                                    if (formName in self.fieldDF["formName"].values) and (
                                        subFieldItem["caption"] in self.fieldDF["fieldName"].values
                                    ):
                                        filt = (self.fieldDF["formName"] == formName) & (
                                            self.fieldDF["fieldName"] == subFieldItem["caption"]
                                        )

                                        if not self.fieldDF.loc[filt, env].empty:
                                            self.fieldDF.loc[filt, env] = subFieldItem["name"]

                                    else:

                                        data = {
                                            "formName": formName,
                                            "isSubForm": isSubForm,
                                            "fieldName": subFieldItem["caption"],
                                            "isSubField": True,
                                            env: subFieldItem["name"],
                                        }
                                        self.fieldDF = self.fieldDF.append(data, ignore_index=True, sort=False)

                        filt = self.fieldDF["formName"] == formName

                        for item in self.fieldDF.loc[filt, "fieldName"].values:

                            if item not in allFields:

                                updateFilt = (self.fieldDF["formName"] == formName) & (
                                    self.fieldDF["fieldName"] == item
                                )
                                self.fieldDF.loc[updateFilt, env] = None

                for name in self.formDF["formName"]:

                    filt = self.formDF["formName"] == name

                    #  If the form name from the DF is not in the list of current forms, and there is a non-None val for the code
                    if name not in forms and pd.notna(self.formDF.loc[filt, env].any()):

                        self.formDF.loc[filt, f"{env}ShortName"] = None
                        self.formDF.loc[filt, env] = None

                        #  Even though the condition below only looks at env/envUpdateRecord, setting all None to avoid confusion if/when reviewed by a human
                        self.formDF.loc[filt, f"{env}UpdateRecord"] = None

                #  removes fields if that whole form was deleted -- need to remove individual fields if they are no longer in the form
                for name in self.fieldDF["formName"].unique():

                    filt = self.fieldDF["formName"] == name

                    if name not in forms:
                        self.fieldDF.loc[filt, env] = None

            self.fieldDF.dropna(how="all", subset=[env for env in self.envs.keys()], inplace=True)
            self.fieldDF.to_csv(self.fieldOutPath, index=False)

            self.formDF.dropna(
                how="all",
                subset=[f"{env}UpdateRecord" for env in self.envs.keys()],
                inplace=True,
            )
            self.formDF.to_csv(self.formOutPath, index=False)

    #  ---------------------------------------------------------------------

    def runQuery(self, env, cpID, AQL):

        self.currentEnv = env

        data = {
            "cpId": cpID,
            "aql": AQL,
            # "caseSensitive": "true",
            # "drivingForm": "Participant",
            # "outputColumnExprs": "false",
            # "outputIsoDateTime": "true",
            # "runType": "Data",
            # "wideRowMode": "DEEP",
        }

        response = self.postResponse(self.queryExtension, data)
        return response

    #  ---------------------------------------------------------------------
