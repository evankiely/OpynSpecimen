import os
import json  # may be required for workflow functions - investigate removing and replacing with HTTPX reply.json() or something
import time  # required for metric logging
import httpx
import pstats  # required for profiling - can be omitted in release if desired
import shutil
import asyncio
import cProfile  # required for profiling - can be omitted in release if desired

import pandas as pd
import jsonpickle as jp

from generic import *
from tqdm import tqdm
from datetime import datetime
from settings import Settings

# from concurrent.futures import ThreadPoolExecutor  #  enable if/when OpS can handle async requests without crashing -- remember to uncomment the requisite code below as well

# TODO: Look for places where apply is used to enact things that are simple string methods, and replace with .str.[method]


class Integration(Settings):
    def __init__(self):

        super().__init__()
        self.currentEnv = None
        self.isUniversal = False
        self.authTokens = self.getTokens()

    #  ---------------------------------------------------------------------

    def profileFunc(self, func: str) -> None:
        """Uses cProfile to introspect the passed function and discover inefficiencies"""

        profile = cProfile.Profile()
        profile.runctx(func, globals(), locals())
        stats = pstats.Stats(profile)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.dump_stats(
            filename=f"./updated_async_{func.split('.')[1].strip('()')}_profiled.prof"
        )  # then, in python interpreter, call "snakeviz [file/path]"

    #  ---------------------------------------------------------------------
    #  NOTE Integrations and syncing functions start here
    #  ---------------------------------------------------------------------

    def renewTokens(self) -> None:  #  probably not an especially relevant or useful function -- just use getTokens...
        """Renews tokens for all OpS envs specified in Settings by invoking the getTokens function"""

        self.authTokens = self.getTokens()

    #  ---------------------------------------------------------------------

    def getTokens(self):
        """Asynchronously fetches tokens for all OpS envs given in Settings"""

        async def tokenLogic():

            urls = {
                env: (
                    self.baseURL.replace("_", env) + self.authExtension
                    if env != "prod"
                    else self.baseURL.replace("_", "") + self.authExtension
                )
                for env in self.envs.keys()
            }

            async with httpx.AsyncClient() as client:

                tasks = [client.post(url, json=self.envs[env]) for env, url in urls.items()]
                replies = await asyncio.gather(*tasks)
                authTokens = {env: reply.json()["token"] for env, reply in zip(self.envs.keys(), replies)}
                return authTokens

        return asyncio.run(tokenLogic())

    #  ---------------------------------------------------------------------

    def genericGetRequest(self, env, extension, params=None):
        """Makes a Get request and returns the response JSON or resulting error message"""

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token}
        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)
        url = f"{base}{extension}"

        with httpx.Client(headers=headers, timeout=20) as client:

            if params:
                reply = client.get(url, params=params)

            else:
                reply = client.get(url)

        reply = [reply.json()[0]["code"], reply.json()[0]["message"]] if reply.is_error else reply.json()

        return reply

    #  ---------------------------------------------------------------------

    def getFormExtension(self, extension, params):
        """Gets the extension used to reference a particular "Additional Fields" form associated with the current CP of interest"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token}
        base = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        )

        url = f"{base}{extension}"

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.get(url, params=params)

        if reply.text:
            reply = [reply.json()[0]["code"], reply.json()[0]["message"]] if reply.is_error else reply.json()

        else:
            print(f"Form specified in params ({extension}) is not attached to the specified CP ({params})")
            reply = None

        return reply

    #  ---------------------------------------------------------------------
    #  TODO: consider refactor of the below -- using iteritems is bad form
    def buildExtensionDetail(self, formExten, data):
        """Builds up the data associated with the "Additional Fields" form of the current record"""

        formId = formExten["formId"]
        formName = formExten["formName"]
        formDF = self.setFormDF()

        #  if there are none vals mixed in, we account for their under the hood float type, which forces ints to be represented as floats in the DF too
        formFilt = (formDF[f"{self.currentEnv}ShortName"] == formName) & (
            formDF[self.currentEnv].astype(int, errors="ignore") == formId
        )
        formName = formDF.loc[formFilt, "formName"].item()

        dropList = [val for val in data.index.to_list() if formName not in val]
        cleanedData = data.drop(labels=dropList).copy()
        cleanedData = cleanedData.dropna()

        #  set the field DF and then establish filters
        fieldDF = self.setFieldDF()
        fieldFilt = (fieldDF["formName"] == formName) & (fieldDF[self.currentEnv] != pd.NA)
        fieldDF = fieldDF.loc[fieldFilt, ["fieldName", self.currentEnv]]

        attrsDict = {}

        for ind, data in cleanedData.iteritems():

            splitInd = ind.split("#")

            # for general fields
            if len(splitInd) < 4 and not splitInd[-1].isdigit():

                filt = fieldDF["fieldName"] == ind.split("#")[1]
                keyVal = fieldDF.loc[filt, self.currentEnv].item()
                attrsDict[keyVal] = data

            # for multi-select dropdowns
            elif len(splitInd) == 3 and splitInd[-1].isdigit():

                filt = fieldDF["fieldName"] == ind.split("#")[1]
                keyVal = fieldDF.loc[filt, self.currentEnv].item()

                if attrsDict.get(keyVal):
                    attrsDict[keyVal].append(data)
                else:
                    attrsDict[keyVal] = [data]

            # for subform fields
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

    def syncDropdowns(self):
        """Creates a csv of all dropdowns and their permissible values for each env given in Settings"""

        for env in self.envs.keys():

            (ddList, maxCount) = self.getDropdownsAsList(env)
            dataDict = {dropdown: self.getDropdownVals(env, dropdown) for dropdown in ddList}

            for key, val in dataDict.items():

                if len(val) < maxCount:
                    noneList = [None] * (maxCount - len(val))
                    val += noneList
                    dataDict[key] = val

            dropdownDF = pd.DataFrame.from_dict(data=dataDict, dtype=str)
            dropdownDF.to_csv(self.dropdownOutpath.replace("_", f"{env}_all_dropdown_values"), index=False)

    #  ---------------------------------------------------------------------

    def getDropdownsAsList(self, env):
        """Gets a list of dropdowns available in the given OpS env"""

        initialDict = self.genericGetRequest(env, self.dropdownExtension)
        ddList = [dropdown["attribute"] for dropdown in initialDict if dropdown["pvCount"] is not None]
        countList = [dropdown["pvCount"] for dropdown in initialDict if dropdown["pvCount"] is not None]
        countList.sort()
        maxCount = countList[-1]

        return (ddList, maxCount)

    #  ---------------------------------------------------------------------

    def getDropdownVals(self, env, dropdown):
        """Gets a list of permissible values for a dropdown in the given OpS env"""

        self.pvExtensionDetails["params"]["attribute"] = dropdown

        initialDict = self.genericGetRequest(
            env, self.pvExtensionDetails["pvExtension"], self.pvExtensionDetails["params"]
        )
        valList = [val["value"] for val in initialDict]
        return valList

    #  ---------------------------------------------------------------------

    def setCPDF(self, refresh=False):
        """Creates a DF of all CPs across OpS envs specified in Settings"""

        # NOTE: no need to check if cpOutPath exists already, as this is covered during instantiation of the Settings object (settings.buildEnv)

        if refresh:
            self.cpDF = self.syncWorkflowList(wantDF=True)

        elif not hasattr(self, "cpDF"):
            self.cpDF = pd.read_csv(self.cpOutPath, dtype=str)

        return self.cpDF.copy()

    #  ---------------------------------------------------------------------

    def syncAll(self):
        """Calls all sync functions in order to ensure the data from OpS stored locally is up to date"""

        self.syncWorkflowList()
        self.syncWorkflows()
        self.syncFormList()
        self.syncFieldList()
        self.syncDropdowns()

    #  ---------------------------------------------------------------------

    def syncWorkflowList(self, wantDF=False):
        """Generates a dataframe of all CPs and their internal reference codes"""

        cpDF = pd.read_csv(self.cpOutPath)

        for env in self.authTokens.keys():

            for reqVals in self.workflowListDetails:

                initialDict = self.genericGetRequest(env, reqVals["listExtension"], reqVals["params"])
                shortTitleKey = reqVals["shortTitleKey"]

                for cp in initialDict:

                    if cp[shortTitleKey] in cpDF["cpShortTitle"].values:

                        filt = cpDF["cpShortTitle"] == cp[shortTitleKey]
                        cpDF.loc[filt, env] = cp["id"]

                    else:

                        if shortTitleKey == "name":
                            cpTitle = "Group Workflow"

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

    def syncWorkflows(self):
        """Pulls down the workflow JSON associated with the CPs in the dataframe generated by syncWorkflowList"""

        for env in self.authTokens.keys():
            base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)

            cpDF = self.setCPDF()
            filt = cpDF[env].notna()

            workflowFilt = filt & (cpDF["cpTitle"] != "Group Workflow")
            workflowDF = cpDF[workflowFilt].copy()

            groupWorkflowFilt = filt & (cpDF["cpTitle"] == "Group Workflow")
            groupWorkflowDF = cpDF[groupWorkflowFilt].copy()

            # handling workflows first
            workflowDF["Url"] = (
                workflowDF[env]
                .astype(str)
                .map((lambda x: f"{base}{self.cpWorkflowExtension.replace('_', x.split('.')[0])}"))
            )

            workflowDF = self.chunkDF(workflowDF, chunkSize=self.lookUpChunkSize)
            workflowDF = pd.concat([self.getWorkflows(env, df) for df in workflowDF])

            filt = workflowDF.apply(
                (lambda x: (not isinstance(x["Workflow"], dict) or len(x["Workflow"]["workflows"]) == 0)),
                axis=1,
            )
            workflowDF.drop(workflowDF.loc[filt, env].index, inplace=True)

            workflowDF["Workflow"] = workflowDF["Workflow"].map(
                (lambda x: [section for section in x["workflows"].values()])
            )

            workflowDF["cpShortTitle"] = workflowDF["cpShortTitle"].map((lambda x: x.replace("/", "_")))
            workflowDF.apply((lambda x: self.writeWorkflow(env, x["cpShortTitle"], x["Workflow"])), axis=1)

            # and groupWorkflows second
            groupWorkflowDF["Url"] = (
                groupWorkflowDF[env]
                .astype(str)
                .map((lambda x: f"{base}{self.groupWorkflowExtension.replace('_', x.split('.')[0])}"))
            )

            groupWorkflowDF = self.chunkDF(groupWorkflowDF, chunkSize=self.lookUpChunkSize)
            groupWorkflowDF = pd.concat([self.getWorkflows(env, df) for df in groupWorkflowDF])

            filt = groupWorkflowDF.apply(
                (lambda x: (not isinstance(x["Workflow"], list) or len(x["Workflow"]) == 0)),
                axis=1,
            )

            groupWorkflowDF.drop(groupWorkflowDF.loc[filt, env].index, inplace=True)

            groupWorkflowDF["cpShortTitle"] = groupWorkflowDF["cpShortTitle"].map((lambda x: x.replace("/", "_")))
            groupWorkflowDF.apply(
                (lambda x: self.writeWorkflow(env, x["cpShortTitle"], x["Workflow"], isGroup=True)), axis=1
            )

    #  ---------------------------------------------------------------------

    def getWorkflows(self, env, data):
        """Asynchronously fetches workflow JSON for the CPs associated with a given env in the cpDF"""

        async def getWorkflowsLogic(env, data):
            token = self.authTokens[env]
            headers = {"X-OS-API-TOKEN": token}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [client.get(data.loc[ind, "Url"]) for ind in data.index]
                replies = await asyncio.gather(*tasks)

            replies = [
                (
                    [reply.json()[0]["code"], reply.json()[0]["message"]]
                    if (reply.is_error and "json" in reply.headers.get("content-type"))
                    else None
                    if (reply.is_error and "json" not in reply.headers.get("content-type"))
                    else reply.json()
                )
                for reply in replies
            ]

            data["Workflow"] = replies

            return data

        return asyncio.run(getWorkflowsLogic(env, data))

    #  ---------------------------------------------------------------------

    def writeWorkflow(self, env, shortTitle, workflow, isGroup=False):
        """Writes workflow JSON to a file"""

        if isGroup:
            with open(f"./workflows/{env}/{shortTitle} Group Workflows.json", "w") as f:
                json.dump(workflow, f, indent=2)

        else:
            with open(f"./workflows/{env}/{shortTitle}.json", "w") as f:
                json.dump(workflow, f, indent=2)

    #  ---------------------------------------------------------------------

    def setFormDF(self, refresh=False):
        """Creates a DF of all forms across OpS envs specified in Settings"""

        # NOTE: no need to check if formOutPath exists already, as this is covered during instantiation of the Settings object (settings.buildEnv)

        if refresh:
            self.formDF = self.syncFormList(wantDF=True)

        elif not hasattr(self, "formDF"):
            self.formDF = pd.read_csv(self.formOutPath)

        return self.formDF.copy()

    #  ---------------------------------------------------------------------

    def syncFormList(self, wantDF=False):
        """Generates a dataframe of all forms, their internal reference codes, and when they were last modified/updated"""

        formDF = pd.read_csv(self.formOutPath)

        for env in self.authTokens.keys():

            self.currentEnv = env
            initialDict = self.genericGetRequest(env, self.formListExtension)

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

    def setFieldDF(self, refresh=False):
        """Creates a DF of all fields across OpS envs specified in Settings"""

        # NOTE: no need to check if fieldOutPath exists already, as this is covered during instantiation of the Settings object (settings.buildEnv)

        if refresh:
            self.fieldDF = self.syncFieldList(wantDF=True)

        elif not hasattr(self, "fieldDF"):
            self.fieldDF = pd.read_csv(self.fieldOutPath)

        return self.fieldDF.copy()

    #  ---------------------------------------------------------------------

    def syncFieldList(self, wantDF=False):
        """Generates a dataframe of all fields and subfields, as well as their internal reference codes, associated with the forms in the dataframe generated by syncFormList"""

        formDF = self.setFormDF()

        universalDF = pd.read_csv(self.fieldOutPath)

        for env in self.authTokens.keys():

            self.currentEnv = env

            for formName, val in zip(formDF["formName"], formDF[env]):

                #  needed because nan in pandas is a float, so it's not sufficient to just convert to int -- throws error when trying to convert float nan
                if pd.notna(val):

                    extension = f"{self.formListExtension}/{int(val)}/definition"
                    fieldList = self.genericGetRequest(env, extension)

                    if isinstance(fieldList, list) or fieldList is None:
                        filt = (formDF["formName"] == formName) & (formDF[env] == val)
                        formDF.drop(formDF.loc[filt, env].index, inplace=True)

                    else:
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
                                universalDF.loc[filt, f"{env}UDN"] = fieldItem["udn"]

                            else:

                                data = {
                                    "formName": formName,
                                    "isSubForm": isSubForm,
                                    "fieldName": fieldItem["caption"],
                                    "isSubField": False,
                                    env: fieldItem["name"],
                                    f"{env}UDN": fieldItem["udn"],
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
                                        universalDF.loc[filt, f"{env}UDN"] = subFieldItem["udn"]

                                    else:

                                        data = {
                                            "formName": formName,
                                            "isSubForm": isSubForm,
                                            "fieldName": subFieldItem["caption"],
                                            "isSubField": True,
                                            env: subFieldItem["name"],
                                            f"{env}UDN": subFieldItem["udn"],
                                            f"{env}SubFormUDN": fieldItem["udn"],
                                            f"{env}SubFormName": fieldItem["caption"],
                                        }
                                        universalDF = universalDF.append(data, ignore_index=True, sort=False)

        universalDF.to_csv(self.fieldOutPath, index=False)

        if wantDF:
            return universalDF

    #  ---------------------------------------------------------------------

    def updateAll(self, envs=None):
        """Updates workflows with newly created CPs and forms based on their revision date"""

        self.updateWorkflows(envs)
        self.updateForms(envs)

    #  ---------------------------------------------------------------------

    def updateWorkflows(self):
        """Updates workflow list and JSONs across envs given in Settings, including removing any no longer in use"""

        #  Note that OpenSpecimen only provides values for when *Forms* have been updated, so there is no way to know if workflows have changed
        #  Thus, this function can only pull workflows for CPs it does not have a record of, and remove those that are no longer in use
        #  It CANNOT pull the most recent workflows, since it has no easy/direct way of knowing if something has changed since last time
        #  Hypothetically, could directly compare stored vs. current, but that would likely be time and resource intensive
        #
        #  In the future, syncWorkflowList may be updated to track the last time a given workflow were synced down by a user and this function
        #  updated to check against that date, which, if outside a specified range, would trigger this function to pull a new copy just in case

        cpDF = self.setCPDF()

        for env in self.authTokens.keys():

            self.currentEnv = env

            #  Allows sync of group and cp level workflows with the same function -- see settings for more details
            for reqVals in self.workflowListDetails:

                initialDict = self.genericGetRequest(env, reqVals["listExtension"], reqVals["params"])
                shortTitleKey = reqVals["shortTitleKey"]
                shortTitles = [val[shortTitleKey] for val in initialDict]

                for cp in initialDict:

                    cpID = cp["id"]

                    if cp[shortTitleKey] in cpDF["cpShortTitle"].values:

                        filt = cpDF["cpShortTitle"] == cp[shortTitleKey]

                        if pd.isna(cpDF.loc[filt, env].item()) or cpDF.loc[filt, env].item() != cpID:
                            cpDF.loc[filt, env] = cpID

                            if shortTitleKey != "name":

                                extension = self.cpWorkflowExtension.replace("_", str(cpID))
                                workflow = self.genericGetRequest(env, extension)

                                #  if 0, no need to keep a record
                                if len(workflow["workflows"]) != 0:

                                    #  removing / because it can interfere with file pathing on save
                                    shortTitle = cp[shortTitleKey].replace("/", "_")
                                    writable = [section for section in workflow["workflows"].values()]

                                    with open(f"./workflows/{env}/{shortTitle}.json", "w") as f:
                                        json.dump(writable, f, indent=2)

                            else:

                                extension = self.groupWorkflowExtension.replace("_", str(cpID))
                                workflow = self.genericGetRequest(env, extension)

                                with open(
                                    f"./workflows/{env}/{cp[shortTitleKey]} Group Workflows.json",
                                    "w",
                                ) as f:
                                    json.dump(workflow, f, indent=2)

                    else:

                        if shortTitleKey == "name":

                            cpTitle = "N/A -- Group Workflow"
                            extension = self.groupWorkflowExtension.replace("_", str(cpID))
                            workflow = self.genericGetRequest(env, extension)

                            with open(
                                f"./workflows/{env}/{cp[shortTitleKey]} Group Workflows.json",
                                "w",
                            ) as f:
                                json.dump(workflow, f, indent=2)

                        else:

                            cpTitle = cp["title"]
                            extension = self.cpWorkflowExtension.replace("_", str(cpID))
                            workflow = self.genericGetRequest(env, extension)

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
                        cpDF = cpDF.append(data, ignore_index=True, sort=False)

                for cpShortTitle, cpTitle in zip(cpDF["cpShortTitle"], cpDF["cpTitle"]):

                    filt = cpDF["cpShortTitle"] == cpShortTitle

                    #  Important -- don't want to delete a normal CP workflow because you're looking at group workflows
                    if shortTitleKey != "name" and cpTitle != "N/A -- Group Workflow":

                        #  If the short title from the DF is not in the list, and there is a non-None val for the code
                        if cpShortTitle not in shortTitles and pd.notna(cpDF.loc[filt, env].item()):

                            cpDF.loc[filt, env] = None
                            workflowLocation = f"./workflows/{env}/{cpShortTitle}.json"

                            if os.path.exists(workflowLocation):
                                os.remove(workflowLocation)

                    elif shortTitleKey == "name" and cpTitle == "N/A -- Group Workflow":

                        if cpShortTitle not in shortTitles and pd.notna(cpDF.loc[filt, env].item()):

                            cpDF.loc[filt, env] = None
                            workflowLocation = f"./workflows/{env}/{cpShortTitle}.json"

                            if os.path.exists(workflowLocation):
                                os.remove(workflowLocation)

        #  Removing all rows that have None vals for all Envs (i.e. don't exist anywhere)
        cpDF.dropna(how="all", subset=[env for env in self.envs.keys()], inplace=True)
        cpDF.to_csv(self.cpOutPath, index=False)

    #  ---------------------------------------------------------------------

    def updateForms(self):
        """Updates forms and fields, including removing any that are no longer in use"""

        fieldDF = self.setFieldDF()
        formDF = self.setFormDF()

        for env in self.authTokens.keys():

            self.currentEnv = env

            initialDict = self.genericGetRequest(env, self.formListExtension)
            forms = [form["caption"] for form in initialDict]
            formIDs = []

            for form in initialDict:

                if form["caption"] in formDF["formName"].values and "modificationTime" in form.keys():

                    updateRecord = form["modificationTime"]
                    filt = formDF["formName"] == form["caption"]

                    if formDF.loc[filt, f"{env}UpdateRecord"].item() != updateRecord:

                        formIDs.append(form["formId"])
                        formDF.loc[filt, f"{env}UpdateRecord"] = updateRecord

                elif form["caption"] not in formDF["formName"].values:

                    #  could be the case that the form name isn't there because it was altered, rather than being a new form, so we check with formId, which is static
                    if form["formId"] in formDF[env].values:

                        #  this may not be the best way of handling this kind of case, since it loses the linkage of this form across envs, though it does encourage consistent naming and updates across envs
                        noneList = [env, f"{env}ShortName", f"{env}UpdateRecord"]
                        filt = formDF[env] == form["formId"]

                        for val in noneList:

                            formDF.loc[filt, val] = None

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
                    formDF = formDF.append(data, ignore_index=True, sort=False)

            for formID in formIDs:

                extension = f"{self.formListExtension}/{formID}/definition"
                fieldList = self.genericGetRequest(env, extension)
                fieldList = fieldList["rows"]
                #  nested list comprehension pulls rows from fieldList, then the items for that row, and unifies all into a single list
                fieldList = [item for row in fieldList for item in row]

                filt = formDF[env] == formID

                #  needed because it seems this will start indexing with the series/column name...
                if not formDF.loc[filt, "formName"].empty:

                    #  have to get form name because not included in form json
                    formName = formDF.loc[filt, "formName"].item()
                    allFields = [fieldItem["caption"] for fieldItem in fieldList]

                    for fieldItem in fieldList:

                        isSubForm = fieldItem["type"] == "subForm"

                        #  confirm both are present, but need to check that these are also in the same row
                        if (formName in fieldDF["formName"].values) and (
                            fieldItem["caption"] in fieldDF["fieldName"].values
                        ):

                            #  so we get all locations where that field appears, and the formName associated with those locations
                            fieldInstances = fieldDF.loc[
                                fieldDF.fieldName == fieldItem["caption"],
                                "formName",
                            ]

                            #  turn them into a dict where the formName is the key and the index of that row is the value
                            fieldInstances = dict(zip(fieldInstances.values, fieldInstances.index))

                            #  if the formName of interest is in the dict, we are good to go -- recall we already filtered by fieldName to create fieldInstances
                            if formName in fieldInstances.keys():

                                #  so now we just grab the index of the field by referencing the specific form we want, since there can be multiple forms with the same field
                                ind = fieldInstances[formName]

                                if fieldDF.loc[ind, env] != fieldItem["name"]:
                                    fieldDF.loc[ind, env] = fieldItem["name"]

                            #  otherwise, make a new entry for that form and field -- this occurs when the form and field exist but the form of interest doesn't actually have that field
                            else:

                                data = {
                                    "formName": formName,
                                    "isSubForm": isSubForm,
                                    "fieldName": fieldItem["caption"],
                                    "isSubField": False,
                                    env: fieldItem["name"],
                                }
                                fieldDF = fieldDF.append(data, ignore_index=True, sort=False)

                        else:

                            data = {
                                "formName": formName,
                                "isSubForm": isSubForm,
                                "fieldName": fieldItem["caption"],
                                "isSubField": False,
                                env: fieldItem["name"],
                            }
                            fieldDF = fieldDF.append(data, ignore_index=True, sort=False)

                        if isSubForm:

                            subFieldList = fieldItem["rows"]
                            subFieldList = [item for row in subFieldList for item in row]
                            allFields += [subFieldItem["caption"] for subFieldItem in subFieldList]

                            for subFieldItem in subFieldList:

                                if (formName in fieldDF["formName"].values) and (
                                    subFieldItem["caption"] in fieldDF["fieldName"].values
                                ):
                                    filt = (fieldDF["formName"] == formName) & (
                                        fieldDF["fieldName"] == subFieldItem["caption"]
                                    )

                                    if not fieldDF.loc[filt, env].empty:
                                        fieldDF.loc[filt, env] = subFieldItem["name"]

                                else:

                                    data = {
                                        "formName": formName,
                                        "isSubForm": isSubForm,
                                        "fieldName": subFieldItem["caption"],
                                        "isSubField": True,
                                        env: subFieldItem["name"],
                                    }
                                    fieldDF = fieldDF.append(data, ignore_index=True, sort=False)

                    filt = fieldDF["formName"] == formName

                    for item in fieldDF.loc[filt, "fieldName"].values:

                        if item not in allFields:

                            updateFilt = (fieldDF["formName"] == formName) & (fieldDF["fieldName"] == item)
                            fieldDF.loc[updateFilt, env] = None

            for name in formDF["formName"]:

                filt = formDF["formName"] == name

                #  If the form name from the DF is not in the list of current forms, and there is a non-None val for the code
                if name not in forms and pd.notna(formDF.loc[filt, env].any()):

                    formDF.loc[filt, f"{env}ShortName"] = None
                    formDF.loc[filt, env] = None

                    #  Even though the condition below only looks at env/envUpdateRecord, setting all None to avoid confusion if/when reviewed by a human
                    formDF.loc[filt, f"{env}UpdateRecord"] = None

            #  removes fields if that whole form was deleted -- need to remove individual fields if they are no longer in the form
            for name in fieldDF["formName"].unique():

                filt = fieldDF["formName"] == name

                if name not in forms:
                    fieldDF.loc[filt, env] = None

        fieldDF.dropna(how="all", subset=[env for env in self.envs.keys()], inplace=True)
        fieldDF.to_csv(self.fieldOutPath, index=False)

        formDF.dropna(
            how="all",
            subset=[f"{env}UpdateRecord" for env in self.envs.keys()],
            inplace=True,
        )
        formDF.to_csv(self.formOutPath, index=False)

    #  ---------------------------------------------------------------------
    #  NOTE Misc. helper functions start here
    #  ---------------------------------------------------------------------

    def fromUTC(self, utcVal):
        """Converts a time from UTC to mm/dd/yyyy"""

        if utcVal is None:
            return None

        elif isinstance(utcVal, str):
            utcVal = int(utcVal)

        try:
            data = datetime.utcfromtimestamp(utcVal / 1000).strftime("%m/%d/%Y")
            return data

        except:
            return "01/01/1900"

    #  ---------------------------------------------------------------------

    def chunkDF(self, df, chunkSize=None):
        """Returns a chunked dataframe"""

        dfUpperBound = len(df.index)
        chunkSize = self.asyncChunkSize if chunkSize is None else chunkSize
        chunked = [
            (df.iloc[n : n + chunkSize].copy() if n + chunkSize <= dfUpperBound else df.iloc[n:dfUpperBound].copy())
            for n in range(0, dfUpperBound, chunkSize)
        ]

        return chunked

    #  ---------------------------------------------------------------------

    def runQuery(self, env, cpID, AQL, wantWideRows=False, asDF=False):
        """Runs a query via OpS and returns the response JSON, otherwise returns error message from the server. Use -1 for cpID if querying across multiple CPs specified in AQL"""

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)

        url = f"{base}{self.queryExtension}"

        data = {
            "cpId": cpID,
            "aql": AQL,
            # "caseSensitive": "true",
            # "drivingForm": "Participant",
            # "outputColumnExprs": "false",
            # "outputIsoDateTime": "true",
            # "runType": "Data",
        }

        # Rather than one row per case of a value, add as many columns as necessary to capture all cases (i.e. instead of one row per MRN Site + MRN Value, one row with multiple columns)
        if wantWideRows:
            data["wideRowMode"] = "DEEP"

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.post(url, data=jp.encode(data, unpicklable=False))

        reply = ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]]) if reply.is_error else reply.json()

        if asDF:
            columns = reply["columnLabels"]
            data = reply["rows"]
            reply = pd.DataFrame(data, columns=columns)

            dateCols = [col for col in reply.columns if "date" in col.lower()]
            for col in dateCols:
                reply[col] = reply[col].str.replace("-", "/")

        return reply

    #  ---------------------------------------------------------------------
    #  NOTE Generic/GUI uploads and related functions start here
    #  ---------------------------------------------------------------------

    def cpDefJSONUpload(self):
        """Creates new CP by uploading CP Def JSON"""

        inputItems = [
            (self.inputDir + item) for item in os.listdir(self.inputDir) if item.split("_")[0].lower() == "cpdef"
        ]

        for item in inputItems:

            if not item.endswith(".json"):
                raise TypeError("Input files must be of type .JSON")

            if item.split("_")[1].lower() in self.envs.keys():
                env = item.split("_")[1].lower()

            else:
                raise KeyError(
                    "Upload file names must be in the following format: [Category]_[Environment Key]_[Additional Misc. Content].JSON"
                )

            token = self.authTokens[env]
            headers = {"X-OS-API-TOKEN": token}
            base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)
            extension = self.cpDefExtension
            url = f"{base}{extension}"

            files = [("file", (".json", open(item, "rb"), "application/octet-stream"))]

            with httpx.Client(headers=headers, timeout=20) as client:
                reply = client.post(url, files=files)

            print(reply.text)

            shutil.move(item, self.outputDir)

    #  ---------------------------------------------------------------------

    def pathReportUpload(self, env):

        data = [report.split(".")[0] for report in os.listdir(self.pathReportInputDir)]
        df = pd.DataFrame(columns=["Path. Number"], data=data)

        df = self.matchVisitForPathReport(df, env)
        df["File Path"] = df["Path. Number"].map((lambda x: f"{self.pathReportInputDir}{x}.pdf"))
        df["Upload Results"] = df.apply((lambda x: self.pushPathReports(x, env)), axis=1)

        df.rename(columns={"Visit Original CP": "Visit CP"})
        df.drop(subset=["File Path", "Visit ID"], inplace=True)

        df.to_csv("./path_report_upload_records.csv", index=False)

    #  ---------------------------------------------------------------------

    def matchVisitForPathReport(self, data, env):
        """Uses surgical accession number to attempt to match an existing visit in OpS"""

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)
        url = f"{base}{self.queryExtension}"

        labels = data["Path. Number"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.visitSurgicalAccessionNumberMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        visitDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)

        return visitDetails

    #  ---------------------------------------------------------------------

    def pushPathReports(self, data, env):
        """Pushes the path report PDF from pathReportUpload to OpS"""

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token}
        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)

        file = data["File Path"]
        visit = data["Visit ID"]

        url = f"{base}{self.uploadPathReportExtension.replace('_',visit)}"
        files = {"file": open(file, "rb")}

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.post(url, files=files)

        return reply.text

    #  ---------------------------------------------------------------------

    def updateCPSites(self, envs=None, add=None, remove=None, refreshCPList=False):
        """Updates the sites associated with a collection protocol"""

        if not add and not remove:
            return

        cpDF = self.setCPDF(refresh=refreshCPList)
        envs = self.envs.keys() if not envs else [envs] if not isinstance(envs, list) else envs

        add = add if isinstance(add, list) else [add] if add else []
        remove = remove if isinstance(remove, list) else [remove] if remove else []

        for env in envs:

            filt = cpDF[env].notna()
            currentDF = cpDF[filt].copy()

            currentDF[env] = currentDF[env].astype(str).map((lambda x: x.split(".")[0]))
            currentDF["Response"] = currentDF[env].map(
                (lambda x: self.genericGetRequest(env, f"{self.cpWorkflowListExtension}{x}"))
            )

            filt = currentDF["Response"].map((lambda x: isinstance(x, dict)))
            currentDF = currentDF[filt]

            currentDF["Sites"] = currentDF["Response"].map((lambda x: x.get("cpSites") if x.get("cpSites") else []))

            currentDF["Updated Sites"] = currentDF["Sites"].map(
                (lambda x: [site for site in x if site["siteName"] not in remove])
            )

            currentDF["Errors"] = currentDF.apply((lambda x: self.pushCPSiteUpdate(env, x, add)), axis=1)

            keepCols = ["cpShortTitle", "Errors"]
            currentDF.drop(columns=[col for col in currentDF.columns if col not in keepCols], inplace=True)
            currentDF.dropna(subset=["Errors"], inplace=True)

            if len(currentDF):
                currentDF.to_csv(f"{self.outputDir}{env}_site_update_errors.csv", index=False)

    #  ---------------------------------------------------------------------

    def pushCPSiteUpdate(self, env, data, add):
        """Pushes data associated with the sites update"""

        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)
        url = f"{base}{self.cpWorkflowListExtension}{data[env]}"

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        uploadData = data["Response"]
        uploadData["cpSites"] = data["Updated Sites"]

        if add:
            uploadData["cpSites"].extend(
                [{"siteName": val} for val in add if all(val != site["siteName"] for site in uploadData["cpSites"])]
            )

        with httpx.Client(headers=headers, timeout=20) as client:
            response = client.put(url, data=jp.encode(uploadData, unpicklable=False))

            response = response.json()

            if isinstance(response, list):
                return response

    #  ---------------------------------------------------------------------

    def genericGUIFileUpload(self, importType="CREATE", checkStatus=False):
        """Enables standard bulk uploads as per the OpS GUI; Allows for distinction between Create and Update per the GUI"""

        uploadTypes = [
            "cp",
            "specimen",
            "cpr",
            "user",
            "userroles",
            "site",
            "shipment",
            "institute",
            "dprequirement",
            "distributionprotocol",
            "distributionorder",
            "storagecontainer",
            "storagecontainertype",
            "containershipment",
            "cpe",
            "masterspecimen",
            "participant",
            "sr",
            "visit",
            "specimenaliquot",
            "specimenderivative",
            "specimendisposal",
            "consent",
        ]

        # below creates dict of dicts as follows {uploadType: {filePath: env, filePath: env}}

        validatedItems = {
            uploadType: {
                (self.inputDir + file): file.split("_")[1].lower()
                for file in os.listdir(self.inputDir)
                if file.lower().startswith(uploadType) and file.split("_")[1].lower() in self.envs.keys()
            }
            for uploadType in uploadTypes
        }

        for templateType in validatedItems.keys():

            if validatedItems[templateType]:
                [
                    self.pushFile(self.fileUploadPrep(file), templateType, env, importType, checkStatus)
                    for file, env in tqdm(
                        validatedItems[templateType].items(),
                        desc=f"File Uploads - {templateType.title()}",
                        unit=" Files",
                    )
                ]

    #  ---------------------------------------------------------------------

    def fileUploadPrep(self, file):
        """Prepares a file for upload via genericGUIFileUpload"""

        df = pd.read_csv(file, dtype=str)

        dtConvertCols = [col for col in df.columns.values if "date" in col.lower() or "created" in col.lower()]
        for col in dtConvertCols:
            filt = df[col].notna()
            df.loc[filt, col] = df.loc[filt, col].map(self.cleanDateForFileUpload)
        df.to_csv(file, index=False)

        return file

    #  ---------------------------------------------------------------------

    def cleanDateForFileUpload(self, date):
        """Prepares dates for upload via genericGUIFileUpload"""

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

    def pushFile(self, file, templateType, env, importType, checkStatus):
        """Pushes the file from genericGUIFileUpload to OpS and provides updates on import"""

        token = self.authTokens[env]
        headers = {"X-OS-API-TOKEN": token}
        base = self.baseURL.replace("_", "") if env == "prod" else self.baseURL.replace("_", env)
        url = f"{base}{self.uploadExtension}input-file"
        files = [("file", (".csv", open(file, "rb"), "application/octet-stream"))]

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.post(url, files=files)

        fileID = ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]]) if reply.is_error else reply.json()
        fileID = fileID["fileId"]

        data = {
            "objectType": self.templateTypes[templateType],
            "importType": importType,
            "inputFileId": fileID,
        }

        url = f"{base}{self.uploadExtension}"
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.post(url, data=jp.encode(data, unpicklable=False))

        uploadID = ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]]) if reply.is_error else reply.json()
        uploadID = uploadID["id"]

        if checkStatus:

            status = None
            statusList = ["completed", "stopped", "failed"]
            extension = self.uploadExtension + str(uploadID)

            while status is None:

                url = f"{base}{extension}"
                with httpx.Client(headers=headers, timeout=20) as client:
                    reply = client.get(url)

                uploadStatus = (
                    ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]])
                    if reply.is_error
                    else reply.json()
                )

                if uploadStatus and "status" in uploadStatus.keys():

                    if uploadStatus["status"].lower() in statusList:
                        status = uploadStatus["status"].lower()

                        if status == "failed":

                            extension += "/output"

                            url = f"{base}{extension}"
                            with httpx.Client(headers=headers, timeout=20) as client:
                                reply = client.get(url)

                            uploadStatus = (
                                ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]])
                                if reply.is_error
                                else reply.text
                            )

                            with open(
                                f"{self.outputDir}/Failed Upload {uploadID} Report.csv",
                                "w",
                            ) as f:
                                f.write(uploadStatus)

                else:
                    time.sleep(0.25)

            print(f"Status of job {uploadID} is {status}!")

        shutil.move(file, self.outputDir)

    #  ---------------------------------------------------------------------
    #  NOTE Custom uploads and related functions start here
    #  ---------------------------------------------------------------------

    def upload(self, matchPPID=False):  #  impliment check for cpDefJSONUpload and genericGUIFileUpload
        """Generic upload function which attempts to upload as many files in the input folder as possible"""

        # self.syncAll()

        # print("Syncing Dropdown Values")
        # self.syncDropdowns()

        uploadTypes = ["universal", "participants", "visits", "specimens", "arrays"]

        # below creates dict of dicts as follows {uploadType: {filePath: env, filePath: env}}

        validatedItems = {
            uploadType: {
                (self.inputDir + file): file.split("_")[1].lower()
                for file in os.listdir(self.inputDir)
                if file.lower().startswith(uploadType) and file.split("_")[1].lower() in self.envs.keys()
            }
            for uploadType in uploadTypes
        }

        # passing dicts of {filePath: env, filePath: env} to their respective upload functions
        # below works because the keys in uploadTypes will always exist, but the dict they link to may be empty, which will eval to False

        if validatedItems["universal"]:
            [
                self.universalUpload(self.dfImport(file, env), matchPPID)
                for file, env in tqdm(validatedItems["universal"].items(), desc="Universal Uploads", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["universal"].keys()]

        if validatedItems["participants"]:
            [
                self.participantUpload(self.dfImport(file, env), matchPPID)
                for file, env in tqdm(
                    validatedItems["participants"].items(), desc="Participant Uploads", unit=" Files"
                )
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["participants"].keys()]

        if validatedItems["visits"]:
            [
                self.visitUpload(self.dfImport(file, env))
                for file, env in tqdm(validatedItems["visits"].items(), desc="Visit Uploads", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["visits"].keys()]

        if validatedItems["specimens"]:
            [
                self.specimenUpload(self.dfImport(file, env))
                for file, env in tqdm(validatedItems["specimens"].items(), desc="Specimen Uploads", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["specimens"].keys()]

        if validatedItems["arrays"]:
            [
                self.arrayUpload(self.dfImport(file, env))
                for file, env in tqdm(validatedItems["arrays"].items(), desc="Array Uploads", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["arrays"].keys()]

    #  ---------------------------------------------------------------------

    def dfImport(self, file, env):
        """Import and pre-processing/pre-validation of data which is to be uploaded/audited"""

        df = pd.read_csv(file, dtype=str)
        self.currentItem = file

        dtConvertCols = [
            col
            for col in df.columns.values
            if any([val in col.lower() for val in ["date", "time", "created on"]])
            and not any([val in col.lower() for val in ["birth", "death", "original"]])
        ]

        if "DTs Processed" not in df.columns:
            df["DTs Processed"] = None

        for col in dtConvertCols:
            originalCol = f"Original {col}"

            if originalCol not in df.columns:
                df[originalCol] = df[col]
                filt = df["DTs Processed"].isna() & df[col].notna()
                df.loc[filt, col] = (
                    pd.to_datetime(df.loc[filt, col]).dt.tz_localize(tz=self.timezone).astype("Int64") // 1e6
                )
                df.loc[filt, col] = df.loc[filt, col].astype("Int64").astype(str)

        # very important to notice that the "Of" is capitalized -- otherwise, can always check against columns which are forced into lower case or something
        if "Date Of Birth" in df.columns:
            filt = (df["Date Of Birth"].notna()) & (df["DTs Processed"].isna())
            df.loc[filt, "Date Of Birth"] = df.loc[filt, "Date Of Birth"].map(
                (
                    lambda x: "-".join(
                        [x.split(" ")[0].split("/")[2], x.split(" ")[0].split("/")[0], x.split(" ")[0].split("/")[1]]
                    )
                )
            )

        if "Death Date" in df.columns:
            filt = (df["Death Date"].notna()) & (df["DTs Processed"].isna())
            df.loc[filt, "Death Date"] = df.loc[filt, "Death Date"].map(
                (
                    lambda x: "-".join(
                        [x.split(" ")[0].split("/")[2], x.split(" ")[0].split("/")[0], x.split(" ")[0].split("/")[1]]
                    )
                )
            )

        df["DTs Processed"] = "TRUE"

        # standard code for the below is "##set_to_blank##" --> see here: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/71598083/Updating+value+as+blank+using+bulk+import
        filt = df.isin([self.setBlankCode]).any()
        if filt.any():
            # empty string should allow the field to be uploaded, and passing an empty string blanks out the value already in OpS, if it exists
            df.loc[filt] = ""

        df.to_csv(file, index=False)
        self.recordDF = df.copy()

        # basically, if participant, visit, specimen, or universal upload
        if "CP Short Title" in df.columns:

            df["CP ID"] = None
            cpDF = self.setCPDF()

            #  getting all unique CP short titles and their codes in order to build a dict that makes referencing them later easier
            uniqueShortTitles = df["CP Short Title"].unique()
            dfsByCP = {}

            for shortTitle in uniqueShortTitles:
                filt = df["CP Short Title"] == shortTitle
                df.loc[filt, "CP ID"] = (
                    cpDF.loc[(cpDF["cpShortTitle"] == shortTitle), env].astype(int, errors="ignore").item()
                )

                if len(uniqueShortTitles) > 1:
                    newDF = df[filt].copy()
                    dfsByCP[shortTitle] = [newDF, env]

                else:
                    dfsByCP[shortTitle] = [df, env]

            return dfsByCP

        # basically, if array upload -- could make this the if statement, instead of the other uploads being first, and do if "array" in file.lower()
        elif "Core Diameter (mm)" in df.columns:

            uniqueArrays = df["Name"].unique()
            arrayByName = {}

            for arrayName in uniqueArrays:
                filt = df["Name"] == arrayName

                if len(uniqueArrays) > 1:
                    newDF = df[filt].copy()
                    arrayByName[arrayName] = [newDF, env]

                else:
                    arrayByName[arrayName] = [df, env]

            return arrayByName

    #  ---------------------------------------------------------------------

    def universalUpload(self, dfDict, matchPPID):
        """Wrapper around the upload functions for the three main import types which compose the OpS "Master Specimen" template; Uploads data from a universal template"""

        self.participantUpload(dfDict, matchPPID)
        self.visitUpload(dfDict)
        self.specimenUpload(dfDict)

    #  ---------------------------------------------------------------------

    def participantUpload(self, dfDict, matchPPID):
        """Performs upload of participant data from a participant template"""

        for shortTitle, (df, env) in dfDict.items():

            self.currentEnv = env
            participantDF = self.participantPreMatchValidation(df, env)
            participantDF = self.matchParticipants(participantDF, shortTitle, matchPPID)

            # used to populate PPIDs in cases where data omits them but includes another value like MRN, etc., which can be used to match profile and get Participant ID
            # 9/23/21 -- don't think it's necessary, but was done as a quality of life thing for users
            ppidParticipantIDFilt = participantDF["PPID"].isna() & participantDF["Participant ID"].notna()
            if ppidParticipantIDFilt.any():

                print("Populating Missing PPIDs by Participant ID")

                matchDF = participantDF.loc[ppidParticipantIDFilt].copy()
                matchParticipantDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
                matchedDF = pd.concat([self.getPPIDByParticipantID(df, shortTitle) for df in matchParticipantDF])

                participantDF.update(matchedDF)

            #  getting all participant additional field form info and making a dict
            cpID = df["CP ID"].unique()[0]
            if not isinstance(cpID, int):
                cpID = str(cpID)
                cpID = cpID.split(".")[0] if "." in cpID else cpID
            params = {"cpId": cpID}
            self.formExtension = {shortTitle: self.getFormExtension(self.pafExtension, params=params)}

            # TODO:
            # if matchPPID <-- filter for PPIDs and do those first, or in parallel with, non-PPID create/update?
            # this should avoid needing error handling for "CPR_DUP_PPID", but still need to consider "CPR_MANUAL_PPID_NOT_ALLOWED"
            # introduces a consideration regarding create/update as a subset of has PPID vs. not

            participantDF = participantDF.apply(self.buildParticipantObj, axis=1)

            dropFilt = participantDF["Participant Obj"].isna()
            participantDF = participantDF.drop(index=participantDF.loc[dropFilt].index)

            updateFilt = participantDF["CPR ID"].notna()

            base = (
                self.baseURL.replace("_", "")
                if self.currentEnv == "prod"
                else self.baseURL.replace("_", self.currentEnv)
            )

            participantDF.loc[updateFilt, "Participant Url"] = participantDF.loc[updateFilt, "CPR ID"].apply(
                (lambda x: f"{base}{self.registerParticipantExtension}{x}")
            )
            participantDF.loc[~updateFilt, "Participant Url"] = f"{base}{self.registerParticipantExtension}"

            updateRecords = self.chunkDF(participantDF.loc[updateFilt].copy())

            createRecords = self.participantNoMatchValidation(participantDF.loc[~updateFilt].copy())
            createRecords = self.chunkDF(createRecords)

            if updateRecords and createRecords:

                # with ThreadPoolExecutor(2) as ex:
                #     updateRecords = pd.concat(ex.map(self.updateParticipants, updateRecords))
                #     createRecords = pd.concat(ex.map(self.createParticipants, createRecords))

                updateRecords = [self.updateParticipants(record) for record in updateRecords]
                createRecords = [self.createParticipants(record) for record in createRecords]

            elif updateRecords:

                # with ThreadPoolExecutor(2) as ex:
                #     participantDF = pd.concat(ex.map(self.updateParticipants, updateRecords))

                updateRecords = [self.updateParticipants(record) for record in updateRecords]

            else:

                # with ThreadPoolExecutor(2) as ex:
                #     participantDF = pd.concat(ex.map(self.createParticipants, createRecords))

                createRecords = [self.createParticipants(record) for record in createRecords]

            filt = self.recordDF["CP Short Title"] == shortTitle

            if self.recordDF.loc[filt, "PPID"].isna().any() and self.recordDF.loc[filt, "PPID"].notna().any():
                # had to add isinstance str filter because upload errors (like CPR_MANUAL_PPID_NOT_ALLOWED) are stored as list in PPID column
                ppidFilt = (
                    (self.recordDF["CP Short Title"] == shortTitle)
                    & self.recordDF["PPID"].map((lambda x: isinstance(x, str)))
                    & (self.recordDF["Critical Error - Participant"].isna())
                )
                self.recordDF.loc[ppidFilt].apply(self.populatePPIDs, axis=1)

            filt = (self.recordDF["CP Short Title"] == shortTitle) & (
                self.recordDF["Participant Original CP"] == shortTitle
            )

            if filt.any():
                self.recordDF.loc[filt, "Participant Original CP"] = None

            self.recordDF.dropna(axis=1, how="all", inplace=True)
            self.recordDF.to_csv(self.currentItem, index=False)

    #  ---------------------------------------------------------------------

    def participantPreMatchValidation(self, df, env):
        """Performs validation of participant specific data to catch any errors and/or duplicates"""

        print("Validating Participants")

        # adding columns that are required for these functions but not user relevant
        # PPID not required for upload, but, if not provided, will be created, and will need a place to store. Also used to filter at the end of participant upload
        internalCols = [
            "Participant ID",
            "CPR ID",
            "PPID",
            "Participant Obj",
            "Participant Original CP",
            "Critical Error - Participant",
        ]
        internalCols = [col for col in internalCols if col not in df.columns]

        if internalCols:
            df[internalCols] = None
            self.recordDF[internalCols] = None

        # catching errors in fields which are required for upload
        # participants are the only case where this is included in PreMatchValidation
        # this is because they may exist in multiple CPs and it is therefore required for match/update and create
        participantCritical = ["CP Short Title"]
        criticalFilt = df[participantCritical].isna().any(axis=1)
        criticalErrors = df[criticalFilt].copy()

        if not criticalErrors.empty:

            criticalFilt = df.index.isin(criticalErrors.index)
            df.loc[
                criticalFilt, "Critical Error - Participant"
            ] = f"Value Error in Critical Column(s) [{', '.join(participantCritical)}]"
            self.recordDF.update(df)
            df = df.loc[~criticalFilt]

        # catching errors for fields which have known, pre-defined permissible values
        self.dropdownDF = pd.read_csv(self.dropdownOutpath.replace("_", f"{env}_all_dropdown_values"), dtype=str)

        dropdownCols = {"Gender": "gender", "Vital Status": "vital_status"}
        dropdownCols = {key: val for key, val in dropdownCols.items() if key in df.columns}

        for col in df.columns:
            if "race" in col.lower():
                dropdownCols[col] = "race"
            elif "ethnicity" in col.lower():
                dropdownCols[col] = "ethnicity"

        for templateCol, dropdownName in dropdownCols.items():

            errorFilt = df[templateCol].isin(self.dropdownDF[dropdownName])
            errorFilt = ~errorFilt & df[templateCol].notna()
            df.loc[errorFilt, "Critical Error - Participant"] = df.loc[
                errorFilt, "Critical Error - Participant"
            ].apply(
                (
                    lambda x: f"{x}; Value Error in Column {templateCol}"
                    if pd.notna(x)
                    else f"Value Error in Column {templateCol}"
                )
            )

        self.recordDF.update(df)

        criticalFilt = df["Critical Error - Participant"].notna()
        df = df.loc[~criticalFilt]

        # catching duplicate records

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

        colCheck = ["PMI", "Race", "Ethnicity", "Participant"]

        participantSub1 = [
            col
            for col in df.columns.values
            if col in participantSub or any([checkVal in col for checkVal in colCheck])
        ]

        df = df.drop_duplicates(subset=participantSub1)

        participantSub2 = ["CP Short Title", "First Name", "Last Name", "Date Of Birth"]
        # keep = false marks all duplicates as true for filtering, otherwise options are mark only first or last instance of duplicate
        duplicateFilt = df.duplicated(subset=participantSub2, keep=False)

        if duplicateFilt.any():

            # duplicateFilt = participantDF.index.isin(duplicatedRecords.index)
            df = df.loc[~duplicateFilt].copy()

            duplicateFilt = (~self.recordDF.duplicated(subset=participantSub1)) & (
                self.recordDF.duplicated(subset=participantSub2, keep=False)
            )

            if duplicateFilt.any():
                self.recordDF.loc[duplicateFilt, "Duplicate Participant"] = "True"

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def matchParticipants(self, participantDF, shortTitle, matchPPID):
        """Attempts to match participants in the data to existing profile for that participant in OpS"""

        if matchPPID and participantDF["Participant ID"].isna().any():

            filt = (participantDF["PPID"].notna()) & (participantDF["Participant ID"].isna())

            if filt.any():

                print("Matching Participants on PPID")

                matchDF = participantDF.loc[filt].copy()
                matchParticipantDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
                matchedDF = pd.concat([self.matchParticipantPPID(df, shortTitle) for df in matchParticipantDF])

                participantDF.update(matchedDF)

        if participantDF["Participant ID"].isna().any():

            if "eMPI" in participantDF.columns and not participantDF["eMPI"].empty:

                filt = (participantDF["eMPI"].notna()) & (participantDF["Participant ID"].isna())

                if filt.any():

                    print("Matching Participants on eMPI")

                    matchDF = participantDF.loc[filt].copy()
                    matchParticipantDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
                    matchedDF = pd.concat([self.matchParticipantEMPI(df, shortTitle) for df in matchParticipantDF])

                    participantDF.update(matchedDF)

        if participantDF["Participant ID"].isna().any():

            siteCols = [col for col in participantDF.columns if "#site" in col.lower() and "pmi#" in col.lower()]
            mrnCols = [col for col in participantDF.columns if "#mrn" in col.lower() and "pmi#" in col.lower()]

            for siteCol, mrnCol in zip(siteCols, mrnCols):

                if not participantDF[siteCol].empty and not participantDF[mrnCol].empty:

                    sites = participantDF[siteCol].unique()

                    for site in sites:

                        filt = (
                            (participantDF[siteCol] == site)
                            & (participantDF[mrnCol].notna())
                            & (participantDF["Participant ID"].isna())
                        )

                        if filt.any():

                            print(f"Matching Participants on MRN Site: {site}")

                            matchDF = participantDF.loc[filt].copy()
                            matchParticipantDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
                            matchedDF = pd.concat(
                                [self.matchParticipantMRN(df, shortTitle, site, mrnCol) for df in matchParticipantDF]
                            )

                            participantDF.update(matchedDF)

        return participantDF

    #  ---------------------------------------------------------------------

    def matchParticipantEMPI(self, data, shortTitle):
        """Uses participant EMPI to attempt to match an existing profile in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["eMPI"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.participanteMPIMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        participantDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        participantDetails.set_index("eMPI", inplace=True)

        # below should be able to update Participant ID (ID for highest level shared info) and CPR ID (ID of profile specific to a given CP)
        filt = participantDetails["Participant Original CP"] == shortTitle
        participantsInCP = participantDetails.loc[filt].copy()

        # below should be able to update Participant ID, but not CPR ID, since they were not identified in the CP of interest
        # filters out participants which are in CP of interest *and* some other CP with eMPI in other DF, then negating the filter
        filt = filt & (participantDetails.index.isin(participantsInCP.index))
        participantsInOtherCP = participantDetails.loc[~filt].copy()
        participantsInOtherCP.drop(columns=["CPR ID"], inplace=True)
        participantsInOtherCP.drop_duplicates(subset=["Participant ID"], inplace=True)

        ind = data.index.copy()
        data.set_index("eMPI", inplace=True)
        data.update(participantsInOtherCP)
        data.update(participantsInCP)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Participant ID", "CPR ID", "Participant Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def matchParticipantMRN(self, data, shortTitle, site, mrnCol):
        """Uses participant MRN to attempt to match an existing profile in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data[mrnCol].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.participantMRNMatchAQL.replace("_", matchVals)
                        .replace("*", site)
                        .replace("$", mrnCol),
                    },
                    unpicklable=False,
                ),
            )

        participantDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        participantDetails.set_index(mrnCol, inplace=True)

        # below should be able to update Participant ID (ID for highest level shared info) and CPR ID (ID of profile specific to a given CP)
        filt = participantDetails["Participant Original CP"] == shortTitle
        participantsInCP = participantDetails.loc[filt].copy()

        # below should be able to update Participant ID, but not CPR ID, since they were not identified in the CP of interest
        # filters out participants which are in CP of interest *and* some other CP with eMPI in other DF, then negating the filter
        filt = filt & (participantDetails.index.isin(participantsInCP.index))
        participantsInOtherCP = participantDetails.loc[~filt].copy()
        participantsInOtherCP.drop(columns=["CPR ID"], inplace=True)
        participantsInOtherCP.drop_duplicates(subset=["Participant ID"], inplace=True)

        ind = data.index.copy()
        data.set_index(mrnCol, inplace=True)
        data.update(participantsInOtherCP)
        data.update(participantsInCP)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Participant ID", "CPR ID", "Participant Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def matchParticipantPPID(self, data, shortTitle):
        """Uses participant PPID to attempt to match an existing profile in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["PPID"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.participantPPIDMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        participantDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        participantDetails.set_index("PPID", inplace=True)

        # below should be able to update Participant ID (ID for highest level shared info) and CPR ID (ID of profile specific to a given CP)
        filt = participantDetails["Participant Original CP"] == shortTitle
        participantsInCP = participantDetails.loc[filt].copy()

        ind = data.index.copy()
        data.set_index("PPID", inplace=True)
        data.update(participantsInCP)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Participant ID", "CPR ID", "Participant Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def participantNoMatchValidation(self, df):
        """Enforces the more stringent rules that come with needing to create a participant (i.e. if they fail to match an existing OpS profile)"""

        # catching errors in fields which are required for Create
        participantCritical = ["Registration Date"]

        criticalFilt = df[participantCritical].isna().any(axis=1)
        criticalErrors = df[criticalFilt].copy()

        if not criticalErrors.empty:

            criticalFilt = df.index.isin(criticalErrors.index)
            df.loc[
                criticalFilt, "Critical Error - Participant"
            ] = f"Value Error in Critical Column(s) [{', '.join(participantCritical)}]"
            self.recordDF.update(df)
            df = df.loc[~criticalFilt]

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def getPPIDByParticipantID(self, data, shortTitle):
        """Uses participant ID and the CP short title where the matched profile resides to look up the associated PPID"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Participant ID"].copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.participantIDMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        participantDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        participantDetails.set_index("Participant ID", inplace=True)

        # below should be able to update Participant ID (ID for highest level shared info) and CPR ID (ID of profile specific to a given CP)
        filt = participantDetails["Participant Original CP"] == shortTitle
        participantsInCP = participantDetails.loc[filt].copy()

        ind = data.index.copy()
        data.set_index("Participant ID", inplace=True)
        data.update(participantsInCP)
        data.reset_index(inplace=True)
        data.index = ind

        self.recordDF.loc[data.index, "PPID"] = data["PPID"]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def buildParticipantObj(self, data):
        """Constructs the participant object which will ultimately be serialized and uploaded"""

        #  putting mrn sites and vals into lists
        siteNames = [
            data[site]
            for site in data.keys()
            if "#site" in site.lower() and "pmi#" in site.lower() and pd.notna(data[site])
        ]
        mrnVals = [
            data[mrnVal]
            for mrnVal in data.keys()
            if "#mrn" in mrnVal.lower() and "pmi#" in mrnVal.lower() and pd.notna(data[mrnVal])
        ]

        # catching cases with redundant MRN sites (set drops duplicates) and cases where the mrn number has non-digit characters -- if caught, log the error and skip the record
        # note that set will put siteNames in alphabetical order -- it is ok in this case because the original list is used when logging in the else statement
        if len(set(siteNames)) < len(siteNames) or not all(map(str.isdigit, mrnVals)):

            self.recordDF.loc[data.name, "Critical Error - Participant"] = "Duplicate MRNs"
            self.recordDF.to_csv(self.currentItem, index=False)

            data["Participant Obj"] = None

            return data

        else:

            participant = Generic()
            registration = Generic()

            cols = data.keys()
            cpDF = self.setCPDF()
            cpShortTitle = data["CP Short Title"]
            formExten = self.formExtension[cpShortTitle]
            exten = Extension()

            #  if so, we should account for that in our data source as well as in our upload, so we get the required form id and name, and set the form data frame
            if formExten:
                exten = self.buildExtensionDetail(formExten, data)

            #  making individual dicts for each mrn site and corresponding val
            pmis = [
                {"siteName": site, "mrn": int(mrnVal)}
                for site, mrnVal in zip(siteNames, mrnVals)
                if siteNames and mrnVals
            ]

            #  putting races and ethnicities into lists
            races = [data.get(col) for col in cols if "race" in col.lower() and pd.notna(data.get(col))]
            ethnicities = [data.get(col) for col in cols if "ethnicity" in col.lower() and pd.notna(data.get(col))]

            participantMap = {
                "firstName": "First Name",
                "middleName": "Middle Name",
                "lastName": "Last Name",
                "uid": "SSN",
                "birthDate": "Date Of Birth",
                "vitalStatus": "Vital Status",
                "deathDate": "Death Date",
                "gender": "Gender",
                "activityStatus": "Participant Activity Status",
                "empi": "eMPI",
                "code": "Participant ID",
            }

            participantData = {key: data.get(val) for key, val in participantMap.items() if pd.notna(data.get(val))}

            for key, val in participantData.items():
                setattr(participant, key, val)

            if races:
                participant.races = races
            if ethnicities:
                participant.ethnicities = ethnicities
            if pmis:
                participant.pmis = pmis

            participant.extensionDetail = exten

            registrationMap = {
                "registrationDate": "Registration Date",
                "activityStatus": "Registration Activity Status",
                "ppid": "PPID",
                "externalSubjectId": "External Subject ID",
                "code": "CPR ID",
            }

            registrationData = {key: data.get(val) for key, val in registrationMap.items() if pd.notna(data.get(val))}

            for key, val in registrationData.items():
                setattr(registration, key, val)

            registration.cpShortTitle = cpShortTitle
            registration.participant = participant

            data["Participant Obj"] = registration

            return data

    #  ---------------------------------------------------------------------

    def updateParticipants(self, data):
        """Pushes data associated with participants matched in the CP of interest (hence update)"""

        async def updateLogic(data):
            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.put(
                        data.loc[ind, "Participant Url"],
                        data=jp.encode(data.loc[ind, "Participant Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            ppids = [
                ([reply.json()[0]["code"], reply.json()[0]["message"]] if reply.is_error else reply.status_code)
                for reply in replies
            ]

            print(f"Participant Update Results: {ppids}")

            data["Participant Upload Status"] = ppids
            data["Participant Upload Status"] = data["Participant Upload Status"].map(
                (lambda x: f"Participant Update Result: {x}")
            )

            self.recordDF.loc[data.index, "Participant Upload Status"] = data["Participant Upload Status"]
            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(updateLogic(data))

    #  ---------------------------------------------------------------------

    def createParticipants(self, data):
        """Pushes data associated with participants which failed to match in CP of interest, or OpS in general, in order to create them"""

        async def createLogic(data):
            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.post(
                        data.loc[ind, "Participant Url"],
                        data=jp.encode(data.loc[ind, "Participant Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            ppids = [
                (
                    reply.json()["ppid"]
                    if "ppid" in reply.json()
                    else [reply.json()[0]["code"], reply.json()[0]["message"]]
                    if reply.is_error
                    else reply
                )
                for reply in replies
            ]

            print(f"Participant Create Results: {ppids}")

            data["PPID"] = ppids

            filt = data["PPID"].map((lambda x: not isinstance(x, list)))
            self.recordDF.loc[data.loc[filt].index, "PPID"] = data.loc[filt, "PPID"]

            data["PPID"] = data["PPID"].map((lambda x: f"Participant Create Result: {x}"))
            self.recordDF.loc[data.index, "Participant Upload Status"] = data["PPID"]

            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(createLogic(data))

    #  ---------------------------------------------------------------------

    def populatePPIDs(self, data):
        """Finds participants in the data which are missing PPIDs and updates the records to include them (for newly created participants)"""

        matchFilt = (
            (self.recordDF["First Name"] == data["First Name"])
            & (self.recordDF["Last Name"] == data["Last Name"])
            & (self.recordDF["CP Short Title"] == data["CP Short Title"])
            & (self.recordDF["Date Of Birth"] == data["Date Of Birth"])
            & (self.recordDF["Registration Date"] == data["Registration Date"])
            & (self.recordDF["PPID"].isna())
        )

        if matchFilt.any():
            self.recordDF.loc[matchFilt, "PPID"] = data["PPID"]

    #  ---------------------------------------------------------------------

    def visitUpload(self, dfDict):
        """Performs upload of visit data from a visit template"""

        for shortTitle, (df, env) in dfDict.items():

            self.currentEnv = env
            visitDF = self.visitPreMatchValidation(df, env)
            visitDF = self.matchVisits(visitDF)

            #  getting all visit additional field form info and making a dict
            cpID = df["CP ID"].unique()[0].split(".")[0] if "." in df["CP ID"].unique()[0] else df["CP ID"].unique()[0]
            params = {"cpId": cpID}
            self.formExtension = {shortTitle: self.getFormExtension(self.vafExtension, params=params)}

            print("Building Visits")

            visitDF = visitDF.apply(self.buildVisitObj, axis=1)

            updateFilt = visitDF["Visit ID"].notna()

            base = (
                self.baseURL.replace("_", "")
                if self.currentEnv == "prod"
                else self.baseURL.replace("_", self.currentEnv)
            )

            visitDF.loc[updateFilt, "Visit Url"] = visitDF.loc[updateFilt, "Visit ID"].apply(
                (lambda x: f"{base}{self.visitExtension.replace('_', x)}")
            )
            visitDF.loc[~updateFilt, "Visit Url"] = base + self.visitExtension.replace("_", "")

            updateRecords = self.chunkDF(visitDF.loc[updateFilt].copy())

            createRecords = self.visitNoMatchValidation(visitDF.loc[~updateFilt].copy())
            createRecords = self.chunkDF(createRecords)

            if updateRecords and createRecords:
                print("On Update and Create Visits")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.updateVisits, updateRecords)
                #     ex.map(self.createVisits, createRecords)

                updated = [self.updateVisits(record) for record in updateRecords]
                created = [self.createVisits(record) for record in createRecords]

            elif updateRecords:
                print("On Update Visits")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.updateVisits, updateRecords)

                updated = [self.updateVisits(record) for record in updateRecords]

            else:
                print("On Create Visits")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.createVisits, createRecords)

                created = [self.createVisits(record) for record in createRecords]

            filt = self.recordDF["CP Short Title"] == shortTitle

            if (
                self.recordDF.loc[filt, "Visit Name"].isna().any()
                and self.recordDF.loc[filt, "Visit Name"].notna().any()
            ):
                print("Populating Visit Names")
                visitFilt = (
                    (self.recordDF["CP Short Title"] == shortTitle)
                    & (self.recordDF["Visit Name"].map((lambda x: isinstance(x, str))))
                    & (self.recordDF["Critical Error - Visit"].isna())
                    & (self.recordDF["PPID"].map((lambda x: isinstance(x, str))))
                )
                self.recordDF.loc[visitFilt].apply(self.populateVisitNames, axis=1)

            filt = (self.recordDF["CP Short Title"] == shortTitle) & (self.recordDF["Visit Original CP"] == shortTitle)

            if filt.any():
                self.recordDF.loc[filt, "Visit Original CP"] = None

            self.recordDF.dropna(axis=1, how="all", inplace=True)
            self.recordDF.to_csv(self.currentItem, index=False)

    #  ---------------------------------------------------------------------

    def visitPreMatchValidation(self, df, env):
        """Performs validation of visit specific data to catch any errors and/or duplicates"""

        print("Validating Visits")

        # adding columns that are required for these functions but not user relevant
        internalCols = ["Visit ID", "Visit Obj", "Visit Original CP", "Critical Error - Visit"]
        internalCols = [col for col in internalCols if col not in df.columns]

        if internalCols:
            df[internalCols] = None
            self.recordDF[internalCols] = None

        # catching errors for fields which have known, pre-defined permissible values
        self.dropdownDF = pd.read_csv(self.dropdownOutpath.replace("_", f"{env}_all_dropdown_values"), dtype=str)

        dropdownCols = {"Clinical Status": "clinical_status", "Missed/Not Collected Reason": "missed_visit_reason"}
        dropdownCols = {key: val for key, val in dropdownCols.items() if key in df.columns}

        for col in df.columns:
            if "clinical diagnosis" in col.lower():
                dropdownCols[col] = "clinical_diagnosis"

        for templateCol, dropdownName in dropdownCols.items():

            errorFilt = df[templateCol].isin(self.dropdownDF[dropdownName])
            errorFilt = ~errorFilt & df[templateCol].notna()
            df.loc[errorFilt, "Critical Error - Visit"] = df.loc[errorFilt, "Critical Error - Visit"].apply(
                (
                    lambda x: f"{x}; Value Error in Column {templateCol}"
                    if pd.notna(x)
                    else f"Value Error in Column {templateCol}"
                )
            )

        self.recordDF.update(df)
        criticalFilt = df["Critical Error - Visit"].notna()
        df = df.loc[~criticalFilt]

        # catching duplicate records
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

        colCheck = ["Visit", "Clinical"]

        visitSub1 = [
            col for col in df.columns.values if col in visitSub or any([checkVal in col for checkVal in colCheck])
        ]

        df = df.drop_duplicates(subset=visitSub1)

        visitSub2 = ["CP Short Title", "PPID", "Event Label", "Visit Name", "Visit Date"]

        duplicateFilt = df.duplicated(subset=visitSub2, keep=False)

        if duplicateFilt.any():

            # duplicateFilt = visitDF.index.isin(duplicatedRecords.index)
            df = df.loc[~duplicateFilt].copy()

            duplicateFilt = (~self.recordDF.duplicated(subset=visitSub1)) & (
                self.recordDF.duplicated(subset=visitSub2, keep=False)
            )

            if duplicateFilt.any():
                self.recordDF.loc[duplicateFilt, "Duplicate Visit"] = "True"

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def matchVisits(self, visitDF):
        """Attempts to match visits in the data to existing visit in OpS"""

        if not visitDF["Visit Name"].empty:

            filt = (visitDF["Visit Name"].notna()) & (visitDF["Visit ID"].isna())

            if filt.any():

                print("Matching Visits")

                matchDF = visitDF.loc[filt].copy()
                matchVisitDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
                matchedDF = pd.concat([self.matchVisitName(df) for df in matchVisitDF])

                visitDF.update(matchedDF)

        return visitDF

    #  ---------------------------------------------------------------------

    def matchVisitName(self, data):
        """Uses visit name to attempt to match an existing visit in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Visit Name"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.visitNameMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        visitDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        visitDetails.set_index("Visit Name", inplace=True)

        ind = data.index.copy()
        data.set_index("Visit Name", inplace=True)
        data.update(visitDetails)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Visit ID", "Visit Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def matchVisitSurgicalAccessionNumber(self, data):
        """Uses surgical accession number to attempt to match an existing visit in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Path. Number"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.visitSurgicalAccessionNumberMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        visitDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        visitDetails.set_index("Visit Name", inplace=True)

        ind = data.index.copy()
        data.set_index("Visit Name", inplace=True)
        data.update(visitDetails)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Visit ID", "Visit Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def visitNoMatchValidation(self, df):
        """Enforces the more stringent rules that come with needing to create a visit (i.e. if they fail to match an existing visit in OpS)"""

        # catching errors in fields which are required for Create
        # enforcing event label requirement so that visits don't end up created as unplanned collection if event label forgotten
        visitCritical = ["CP Short Title", "PPID", "Event Label"]

        criticalFilt = df[visitCritical].isna().any(axis=1)
        criticalErrors = df[criticalFilt].copy()

        if not criticalErrors.empty:

            criticalFilt = df.index.isin(criticalErrors.index)
            df.loc[
                criticalFilt, "Critical Error - Visit"
            ] = f"Value Error in Critical Column(s) [{', '.join(visitCritical)}]"
            self.recordDF.update(df)
            df = df.loc[~criticalFilt]

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def buildVisitObj(self, data):
        """Constructs the visit object which will ultimately be serialized and uploaded"""

        formExten = self.formExtension[data["CP Short Title"]]

        visit = Generic()

        if formExten:
            extensionDetail = self.buildExtensionDetail(formExten, data)

        #  since it's required for specimen class, and attrsMap defaults to an empty dict, go ahead and make an empty Extension instance
        else:
            extensionDetail = Extension()

        clinicalDiagnoses = [
            data.get(col) for col in data.keys() if "clinical diagnosis#" in col.lower() and pd.notna(data.get(col))
        ]

        visitMap = {
            "name": "Visit Name",
            "eventId": "Event Id",
            "eventLabel": "Event Label",
            "ppid": "PPID",
            "cpTitle": "CP Title",
            "cpShortTitle": "CP Short Title",
            "clinicalStatus": "Clinical Status",
            "activityStatus": "Visit Activity Status",
            "status": "Visit Status",
            "missedReason": "Missed/Not Collected Reason",
            "missedBy": "Missed/Not Collected By#Email Address",
            "surgicalPathologyNumber": "Path. Number",
            "cohort": "Cohort",
            "visitDate": "Visit Date",
            "eventPoint": "Event Point",
            "site": "Collection Site",
            "comments": "Visit Comments",
            "code": "Visit ID",
        }

        visitData = data.dropna()
        visitData = {key: visitData[val] for key, val in visitMap.items() if val in visitData.keys()}

        for key, val in visitData.items():
            setattr(visit, key, val)

        visit.extensionDetail = extensionDetail

        if clinicalDiagnoses:
            visit.clinicalDiagnoses = clinicalDiagnoses

        data["Visit Obj"] = visit

        return data

    #  ---------------------------------------------------------------------

    def updateVisits(self, data):
        """Pushes data associated with visits matched in the CP of interest (hence update)"""

        async def updateLogic(data):

            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.put(
                        data.loc[ind, "Visit Url"],
                        data=jp.encode(data.loc[ind, "Visit Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            visits = [
                ([reply.json()[0]["code"], reply.json()[0]["message"]] if reply.is_error else reply.status_code)
                for reply in replies
            ]

            print(f"Visit Update Results: {visits}")

            data["Visit Upload Status"] = visits
            data["Visit Upload Status"] = data["Visit Upload Status"].map((lambda x: f"Visit Update Result: {x}"))

            self.recordDF.loc[data.index, "Visit Upload Status"] = data["Visit Upload Status"]
            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(updateLogic(data))

    #  ---------------------------------------------------------------------

    def createVisits(self, data):
        """Pushes data associated with visits which failed to match in CP of interest in order to create them"""

        async def createLogic(data):
            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.post(
                        data.loc[ind, "Visit Url"],
                        data=jp.encode(data.loc[ind, "Visit Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            visits = [
                (
                    reply.json()["name"]
                    if "name" in reply.json()
                    else [reply.json()[0]["code"], reply.json()[0]["message"]]
                    if reply.is_error
                    else reply.json()
                )
                for reply in replies
            ]

            print(f"Visit Create Results: {visits}")

            data["Visit Name"] = visits

            filt = data["Visit Name"].map((lambda x: not isinstance(x, list)))
            self.recordDF.loc[data.loc[filt].index, "Visit Name"] = data.loc[filt, "Visit Name"]

            data["Visit Name"] = data["Visit Name"].map((lambda x: f"Visit Create Result: {x}"))
            self.recordDF.loc[data.index, "Visit Upload Status"] = data["Visit Name"]

            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(createLogic(data))

    #  ---------------------------------------------------------------------

    def populateVisitNames(self, data):
        """Finds visits in the data which are missing names and updates the records to include them (for newly created visits)"""

        matchFilt = (
            (self.recordDF["PPID"] == data["PPID"])
            & (self.recordDF["CP Short Title"] == data["CP Short Title"])
            & (self.recordDF["Event Label"] == data["Event Label"])
            & (self.recordDF["Visit Date"] == self.recordDF.loc[data.name, "Visit Date"])
            & (self.recordDF["Visit Name"].isna())
        )

        self.recordDF.loc[matchFilt, "Visit Name"] = data["Visit Name"]

        if "Visit ID" in data.keys():
            self.recordDF.loc[matchFilt, "Visit ID"] = data["Visit ID"]

    #  ---------------------------------------------------------------------

    def specimenUpload(self, dfDict):
        """Performs upload of specimen data from a specimen template"""

        for shortTitle, (df, env) in dfDict.items():

            self.currentEnv = env
            specimenDF = self.specimenPreMatchValidation(df, env)

            #  getting all specimen additional field form info and making a dict as above
            cpID = df["CP ID"].unique()[0].split(".")[0] if "." in df["CP ID"].unique()[0] else df["CP ID"].unique()[0]
            params = {"cpId": cpID}
            self.formExtension = {shortTitle: self.getFormExtension(self.safExtension, params=params)}

            labelFilt = specimenDF["Specimen Label"].notna()
            specimenDF.loc[labelFilt, "Specimen Label"] = specimenDF.loc[labelFilt, "Specimen Label"].map(
                (lambda x: x.replace(",", ""))
            )

            labelFilt = specimenDF["Parent Specimen Label"].notna()
            specimenDF.loc[labelFilt, "Parent Specimen Label"] = specimenDF.loc[
                labelFilt, "Parent Specimen Label"
            ].map((lambda x: x.replace(",", "")))

            specimenDF = self.matchSpecimens(specimenDF)

            print("Building Specimens")

            # would be interesting to do this with processpoolexecutor, as below, if possible
            # objBuildDFs = self.chunkDF(specimenDF)

            # with ProcessPoolExecutor() as ex:
            #     # buildSpecimenObjMP just takes the chunked DFs and applies buildSpecimenObj to each
            #     objBuildDFs = ex.map(self.buildSpecimenObjMP, objBuildDFs)
            #     specimenDF = pd.concat(objBuildDFs)

            specimenDF = specimenDF.apply(self.buildSpecimenObj, axis=1)

            updateFilt = specimenDF["Specimen ID"].notna()

            base = (
                self.baseURL.replace("_", "")
                if self.currentEnv == "prod"
                else self.baseURL.replace("_", self.currentEnv)
            )

            specimenDF.loc[updateFilt, "Specimen Url"] = specimenDF.loc[updateFilt, "Specimen ID"].apply(
                (lambda x: f"{base}{self.specimenExtension.replace('_', x)}")
            )

            createFilt = specimenDF["Specimen ID"].isna()

            parentFilt = createFilt & (specimenDF["Lineage"].isin(["New", "new", "Derived", "derived"]))
            specimenDF.loc[parentFilt, "Specimen Url"] = base + self.specimenExtension.replace("_", "")

            childFilt = createFilt & (specimenDF["Lineage"].isin(["Aliquot", "aliquot"]))
            specimenDF.loc[childFilt, "Specimen Url"] = base + self.aliquotExtension

            updateRecords = self.chunkDF(specimenDF.loc[updateFilt].copy())

            createRecords = self.specimenNoMatchValidation(specimenDF.loc[createFilt].copy())
            createRecords = self.chunkDF(createRecords)

            if updateRecords and createRecords:
                print("Updating and Creating Specimens")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.updateSpecimens, updateRecords)
                #     ex.map(self.createSpecimens, createRecords)

                updated = [self.updateSpecimens(record) for record in updateRecords]
                created = [self.createSpecimens(record) for record in createRecords]

            elif updateRecords:
                print("Updating Specimens")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.updateSpecimens, updateRecords)

                updated = [self.updateSpecimens(record) for record in updateRecords]

            else:
                print("Creating Specimens")

                # with ThreadPoolExecutor(2) as ex:
                #     ex.map(self.createSpecimens, createRecords)

                created = [self.createSpecimens(record) for record in createRecords]

            filt = (self.recordDF["CP Short Title"] == shortTitle) & (
                self.recordDF["Specimen Original CP"] == shortTitle
            )

            if filt.any():
                self.recordDF.loc[filt, "Specimen Original CP"] = None

            self.recordDF.dropna(axis=1, how="all", inplace=True)
            self.recordDF.to_csv(self.currentItem, index=False)

    #  ---------------------------------------------------------------------

    def specimenPreMatchValidation(self, df, env):
        """Performs validation of specimen specific data to catch any errors and/or duplicates"""

        print("Validating Specimens")

        # adding columns that are required for these functions but not user relevant
        internalCols = [
            "Specimen ID",
            "Parent ID",
            "Specimen Obj",
            "Specimen Original CP",
            "Critical Error - Specimen",
        ]
        internalCols = [col for col in internalCols if col not in df.columns]

        if internalCols:
            df[internalCols] = None
            self.recordDF[internalCols] = None

        # catching errors for fields which have known, pre-defined permissible values
        self.dropdownDF = pd.read_csv(self.dropdownOutpath.replace("_", f"{env}_all_dropdown_values"), dtype=str)

        dropdownCols = {
            "Anatomic Site": "anatomic_site",
            "Collection Container": "collection_container",
            "Collection Procedure": "collection_procedure",
            "Laterality": "laterality",
            "Pathological Status": "pathology_status",
            "Received Quality": "receive_quality",
            "Type": "specimen_type",
        }
        dropdownCols = {key: val for key, val in dropdownCols.items() if key in df.columns}

        for col in df.columns:
            if "biohazard" in col.lower():
                dropdownCols[col] = "specimen_biohazard"

        for templateCol, dropdownName in dropdownCols.items():

            errorFilt = df[templateCol].isin(self.dropdownDF[dropdownName])
            errorFilt = ~errorFilt & df[templateCol].notna()
            df.loc[errorFilt, "Critical Error - Specimen"] = df.loc[errorFilt, "Critical Error - Specimen"].apply(
                (
                    lambda x: f"{x}; Value Error in Column {templateCol}"
                    if pd.notna(x)
                    else f"Value Error in Column {templateCol}"
                )
            )

        self.recordDF.update(df)
        criticalFilt = df["Critical Error - Specimen"].notna()
        df = df.loc[~criticalFilt]

        # catching duplicate records

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
            "Initial Quantity",
            "Available Quantity",
            "Concentration",
            "Freeze/Thaw Cycles",
            "Created On",
            "Comments",
            "Collection Status",
            "Container",
            "Row",
            "Column",
            # "Position",
            "Collection Date",
            "Collection Proceedure",
            "Collection Container",
            "Collector",
            "Received Date",
            "Received Quality",
            "Receiver",
        ]

        colCheck = ["External", "Specimen"]

        specimenSub1 = [
            col for col in df.columns.values if col in specimenSub or any([checkVal in col for checkVal in colCheck])
        ]

        df = df.drop_duplicates(subset=specimenSub1)

        specimenSub2 = ["CP Short Title", "Visit Name", "Specimen Label"]
        duplicateFilt = df.duplicated(subset=specimenSub2, keep=False)

        if duplicateFilt.any():

            # duplicateFilt = specimenDF.index.isin(duplicatedRecords.index)
            df = df.loc[~duplicateFilt].copy()

            duplicateFilt = (~self.recordDF.duplicated(subset=specimenSub1)) & (
                self.recordDF.duplicated(subset=specimenSub2, keep=False)
            )

            if duplicateFilt.any():
                self.recordDF.loc[duplicateFilt, "Duplicate Specimen"] = "True"

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def matchSpecimens(self, specimenDF):
        """Attempts to match specimens in the data to existing specimens in OpS"""

        matchFilt = (specimenDF["Specimen Label"].notna()) & (specimenDF["Specimen ID"].isna())

        if matchFilt.any():

            print("Matching Specimens")

            t1 = time.perf_counter()

            matchDF = specimenDF.loc[matchFilt].copy()
            matchSpecimenDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
            matchedDF = pd.concat([self.matchSpecimenLabel(df) for df in matchSpecimenDF])

            # instead of below if/else, maybe just specimenDF.update(matchedDF) -- should avoid needing to split into unmatched and recombine, etc.

            if not specimenDF.loc[~matchFilt].empty:
                unmatchedDF = specimenDF.loc[~matchFilt].copy()
                specimenDF = pd.concat([matchedDF, unmatchedDF])

            else:
                specimenDF = matchedDF

            elapsed = time.perf_counter() - t1
            size = len(matchDF.index)
            print(f"Time Elapsed to Match and Concat Specimens: {elapsed}")
            print(f"Number of Specimens: {size}")
            print(f"Time per Specimen: {elapsed/size}")

        # previously filtered for lineage == new, but derivatives can be parents of aliquots, etc.
        matchFilt = (specimenDF["Parent Specimen Label"].notna()) & (specimenDF["Parent ID"].isna())

        if matchFilt.any():
            specimenDF.loc[matchFilt] = specimenDF.loc[matchFilt].apply(
                self.populateParentInfo, args=[specimenDF], axis=1
            )

        matchFilt = (specimenDF["Parent Specimen Label"].notna()) & (specimenDF["Parent ID"].isna())

        if matchFilt.any():

            print("Matching Remaining Parent Specimens")

            t1 = time.perf_counter()

            matchDF = specimenDF.loc[matchFilt].copy()
            matchDF.drop_duplicates(subset=["Parent Specimen Label"], inplace=True)
            matchParentDF = self.chunkDF(matchDF, chunkSize=self.lookUpChunkSize)
            matchedDF = pd.concat([self.matchParentSpecimenLabel(df) for df in matchParentDF])

            specimenDF.update(matchedDF)

            elapsed = time.perf_counter() - t1
            size = len(matchDF.index)
            print(f"Time Elapsed to Match and Concat Unmatched Parents: {elapsed}")
            print(f"Number of Unmatched Parents: {size}")
            print(f"Time per Parent Record: {elapsed/size}")

        matchFilt = (specimenDF["Parent Specimen Label"].notna()) & (specimenDF["Parent ID"].isna())

        if matchFilt.any():

            specimenDF.loc[matchFilt] = specimenDF.loc[matchFilt].apply(
                self.populateParentInfo, args=[specimenDF], axis=1
            )

            self.recordDF.loc[specimenDF.index, "Parent ID"] = specimenDF["Parent ID"]
            self.recordDF.to_csv(self.currentItem, index=False)

        return specimenDF

    #  ---------------------------------------------------------------------

    def matchSpecimenLabel(self, data):
        """Uses specimen label to attempt to match an existing specimen in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Specimen Label"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.specimenMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        specimenDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        specimenDetails.set_index("Specimen Label", inplace=True)

        ind = data.index.copy()
        data.set_index("Specimen Label", inplace=True)
        data.update(specimenDetails)
        data.reset_index(inplace=True)
        data.index = ind

        cols = ["Specimen ID", "Specimen Original CP"]
        self.recordDF.loc[data.index, cols] = data[cols]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def matchParentSpecimenLabel(self, data):
        """Uses parent specimen label to attempt to match an existing parent specimen in OpS; Required for cases where parent specimen exists in OpS but is not given in data"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Parent Specimen Label"].map((lambda x: f'"{x}"')).copy()
        matchVals = ", ".join(labels.to_list())

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {
                        "cpId": -1,
                        "aql": self.parentMatchAQL.replace("_", matchVals),
                    },
                    unpicklable=False,
                ),
            )

        specimenDetails = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        specimenDetails.set_index("Parent Specimen Label", inplace=True)

        ind = data.index.copy()
        data.set_index("Parent Specimen Label", inplace=True)
        data.update(specimenDetails)
        data.reset_index(inplace=True)
        data.index = ind

        self.recordDF.loc[data.index, "Parent ID"] = data["Parent ID"]
        self.recordDF.to_csv(self.currentItem, index=False)

        return data

    #  ---------------------------------------------------------------------

    def populateParentInfo(self, data, specimenDF):
        """Populates the required parent specimen info into the child specimen's record"""

        filt = (specimenDF["Specimen Label"] == data["Parent Specimen Label"]) & (specimenDF["Specimen ID"].notna())

        if filt.any():
            data["Parent ID"] = specimenDF.loc[filt, "Specimen ID"].unique()[0]

        else:
            filt = (specimenDF["Parent Specimen Label"] == data["Parent Specimen Label"]) & (
                specimenDF["Parent ID"].notna()
            )

            if filt.any():
                data["Parent ID"] = specimenDF.loc[filt, "Parent ID"].unique()[0]

        return data

    #  ---------------------------------------------------------------------

    def specimenNoMatchValidation(self, df):
        """Enforces the more stringent rules that come with needing to create a specimen (i.e. if they fail to match an existing specimen in OpS)"""

        # catching errors in fields which are required for Create
        specimenCritical = [
            "CP Short Title",
            "Visit Name",
            "Type",
        ]

        # looks different than other cases because have to account for instances where Type == "not specified" and the Class field is empty, as it is required in that case
        # and when parent specimen label is missing but lineage is new, since that is also permissible
        criticalFilt = (
            df[specimenCritical].isna().any(axis=1)
            | ((df["Type"].str.lower() == "not specified") & (df["Class"].isna()))
            | ((df["Parent Specimen Label"].isna()) & (df["Lineage"].str.lower() != "new"))
        )
        criticalErrors = df[criticalFilt].copy()

        if not criticalErrors.empty:

            criticalFilt = df.index.isin(criticalErrors.index)
            df.loc[
                criticalFilt, "Critical Error - Specimen"
            ] = f"Value Error in Critical Column(s) [{', '.join(specimenCritical)}]"
            self.recordDF.update(df)
            df = df.loc[~criticalFilt]

        self.recordDF.to_csv(self.currentItem, index=False)
        return df

    #  ---------------------------------------------------------------------

    def buildSpecimenObj(self, data):
        """Constructs the specimen object which will ultimately be serialized and uploaded"""

        specimen = Generic()

        specimenMap = {
            "label": "Specimen Label",
            "specimenClass": "Class",
            "type": "Type",
            "anatomicSite": "Anatomic Site",
            "pathology": "Pathological Status",
            "lineage": "Lineage",
            "initialQty": "Initial Quantity",
            "availableQty": "Available Quantity",
            "laterality": "Laterality",
            "collectionStatus": "Collection Status",
            "activityStatus": "Specimen Activity Status",
            "createdOn": "Created On",
            "comments": "Specimen Comments",
            "concentration": "Concentration",
            "barcode": "Barcode",
            "visitName": "Visit Name",
            "Id": "Specimen ID",
        }

        specimenData = {key: data.get(val) for key, val in specimenMap.items() if pd.notna(data.get(val))}

        for key, val in specimenData.items():
            setattr(specimen, key, val)

        if pd.notna(data.get("Visit ID")):
            specimen.visitId = str(data["Visit ID"]).split(".")[0]

        if pd.notna(data.get("Parent ID")):
            specimen.parentId = str(data["Parent ID"]).split(".")[0]

        storageMap = {"name": "Container", "positionY": "Row", "positionX": "Column"}

        storageLocation = {
            key: (int(data.get(val)) if isinstance(data.get(val), float) else data.get(val))
            for key, val in storageMap.items()
            if pd.notna(data.get(val))
        }

        if storageLocation:
            specimen.storageLocation = storageLocation

        biohazards = [data.get(col) for col in data.keys() if "biohazard" in col.lower() and pd.notna(data.get(col))]

        if biohazards:
            specimen.biohazards = biohazards

        collectionEventMap = {
            "user": "Collector",
            "time": "Collection Date",
            "container": "Collection Container",
            "procedure": "Collection Procedure",
            "comments": "Collection Comments",
        }

        collectionEvent = {key: data.get(val) for key, val in collectionEventMap.items() if pd.notna(data.get(val))}

        if collectionEvent:
            specimen.collectionEvent = collectionEvent

        receivedEventMap = {
            "user": "Receiver",
            "time": "Received Date",
            "receivedQuality": "Received Quality",
            "comments": "Received Comments",
        }

        receivedEvent = {key: data.get(val) for key, val in receivedEventMap.items() if pd.notna(data.get(val))}

        if receivedEvent:
            specimen.receivedEvent = receivedEvent

        if specimen.lineage not in ["Aliquot", "aliquot"]:

            formExten = self.formExtension[data["CP Short Title"]]

            if formExten:
                extensionDetail = self.buildExtensionDetail(formExten, data)

            #  since it's required for specimen class, and attrsMap defaults to an empty dict, go ahead and make an empty Extension instance
            else:
                extensionDetail = Extension()

            specimen.extensionDetail = extensionDetail

        # for aliquots which need to be created, can push them as an array, otherwise, must be a single object to update a specific specimen
        elif pd.isna(data.get("Specimen ID")):

            if pd.notna(data.get("Quantity")):
                specimen = [specimen for val in range(int(data["Quantity"]))]

            else:
                specimen = [specimen]

        data["Specimen Obj"] = specimen

        return data

    #  ---------------------------------------------------------------------

    def updateSpecimens(self, data):
        """Pushes data associated with specimens matched in the CP of interest (hence update)"""

        async def updateLogic(data):

            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.put(
                        data.loc[ind, "Specimen Url"],
                        data=jp.encode(data.loc[ind, "Specimen Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            specimens = [
                ([reply.json()[0]["code"], reply.json()[0]["message"]] if reply.is_error else reply.status_code)
                for reply in replies
            ]

            print(f"Specimen Update Results: {specimens}")

            data["Specimen Upload Status"] = specimens
            data["Specimen Upload Status"] = data["Specimen Upload Status"].map(
                (lambda x: f"Specimen Update Result: {x}")
            )

            self.recordDF.loc[data.index, "Specimen Upload Status"] = data["Specimen Upload Status"]
            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(updateLogic(data))

    #  ---------------------------------------------------------------------

    def createSpecimens(self, data):
        """Pushes data associated with specimens which failed to match in CP of interest in order to create them"""

        async def updateLogic(data):
            token = self.authTokens[self.currentEnv]
            headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

            async with httpx.AsyncClient(headers=headers, timeout=20) as client:

                tasks = [
                    client.post(
                        data.loc[ind, "Specimen Url"],
                        data=jp.encode(data.loc[ind, "Specimen Obj"], unpicklable=False),
                    )
                    for ind in data.index
                ]
                replies = await asyncio.gather(*tasks)

            specimens = [
                (
                    reply.json()["label"]
                    if "label" in reply.json()
                    else reply.json()[0]["label"]
                    if "label" in reply.json()[0]
                    else [reply.json()[0]["code"], reply.json()[0]["message"]]
                    if reply.is_error
                    else reply.json()
                )
                for reply in replies
            ]

            print(f"Specimen Create Results: {specimens}")

            data["Specimen Label"] = specimens

            filt = data["Specimen Label"].map((lambda x: not isinstance(x, list)))
            self.recordDF.loc[data.loc[filt].index, "Specimen Label"] = data.loc[filt, "Specimen Label"]

            data["Specimen Label"] = data["Specimen Label"].map((lambda x: f"Specimen Create Result: {x}"))
            self.recordDF.loc[data.index, "Specimen Upload Status"] = data["Specimen Label"]

            self.recordDF.to_csv(self.currentItem, index=False)

            return data

        return asyncio.run(updateLogic(data))

    #  ---------------------------------------------------------------------

    def arrayUpload(self, dfDict):
        """Performs upload of array data from an array template"""

        for arrayName, (df, self.currentEnv) in dfDict.items():

            arrayDF = self.arrayPreMatchValidation(df)

            filt = arrayDF["Array ID"].notna()

            #  maybe a good idea to make sure the array name is matched as well before adding the ID to those missing IDs
            if filt.any():
                arrayDF["Array ID"].loc[~filt] = arrayDF["Array ID"].loc[filt].unique()[0]

            else:
                arrayDF["Array ID"] = self.matchArray(arrayName)

            arrayObj = self.buildArrayObj(arrayDF.iloc[0])

            reset = None

            if arrayObj.status.lower() == "completed":
                reset = True
                arrayObj.status = "PENDING"

            hasID = hasattr(arrayObj, "id")

            base = (
                self.baseURL.replace("_", "")
                if self.currentEnv == "prod"
                else self.baseURL.replace("_", self.currentEnv)
            )

            if hasID:
                arrayID = arrayObj.id
                url = f"{base}{self.arrayExtension}{arrayID}"
                arrayDF["Array Url"] = url
                self.updateArray(arrayObj, url)

            else:
                arrayID = self.createArray(arrayObj, base)

            url = f"{base}{self.arrayExtension}{arrayID}/cores"

            arrayDF["Core Details"] = arrayDF.apply(
                (
                    lambda x: {
                        "specimen": {
                            "label": x["Cores Detail#Specimen#Specimen Label"],
                            "cpShortTitle": x["Cores Detail#Specimen#CP Short Title"],
                        },
                        "rowStr": x["Cores Detail#Row"],
                        "columnStr": x["Cores Detail#Column"],
                    }
                ),
                axis=1,
            )

            cores = Generic()
            cores.cores = arrayDF["Core Details"].to_list()

            self.populateArray(cores, url, arrayName)

            if reset:
                arrayObj.status = "COMPLETED"
                url = arrayDF["Array Url"].unique()[0]
                self.updateArray(arrayObj, url)

    #  ---------------------------------------------------------------------

    def arrayPreMatchValidation(self, df):
        """Performs validation of array specific data to catch any errors and/or duplicates"""

        print("Validating Arrays/Cores")

        internalCols = ["Array ID", "Critical Error - Array"]
        internalCols = [col for col in internalCols if col not in df.columns]

        if internalCols:
            df[internalCols] = None
            self.recordDF[internalCols] = None

        # specimen/core required fields omitted in case only bulk creating empty arrays initially
        arrayCritical = [
            "Name",
            "Rows",
            "Columns",
            "Row Labeling Scheme",
            "Column Labeling Scheme",
            "Core Diameter (mm)",
            "Creation Date",
            "Status",
        ]

        criticalFilt = df[arrayCritical].isna().any(axis=1)
        criticalErrors = df[criticalFilt].copy()

        if not criticalErrors.empty:

            criticalFilt = df.index.isin(criticalErrors.index)
            df.loc[criticalFilt, "Critical Error - Array"] = "True"
            self.recordDF.update(df)
            df = df.loc[~criticalFilt]

        arraySub = [
            "Name",
            "Length (mm)",
            "Width (mm)",
            "Thickness (mm)",
            "Rows",
            "Columns",
            "Row Labeling Scheme",
            "Column Labeling Scheme",
            "Core Diameter (mm)",
            "Creation Date",
            "Quality",
            "Status",
            "Comments",
            "Cores Detail#Row",
            "Cores Detail#Column",
            "Cores Detail#Specimen#CP Short Title",
            "Cores Detail#Specimen#Specimen Label",
        ]

        arraySub1 = [col for col in df.columns.values if col in arraySub]

        df = df.drop_duplicates(subset=arraySub1)

        arraySub2 = [
            "Name",
            "Creation Date",
            "Cores Detail#Row",
            "Cores Detail#Column",
            "Cores Detail#Specimen#Specimen Label",
        ]

        duplicateFilt = df.duplicated(subset=arraySub2, keep=False)

        if duplicateFilt.any():

            df = df.loc[~duplicateFilt].copy()

            duplicateFilt = (~self.recordDF.duplicated(subset=arraySub1)) & (
                self.recordDF.duplicated(subset=arraySub2, keep=False)
            )

            if duplicateFilt.any():
                self.recordDF.loc[duplicateFilt, "Duplicate Core"] = "True"

        cols = [col for col in self.recordDF.columns if "Duplicate" in col or "Critical Error" in col]

        if cols:
            self.recordDF.dropna(how="all", subset=cols).to_csv(self.currentItem, index=False)

        return df

    #  ---------------------------------------------------------------------

    def matchArray(self, arrayName):
        """Attempts to match arrays in the data to existing arrays in OpS"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.arrayExtension

        params = {"name": arrayName, "exactMatch": True}

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.get(url, params=params)

        if reply:
            arrayID = reply.json()[0]["id"]

            self.recordDF["Array ID"] = arrayID
            self.recordDF.to_csv(self.currentItem, index=False)

        else:
            arrayID = None

        return arrayID

    #  ---------------------------------------------------------------------

    def buildArrayObj(self, data):
        """Constructs the array object which will ultimately be serialized and uploaded"""

        array = Generic()

        arrayMap = {
            "name": "Name",
            "length": "Length (mm)",
            "width": "Width (mm)",
            "thickness": "Thickness (mm)",
            "numberOfRows": "Rows",
            "rowLabelingScheme": "Row Labeling Scheme",  # may need to be upper case (str.upper())
            "numberOfColumns": "Columns",
            "columnLabelingScheme": "Column Labeling Scheme",  # may need to be upper case (str.upper())
            "coreDiameter": "Core Diameter (mm)",
            "creationDate": "Creation Date",
            "status": "Status",
            "qualityControl": "Quality",
            "comments": "Comments",
            "id": "Array ID",
        }

        arrayData = {key: data.get(val) for key, val in arrayMap.items() if pd.notna(data.get(val))}

        for key, val in arrayData.items():
            setattr(array, key, val)

        array.rowLabelingScheme = array.rowLabelingScheme.upper()
        array.columnLabelingScheme = array.columnLabelingScheme.upper()

        return array

    #  ---------------------------------------------------------------------

    def updateArray(self, arrayObj, url):
        """Pushes data associated with arrays matched in OpS (hence update)"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.put(url, data=jp.encode(arrayObj, unpicklable=False))

        reply = (
            ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]]) if reply.is_error else reply.status_code
        )

        print(f"Array Update Results: {reply}")

        filt = self.recordDF["Name"] = arrayObj.name
        self.recordDF.loc[filt, "Array Update Status"] = reply
        self.recordDF.to_csv(self.currentItem, index=False)

    #  ---------------------------------------------------------------------

    def createArray(self, arrayObj, base):
        """Pushes data associated with arrays which failed to match in OpS in order to create them"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = f"{base}{self.arrayExtension}/"

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.post(url, data=jp.encode(arrayObj, unpicklable=False))

        reply = (
            reply.json()["id"]
            if "id" in reply.json()
            else reply.json()[0]["id"]
            if "id" in reply.json()[0]
            else [reply.json()[0]["code"], reply.json()[0]["message"]]
            if reply.is_error
            else reply.json()
        )

        print(f"Array Create Results: {reply}")

        filt = self.recordDF["Name"] = arrayObj.name
        self.recordDF.loc[filt, "Array ID"] = reply
        self.recordDF.to_csv(self.currentItem, index=False)

        return reply

    #  ---------------------------------------------------------------------

    def populateArray(self, coreList, url, arrayName):
        """Populates array object with the required core specimens"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}

        with httpx.Client(headers=headers, timeout=20) as client:
            reply = client.put(url, data=jp.encode(coreList, unpicklable=False))

        reply = (
            ", ".join([reply.json()[0]["code"], reply.json()[0]["message"]]) if reply.is_error else reply.status_code
        )

        print(f"Populate Array Results: {reply}")

        filt = self.recordDF["Name"] = arrayName
        self.recordDF.loc[filt, "Populate Array Status"] = reply
        self.recordDF.to_csv(self.currentItem, index=False)

    #  ---------------------------------------------------------------------
    #  NOTE Audits and related functions start here
    #  ---------------------------------------------------------------------

    def audit(self, matchPPID=False):
        """Generic audit function which attempts to audit as many files in the input folder as possible"""

        uploadTypes = ["universal", "participants", "visits", "specimens"]

        # below creates dict of dicts as follows {uploadType: {filePath: env, filePath: env}}

        validatedItems = {
            uploadType: {
                (self.inputDir + file): file.split("_")[2].lower()
                for file in os.listdir(self.inputDir)
                if file.lower().startswith("audit")
                and file.split("_")[1].lower() == uploadType
                and file.split("_")[2].lower() in self.envs.keys()
            }
            for uploadType in uploadTypes
        }

        # passing dicts of {filePath: env, filePath: env} to their respective upload functions
        # below works because the keys in uploadTypes will always exist, but the dict they link to may be empty, which will eval to False

        if validatedItems["universal"]:
            [
                self.universalAudit(self.dfImport(file, env), matchPPID)
                for file, env in tqdm(validatedItems["universal"].items(), desc="Universal Audits", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["universal"].keys()]

        if validatedItems["participants"]:
            [
                self.participantAudit(self.dfImport(file, env), matchPPID)
                for file, env in tqdm(validatedItems["participants"].items(), desc="Participant Audits", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["participants"].keys()]

        if validatedItems["visits"]:
            [
                self.visitAudit(self.dfImport(file, env))
                for file, env in tqdm(validatedItems["visits"].items(), desc="Visit Audits", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["visits"].keys()]

        if validatedItems["specimens"]:
            [
                self.specimenAudit(self.dfImport(file, env))
                for file, env in tqdm(validatedItems["specimens"].items(), desc="Specimen Audits", unit=" Files")
            ]
            [shutil.move(file, self.outputDir) for file in validatedItems["specimens"].keys()]

    #  ---------------------------------------------------------------------

    def universalAudit(self, dfDict, matchPPID):
        """Wrapper around the audit functions for the three main import types which compose the OpS "Master Specimen" template; Audits data from a universal template"""

        self.participantAudit(dfDict, matchPPID)
        self.visitAudit(dfDict)
        self.specimenAudit(dfDict)

    #  ---------------------------------------------------------------------

    def participantAudit(self, dfDict, matchPPID):
        """Performs audit of participant data given in the participant template being audited"""

        # maybe do this in a list comprehension instead and concat all compared DFs into one per CSV, since df import splits single CSV in to DFs by CPs therein
        allCompared = []

        outPath = self.currentItem.split("/")
        fileName = "_".join(outPath[-1].split("_")[2:])
        fileName = f"Participants_with_Audit_Issues_{fileName}"
        outPath = f"{self.outputDir}/{fileName}"

        for shortTitle, (df, env) in dfDict.items():

            print(f"On {shortTitle}")

            self.currentEnv = env
            participantDF = self.participantPreMatchValidation(df, env)
            participantDF = self.matchParticipants(participantDF, shortTitle, matchPPID)

            filt = participantDF["Participant ID"].isna()
            unmatchedParticipants = participantDF.loc[filt].copy()
            participantDF = participantDF.loc[~filt].copy()

            if participantDF.empty:
                if not unmatchedParticipants.empty:
                    unmatchedParticipants.to_csv(outPath, index=False)
                continue

            uploadDataForComparison = participantDF.drop(columns=["CP ID", "DTs Processed", "Participant Original CP"])

            opsDataForComparison = self.chunkDF(participantDF, chunkSize=self.lookUpChunkSize)
            opsDataForComparison = pd.concat([self.getOpSParticipantData(df, env) for df in opsDataForComparison])

            # below subsetting is required because OpS can have limitless cases where one participant is in
            # multiple CPs and not necessarily the CP(s) of interest either. leaving this unaddressed leads to
            # ValueError: Can only compare identically-labeled Series objects

            subsetFilt = (
                opsDataForComparison["Participant ID"].isin(uploadDataForComparison["Participant ID"].to_list())
            ) & (opsDataForComparison["CP Short Title"] == shortTitle)
            opsDataSubset = opsDataForComparison.loc[subsetFilt]

            subsetFiltTwo = (
                opsDataForComparison["Participant ID"].isin(uploadDataForComparison["Participant ID"].to_list())
            ) & ~(opsDataForComparison["Participant ID"].isin(opsDataSubset["Participant ID"].to_list()))
            opsDataSubsetTwo = opsDataForComparison.loc[subsetFiltTwo]

            opsDataForComparison = pd.concat([opsDataSubset, opsDataSubsetTwo])

            filt = (opsDataForComparison["Participant ID"].duplicated()) & (
                opsDataForComparison["CP Short Title"] != shortTitle
            )
            opsDataForComparison = opsDataForComparison.loc[~filt]

            dropCols = [col for col in opsDataForComparison.columns if col not in uploadDataForComparison.columns]
            opsDataForComparison = opsDataForComparison.drop(columns=dropCols)

            addCols = [col for col in uploadDataForComparison.columns if col not in opsDataForComparison.columns]
            opsDataForComparison[addCols] = None

            sortedCols = sorted(opsDataForComparison.columns)
            opsDataForComparison = opsDataForComparison[sortedCols]

            sortedCols = sorted(uploadDataForComparison.columns)
            uploadDataForComparison = uploadDataForComparison[sortedCols]

            filt = uploadDataForComparison["Participant ID"].isin(opsDataForComparison["Participant ID"])
            unmatchedParticipants = unmatchedParticipants.append(uploadDataForComparison.loc[~filt])

            uploadDataForComparison = uploadDataForComparison.loc[filt]

            if uploadDataForComparison.equals(opsDataForComparison):
                continue

            # these must be done after the above column unification, otherwise Participant ID is not a column, it's an index and will be dropped
            opsDataForComparison.set_index(keys=["Participant ID"], inplace=True)
            opsDataForComparison.sort_index(inplace=True)

            opsDataForComparison["First Name"] = opsDataForComparison["First Name"].str.title()
            opsDataForComparison["Last Name"] = opsDataForComparison["Last Name"].str.title()
            # opsDataForComparison.insert(0, "Source", (["OpenSpecimen"] * len(opsDataForComparison)))

            uploadDataForComparison.set_index(keys=["Participant ID"], inplace=True)
            uploadDataForComparison.sort_index(inplace=True)

            uploadDataForComparison["First Name"] = uploadDataForComparison["First Name"].str.title()
            uploadDataForComparison["Last Name"] = uploadDataForComparison["Last Name"].str.title()
            # uploadDataForComparison.insert(0, "Source", (["CSV"] * len(uploadDataForComparison)))

            comparedDF = uploadDataForComparison.compare(opsDataForComparison, align_axis=0)
            comparedDF.index = comparedDF.index.set_levels(["CSV", "OpenSpecimen"], level=1)
            comparedDF.reset_index(level=0, inplace=True)

            referenceCols = {"CSV CP Short Title": "CP Short Title", "CSV PPID": "PPID"}

            for key, val in referenceCols.items():

                comparedDF[key] = comparedDF["Participant ID"].map(
                    (lambda x: participantDF.loc[(participantDF["Participant ID"] == x), val].item())
                )

            comparedDF.drop(columns=["Participant ID"], inplace=True)

            # NOTE below meant to reorder columns such that the first three are CP Short Title, Specimen Label, and Visit Name
            referenceCols = [val for val in referenceCols.keys()]
            newCols = [col for col in comparedDF.columns if col not in referenceCols]
            orderedCols = referenceCols + newCols
            comparedDF = comparedDF[orderedCols]

            if not unmatchedParticipants.empty:
                unmatchedParticipants["Critical Error - Participant"] = "Not found in OpenSpecimen"
                unmatchedParticipants.index = ["CSV"] * len(unmatchedParticipants)
                comparedDF = comparedDF.append(unmatchedParticipants)

            if not comparedDF.empty:
                comparedDF = comparedDF.dropna(axis=1, how="all")
                allCompared.append(comparedDF)

        allCompared = pd.concat(allCompared)
        allCompared.to_csv(outPath)

    #  ---------------------------------------------------------------------

    def getOpSParticipantData(self, data, env):
        """Retrieves the OpS data associated with participants given in the participant template being audited"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Participant ID"].copy()
        matchVals = ", ".join(labels.to_list())

        aql = self.participantAuditAQL.replace("*", matchVals)
        pafAQL = self.generatePAFAQL(data, env)

        if pafAQL:
            aql = aql.replace("$", f", {pafAQL}")
        else:
            aql = aql.replace("$", "")

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {"cpId": -1, "aql": aql, "wideRowMode": "DEEP"},
                    unpicklable=False,
                ),
            )

        data = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        data.dropna(axis=1, how="all", inplace=True)

        columns = {
            column: (
                column.replace("^", "1")
                if not column[-1].isdigit()
                else column[:-4].replace("^", f"{int(column[-1]) + 1}")
            )
            for column in data.columns
            if "^" in column
        }
        data.rename(columns=columns, inplace=True)

        columns = {column: ("#".join(column.split("# "))) for column in data.columns if "# " in column}
        data.rename(columns=columns, inplace=True)

        columns = {
            column: ("#".join(column.split("#")[1:])) for column in data.columns if column.startswith("Participant#")
        }
        data.rename(columns=columns, inplace=True)

        return data

    #  ---------------------------------------------------------------------

    def generatePAFAQL(self, df, env):
        """Constructs the AQL used in the getOpSParticipantData function"""

        pafAQL = None
        fields = []
        subformFieldsList = []
        subformNamesList = []

        df["CP ID"] = df["CP ID"].astype(str)

        cpID = df["CP ID"].unique()[0].split(".")[0] if "." in df["CP ID"].unique()[0] else df["CP ID"].unique()[0]
        params = {"cpId": cpID}
        formExten = self.getFormExtension(self.pafExtension, params=params)

        if formExten:
            formDF = self.setFormDF()
            compactName = formExten["formName"]
            filt = (formDF[f"{env}ShortName"] == compactName) & (formDF["formName"].notna())
            formName = formDF.loc[filt, "formName"].item()

            fieldDF = self.setFieldDF()

            filt = (fieldDF["formName"] == formName) & (fieldDF[f"{env}UDN"].notna()) & (fieldDF["isSubForm"] == False)
            fields = fieldDF.loc[filt, f"{env}UDN"].to_list()

            filt = (
                (fieldDF["formName"] == formName)
                & (fieldDF[f"{env}SubFormUDN"].notna())
                & (fieldDF[f"{env}UDN"].notna())
                & (fieldDF["isSubForm"] == True)
                & (fieldDF["isSubField"] == True)
            )
            subformFields = fieldDF.loc[filt, [f"{env}SubFormUDN", f"{env}UDN", f"{env}SubFormName", "fieldName"]]

            subformFields["unifiedAQL"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormUDN']}.{x[f'{env}UDN']}"), axis=1
            )
            subformFieldsList = subformFields["unifiedAQL"].to_list()

            subformFields["unifiedHeader"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormName']}.{x['fieldName']}"), axis=1
            )
            subformNamesList = subformFields["unifiedHeader"].to_list()

        fields = [f"Participant.customFields.{compactName}.{fieldName}" for fieldName in fields]

        subformFields = []
        for subformName, subfieldName in zip(subformNamesList, subformFieldsList):
            subformFields.append(
                f'Participant.customFields.{compactName}.{subfieldName} as "{formName}#{subformName.split(".")[0]}#^#{subformName.split(".")[1]}"'
            )

        fields = fields + subformFields

        if fields:
            pafAQL = ", ".join(fields)

        return pafAQL

    #  ---------------------------------------------------------------------

    def visitAudit(self, dfDict):
        """Performs audit of visit data given in the visit template being audited"""

        # maybe do this in a list comprehension instead and concat all compared DFs into one per CSV, since df import splits single CSV in to DFs by CPs therein
        allCompared = []

        outPath = self.currentItem.split("/")
        fileName = "_".join(outPath[-1].split("_")[2:])
        fileName = f"Visits_with_Audit_Issues_{fileName}"
        outPath = f"{self.outputDir}/{fileName}"

        for shortTitle, (df, env) in dfDict.items():

            self.currentEnv = env
            visitDF = self.visitPreMatchValidation(df, env)
            visitDF = self.matchVisits(visitDF)

            filt = visitDF["Visit ID"].isna()
            unmatchedVisits = visitDF.loc[filt].copy()
            visitDF = visitDF.loc[~filt].copy()

            if visitDF.empty:
                if not unmatchedVisits.empty:
                    unmatchedVisits.to_csv(outPath, index=False)
                continue

            opsDataForComparison = self.chunkDF(visitDF, chunkSize=self.lookUpChunkSize)
            opsDataForComparison = pd.concat([self.getOpSVisitData(df, env) for df in opsDataForComparison])

            uploadDataForComparison = visitDF.drop(columns=["CP ID", "DTs Processed", "Visit Original CP"])

            dropCols = [col for col in opsDataForComparison.columns if col not in uploadDataForComparison.columns]
            opsDataForComparison = opsDataForComparison.drop(columns=dropCols)

            addCols = [col for col in uploadDataForComparison.columns if col not in opsDataForComparison.columns]
            opsDataForComparison[addCols] = None

            sortedCols = sorted(opsDataForComparison.columns)
            opsDataForComparison = opsDataForComparison[sortedCols]

            sortedCols = sorted(uploadDataForComparison.columns)
            uploadDataForComparison = uploadDataForComparison[sortedCols]

            filt = uploadDataForComparison["Visit ID"].isin(opsDataForComparison["Visit ID"])
            unmatchedVisits = unmatchedVisits.append(uploadDataForComparison.loc[~filt])

            filt = filt & (uploadDataForComparison["Visit ID"].notna())
            uploadDataForComparison = uploadDataForComparison.loc[filt]

            if uploadDataForComparison.equals(opsDataForComparison):
                continue

            # these must be done after the above column unification, otherwise Visit ID is not a column, it's an index and will be dropped
            opsDataForComparison.set_index(keys=["Visit ID"], inplace=True)
            opsDataForComparison.sort_index(inplace=True)

            uploadDataForComparison.set_index(keys=["Visit ID"], inplace=True)
            uploadDataForComparison.sort_index(inplace=True)

            comparedDF = uploadDataForComparison.compare(opsDataForComparison, align_axis=0)
            comparedDF.index = comparedDF.index.set_levels(["CSV", "OpenSpecimen"], level=1)
            comparedDF.reset_index(level=0, inplace=True)

            # referenceCols = ["CSV CP Short Title", "CSV PPID", "CSV Visit Name"]

            # for col in referenceCols:

            #     comparedDF[col] = comparedDF["Visit ID"].map(
            #         (lambda x: visitDF.loc[(visitDF["Visit ID"] == x), col].item())
            #     )

            referenceCols = {
                "CSV CP Short Title": "CP Short Title",
                "CSV PPID": "PPID",
                "CSV Visit Name": "Visit Name",
            }

            for key, val in referenceCols.items():

                comparedDF[key] = comparedDF["Visit ID"].map(
                    (lambda x: visitDF.loc[(visitDF["Visit ID"] == x), val].item())
                )

            comparedDF.drop(columns=["Visit ID"], inplace=True)

            # NOTE below meant to reorder columns such that the first three are CP Short Title, Specimen Label, and Visit Name

            referenceCols = list(referenceCols.keys())
            newCols = [col for col in comparedDF.columns if col not in referenceCols]
            orderedCols = referenceCols + newCols
            comparedDF = comparedDF[orderedCols]

            if not unmatchedVisits.empty:
                unmatchedVisits["Critical Error - Visit"] = "Not found in OpenSpecimen"
                unmatchedVisits.index = ["CSV"] * len(unmatchedVisits.index)
                comparedDF = comparedDF.append(unmatchedVisits)

            if not comparedDF.empty:
                comparedDF = comparedDF.dropna(axis=1, how="all")
                allCompared.append(comparedDF)

        allCompared = pd.concat(allCompared)
        allCompared.to_csv(outPath)

    #  ---------------------------------------------------------------------

    def getOpSVisitData(self, data, env):
        """Retrieves the OpS data associated with visits given in the visit template being audited"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Visit ID"].copy()
        matchVals = ", ".join(labels.to_list())

        aql = self.visitAuditAQL.replace("*", matchVals)
        vafAQL = self.generateVAFAQL(data, env)

        if vafAQL:
            aql = aql.replace("$", f", {vafAQL}")
        else:
            aql = aql.replace("$", "")

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {"cpId": -1, "aql": aql, "wideRowMode": "DEEP"},
                    unpicklable=False,
                ),
            )

        data = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        data.dropna(axis=1, how="all", inplace=True)

        columns = {
            column: (
                column.replace("^", "1")
                if not column[-1].isdigit()
                else column[:-4].replace("^", f"{int(column[-1]) + 1}")
            )
            for column in data.columns
            if "^" in column
        }

        data.rename(columns=columns, inplace=True)

        columns = {column: ("#".join(column.split("# "))) for column in data.columns if "# " in column}

        data.rename(columns=columns, inplace=True)

        return data

    #  ---------------------------------------------------------------------

    def generateVAFAQL(self, df, env):
        """Constructs the AQL used in the getOpSVisitData function"""

        vafAQL = None
        fields = []
        subformFieldsList = []
        subformNamesList = []

        cpID = df["CP ID"].unique()[0].split(".")[0] if "." in df["CP ID"].unique()[0] else df["CP ID"].unique()[0]
        params = {"cpId": cpID}
        formExten = self.getFormExtension(self.vafExtension, params=params)

        if formExten:
            formDF = self.setFormDF()
            compactName = formExten["formName"]
            filt = (formDF[f"{env}ShortName"] == compactName) & (formDF["formName"].notna())
            formName = formDF.loc[filt, "formName"].item()

            fieldDF = self.setFieldDF()

            filt = (fieldDF["formName"] == formName) & (fieldDF[f"{env}UDN"].notna()) & (fieldDF["isSubForm"] == False)
            fields = fieldDF.loc[filt, f"{env}udn"].to_list()

            filt = (
                (fieldDF["formName"] == formName)
                & (fieldDF[f"{env}SubFormUDN"].notna())
                & (fieldDF[f"{env}UDN"].notna())
                & (fieldDF["isSubForm"] == True)
                & (fieldDF["isSubField"] == True)
            )
            subformFields = fieldDF.loc[filt, [f"{env}SubFormUDN", f"{env}UDN", f"{env}SubFormName", "fieldName"]]

            subformFields["unifiedAQL"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormUDN']}.{x[f'{env}UDN']}"), axis=1
            )
            subformFieldsList = subformFields["unifiedAQL"].to_list()

            subformFields["unifiedHeader"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormName']}.{x['fieldName']}"), axis=1
            )
            subformNamesList = subformFields["unifiedHeader"].to_list()

        fields = [f"SpecimenCollectionGroup.customFields.{compactName}.{fieldName}" for fieldName in fields]

        subformFields = []
        for subformName, subfieldName in zip(subformNamesList, subformFieldsList):
            subformFields.append(
                f'SpecimenCollectionGroup.customFields.{compactName}.{subfieldName} as "{formName}#{subformName.split(".")[0]}#^#{subformName.split(".")[1]}"'
            )

        fields = fields + subformFields

        if fields:
            vafAQL = ", ".join(fields)

        return vafAQL

    #  ---------------------------------------------------------------------

    def specimenAudit(self, dfDict):
        """Performs audit of specimen data given in the specimen template being audited"""

        # maybe do this in a list comprehension instead and concat all compared DFs into one per CSV, since df import splits single CSV in to DFs by CPs therein
        allCompared = []

        outPath = self.currentItem.split("/")
        fileName = "_".join(outPath[-1].split("_")[2:])
        fileName = f"Specimens_with_Audit_Issues_{fileName}"
        outPath = f"{self.outputDir}/{fileName}"

        for shortTitle, (df, env) in dfDict.items():

            self.currentEnv = env
            specimenDF = self.specimenPreMatchValidation(df, env)
            specimenDF = self.matchSpecimens(specimenDF)

            filt = specimenDF["Specimen ID"].isna()
            unmatchedSpecimens = specimenDF.loc[filt].copy()
            specimenDF = specimenDF.loc[~filt].copy()

            if specimenDF.empty:
                if not unmatchedSpecimens.empty:
                    unmatchedSpecimens.to_csv(outPath, index=False)
                continue

            opsDataForComparison = self.chunkDF(specimenDF, chunkSize=self.lookUpChunkSize)
            opsDataForComparison = pd.concat([self.getOpSSpecimenData(df, env) for df in opsDataForComparison])

            uploadDataForComparison = specimenDF.drop(
                columns=["CP ID", "DTs Processed", "Specimen Original CP", "Parent ID"]
            )

            dropCols = [col for col in opsDataForComparison.columns if col not in uploadDataForComparison.columns]
            opsDataForComparison = opsDataForComparison.drop(columns=dropCols)

            addCols = [col for col in uploadDataForComparison.columns if col not in opsDataForComparison.columns]
            opsDataForComparison[addCols] = None

            sortedCols = sorted(opsDataForComparison.columns)
            opsDataForComparison = opsDataForComparison[sortedCols]

            sortedCols = sorted(uploadDataForComparison.columns)
            uploadDataForComparison = uploadDataForComparison[sortedCols]

            filt = uploadDataForComparison["Specimen ID"].isin(opsDataForComparison["Specimen ID"])
            unmatchedSpecimens = unmatchedSpecimens.append(uploadDataForComparison.loc[~filt])

            filt = filt & (uploadDataForComparison["Specimen ID"].notna())
            uploadDataForComparison = uploadDataForComparison.loc[filt]

            if uploadDataForComparison.equals(opsDataForComparison):
                continue

            # these must be done after the above column unification, otherwise Specimen ID is not a column, it's an index and will be dropped
            opsDataForComparison.set_index(keys=["Specimen ID"], inplace=True)
            opsDataForComparison.sort_index(inplace=True)

            uploadDataForComparison.set_index(keys=["Specimen ID"], inplace=True)
            uploadDataForComparison.sort_index(inplace=True)

            comparedDF = uploadDataForComparison.compare(opsDataForComparison, align_axis=0)
            comparedDF.index = comparedDF.index.set_levels(["CSV", "OpenSpecimen"], level=1)
            comparedDF.reset_index(level=0, inplace=True)

            # referenceCols = ["CSV CP Short Title", "CSV Visit Name", "CSV Specimen Label"]

            # for col in referenceCols:

            #     comparedDF[col] = comparedDF["Specimen ID"].map(
            #         (lambda x: specimenDF.loc[(specimenDF["Specimen ID"] == x), col].item())
            #     )

            referenceCols = {
                "CSV CP Short Title": "CP Short Title",
                "CSV Visit Name": "Visit Name",
                "CSV Specimen Label": "Specimen Label",
            }

            for key, val in referenceCols.items():

                comparedDF[key] = comparedDF["Specimen ID"].map(
                    (lambda x: specimenDF.loc[(specimenDF["Specimen ID"] == x), val].item())
                )

            comparedDF.drop(columns=["Specimen ID"], inplace=True)

            # NOTE below meant to reorder columns such that the first three are CP Short Title, Specimen Label, and Visit Name

            referenceCols = list(referenceCols.keys())
            newCols = [col for col in comparedDF.columns if col not in referenceCols]
            orderedCols = referenceCols + newCols
            comparedDF = comparedDF[orderedCols]

            if not unmatchedSpecimens.empty:
                unmatchedSpecimens["Critical Error - Specimen"] = "Not found in OpenSpecimen"
                unmatchedSpecimens.index = ["CSV"] * len(unmatchedSpecimens.index)
                comparedDF = comparedDF.append(unmatchedSpecimens)

            if not comparedDF.empty:
                comparedDF = comparedDF.dropna(axis=1, how="all")
                allCompared.append(comparedDF)

        allCompared = pd.concat(allCompared)
        allCompared.to_csv(outPath)

    #  ---------------------------------------------------------------------

    def getOpSSpecimenData(self, data, env):
        """Retrieves the OpS data associated with specimens given in the specimen template being audited"""

        token = self.authTokens[self.currentEnv]
        headers = {"X-OS-API-TOKEN": token, "Content-Type": "application/json"}
        url = (
            self.baseURL.replace("_", "") if self.currentEnv == "prod" else self.baseURL.replace("_", self.currentEnv)
        ) + self.queryExtension

        labels = data["Specimen ID"].copy()
        matchVals = ", ".join(labels.to_list())

        aql = self.specimenAuditAQL.replace("*", matchVals)
        safAQL = self.generateSAFAQL(data, env)

        if safAQL:
            aql = aql.replace("$", f", {safAQL}")
        else:
            aql = aql.replace("$", "")

        with httpx.Client(headers=headers, timeout=20) as client:

            reply = client.post(
                url,
                data=jp.encode(
                    {"cpId": -1, "aql": aql, "wideRowMode": "DEEP"},
                    unpicklable=False,
                ),
            )

        data = pd.DataFrame(data=reply.json()["rows"], columns=reply.json()["columnLabels"], dtype=str)
        # data.dropna(axis=1, how="all", inplace=True)

        columns = {
            column: (
                column.replace("^", "1")
                if not column[-1].isdigit()
                else column[:-4].replace("^", f"{int(column[-1]) + 1}")
            )
            for column in data.columns
            if "^" in column
        }

        data.rename(columns=columns, inplace=True)

        columns = {column: ("#".join(column.split("# "))) for column in data.columns if "# " in column}

        data.rename(columns=columns, inplace=True)

        # print(data.columns)
        # quit()

        return data

    #  ---------------------------------------------------------------------

    def generateSAFAQL(self, df, env):
        """Constructs the AQL used in the getOpSSpecimenData function"""

        safAQL = None
        fields = []
        subformFieldsList = []
        subformNamesList = []

        cpID = df["CP ID"].unique()[0].split(".")[0] if "." in df["CP ID"].unique()[0] else df["CP ID"].unique()[0]
        params = {"cpId": cpID}
        formExten = self.getFormExtension(self.safExtension, params=params)

        if formExten:
            formDF = self.setFormDF()
            compactName = formExten["formName"]
            filt = (formDF[f"{env}ShortName"] == compactName) & (formDF["formName"].notna())
            formName = formDF.loc[filt, "formName"].item()

            fieldDF = self.setFieldDF()

            filt = (fieldDF["formName"] == formName) & (fieldDF[f"{env}UDN"].notna()) & (fieldDF["isSubForm"] == False)
            fields = fieldDF.loc[filt, f"{env}UDN"].to_list()

            filt = (
                (fieldDF["formName"] == formName)
                & (fieldDF[f"{env}SubFormUDN"].notna())
                & (fieldDF[f"{env}UDN"].notna())
                & (fieldDF["isSubForm"] == True)
                & (fieldDF["isSubField"] == True)
            )
            subformFields = fieldDF.loc[filt, [f"{env}SubFormUDN", f"{env}UDN", f"{env}SubFormName", "fieldName"]]

            subformFields["unifiedAQL"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormUDN']}.{x[f'{env}UDN']}"), axis=1
            )
            subformFieldsList = subformFields["unifiedAQL"].to_list()

            subformFields["unifiedHeader"] = subformFields.apply(
                (lambda x: f"{x[f'{env}SubFormName']}.{x['fieldName']}"), axis=1
            )
            subformNamesList = subformFields["unifiedHeader"].to_list()

        fields = [f"Specimen.customFields.{compactName}.{fieldName}" for fieldName in fields]

        subformFields = []
        for subformName, subfieldName in zip(subformNamesList, subformFieldsList):
            subformFields.append(
                f'Specimen.customFields.{compactName}.{subfieldName} as "{formName}#{subformName.split(".")[0]}#^#{subformName.split(".")[1]}"'
            )

        fields = fields + subformFields

        if fields:
            safAQL = ", ".join(fields)

        return safAQL

    #  ---------------------------------------------------------------------
