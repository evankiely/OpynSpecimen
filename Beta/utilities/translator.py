import os
import re
import csv
import json
import shutil
import difflib

import pandas as pd

from settings import Settings


class Translator(Settings):
    def __init__(self):

        super().__init__()
        self.inputItems = os.listdir(self.translatorInputDir)
        self.pulledWorkflows = self.loadDF(self.cpOutPath)
        self.fieldDF = self.loadDF(self.fieldOutPath)
        self.formDF = self.loadDF(self.formOutPath)
        self.availableWorkflows = self.pulledWorkflows["cpShortTitle"].values

    #  ---------------------------------------------------------------------

    def loadDF(self, path):
        """Validates file path and imports df from csv if found"""

        if os.path.exists(path):
            return pd.read_csv(path)

        else:
            raise NameError(f"Provided path, [{path}], not found.")

    #  ---------------------------------------------------------------------

    def getDiffReport(self, filePaths=None, fileNames=None, directComp=False, openOnFinish=False):
        """A generic function that compares two JSON files and creates a folder containing the two compared documents and the Diff Report file itself"""

        if filePaths is not None and isinstance(filePaths, dict):

            origFilePath = filePaths["original"]
            compFilePath = filePaths["comparison"]

            origHeader = origFilePath.split("/")[-1].split(".")[0]
            compHeader = compFilePath.split("/")[-1].split(".")[0]

        elif fileNames is not None and isinstance(fileNames, dict):

            origHeader = fileNames["original"]["file"]
            origEnv = fileNames["original"]["env"]

            compHeader = fileNames["comparison"]["file"]
            compEnv = fileNames["comparison"]["env"]

            origFilePath = f"./workflows/{origEnv}/{origHeader}"
            compFilePath = f"./workflows/{compEnv}/{compHeader}"

        else:
            raise KeyError("Something went wrong with your filePaths and/or fileNames!")

        with open(origFilePath) as orig:

            origFile = orig.readlines()

            with open(compFilePath) as comp:

                compFile = comp.readlines()

                difference = difflib.HtmlDiff().make_file(origFile, compFile, origHeader, compHeader, context=True)

                origPathReady = origHeader.split(".")[0].split("_")[0]
                compPathReady = compHeader.split(".")[0].split("_")[0]

                recordStore = f"{self.translatorOutputDir}/{origPathReady}_records"
                origOutPath = f"{recordStore}/{origPathReady}_original.json"

                if directComp:
                    compOutPath = f"{recordStore}/{compPathReady}_comparedAgainst.json"

                else:
                    compOutPath = f"{recordStore}/{compPathReady}_transitioned.json"

                if not os.path.exists(recordStore):
                    os.makedirs(recordStore)

                if not os.path.exists(origOutPath):
                    shutil.copyfile(origFilePath, origOutPath)

                if not os.path.exists(compOutPath):
                    shutil.copyfile(compFilePath, compOutPath)

                diffReportPath = os.path.expanduser(
                    f"{self.translatorOutputDir}/{origPathReady}_records/{origPathReady}_diffReport.html"
                )

                with open(diffReportPath, "w") as diffFile:
                    diffFile.write(difference)

        if openOnFinish:
            os.startfile(os.path.expanduser(diffReportPath))

    #  ---------------------------------------------------------------------

    def getFormName(self, blockName):
        """Takes in a value that may be the name of an attached form and attempts to identify the form in the form Dataframe"""

        formName = re.findall("^[a-z]+|[A-Z][^A-Z]*", blockName)

        if formName[0] == "Specimen":
            formName = " ".join(formName[1:])

        else:
            formName = " ".join(formName)

        return formName.title()

    #  ---------------------------------------------------------------------

    def translate(self, openDiff=False):
        """Performs translation of CP JSON from one env context to another"""

        for item in self.inputItems:

            #  maybe item.lower().endswith(".csv")?  -- NOTE: we can get away with simple .csv check because translate has its own upload folder
            if not item.endswith(".csv"):
                raise TypeError("Input files must be of type .CSV")

            else:
                inputDF = pd.read_csv(self.translatorInputDir + item)

                for cp, fromEnv in zip(inputDF["shortTitle"], inputDF["fromEnv"]):

                    filt = (inputDF["shortTitle"] == cp) & (inputDF["fromEnv"] == fromEnv)
                    toEnv = inputDF.loc[filt, "toEnv"].str.lower()

                    #  TODO: Add flexibility here -- source list from file names in folder of fromEnv. Currently only accepts if cp matches exactly (upper/lower case, etc.)
                    if cp in self.availableWorkflows:

                        #  removing / because it can interfere with file pathing
                        cp = cp.replace("/", "_")

                        fPath = f"./workflows/{fromEnv}/{cp}.json"
                        outPath = os.path.expanduser(f"{self.translatorOutputDir}/{cp}_records")

                        transitionedPath = f"{outPath}/{cp}_transitioned.json"
                        origCopyPath = f"{outPath}/{cp}_original.json"
                        formsPath = f"{outPath}/{cp}_requiredForms.csv"

                        if not os.path.exists(outPath):
                            os.makedirs(outPath)

                        if not os.path.exists(origCopyPath):
                            shutil.copyfile(fPath, origCopyPath)

                        with open(fPath) as f:

                            file = json.loads(f.read())
                            formList = []

                            for line in file:

                                if line["name"] == "specimenCollection":
                                    fields = line["data"]["visitFields"]["fields"][0][:]

                                    for field in fields:
                                        name = field["name"].split(".")

                                        #  filtering for "native" fields, like specimen.type, which don't need to be updated
                                        if len(name) > 2:
                                            fieldCode = name[-1]

                                            if "events" in name:
                                                formName = self.getFormName(name[-2])

                                                if formName not in formList:
                                                    formList.append(formName)

                                                codeFilt = (self.fieldDF[fromEnv.lower()] == fieldCode) & (
                                                    self.fieldDF.formName == formName
                                                )
                                                extension = self.fieldDF.loc[codeFilt, toEnv].values[0]

                                                if not pd.isna(extension[0]):

                                                    if fieldCode != extension[0]:

                                                        field["name"] = (
                                                            ".".join(field["name"].split(".")[:-1])
                                                            + f".{extension[0]}"
                                                        )
                                                        field["baseField"] = (
                                                            ".".join(field["baseField"].split(".")[:-1])
                                                            + f".{extension[0]}"
                                                        )

                                                        with open(transitionedPath, "w") as f1:
                                                            json.dump(file, f1, indent=2)

                                            else:
                                                codeFilt = self.fieldDF[fromEnv.lower()] == fieldCode

                                                for extension in self.fieldDF.loc[codeFilt, toEnv].values:

                                                    if not pd.isna(extension[0]):

                                                        if fieldCode != extension[0]:

                                                            field["name"] += f".{extension[0]}"
                                                            field["baseField"] += f".{extension[0]}"

                                                            with open(transitionedPath, "w") as f1:
                                                                json.dump(file, f1, indent=2)

                                    groups = line["data"]["fieldGroups"][:]

                                    for group in groups:
                                        rules = group["criteria"]["rules"][:]

                                        for rule in rules:
                                            name = rule["field"].split(".")

                                            if len(name) > 2:
                                                fieldCode = name[-1]

                                                if "events" in name:
                                                    formName = self.getFormName(name[-2])

                                                    if formName not in formList:
                                                        formList.append(formName)

                                                    codeFilt = (self.fieldDF[fromEnv.lower()] == fieldCode) & (
                                                        self.fieldDF.formName == formName
                                                    )
                                                    extension = self.fieldDF.loc[codeFilt, toEnv].values[0]

                                                    if not pd.isna(extension[0]):

                                                        if fieldCode != extension[0]:

                                                            field["name"] = (
                                                                ".".join(field["name"].split(".")[:-1])
                                                                + f".{extension[0]}"
                                                            )
                                                            field["baseField"] = (
                                                                ".".join(field["baseField"].split(".")[:-1])
                                                                + f".{extension[0]}"
                                                            )

                                                            with open(transitionedPath, "w") as f1:
                                                                json.dump(file, f1, indent=2)

                                                else:
                                                    codeFilt = self.fieldDF[fromEnv.lower()] == fieldCode

                                                    for extension in self.fieldDF.loc[codeFilt, toEnv].values:

                                                        if not pd.isna(extension[0]):

                                                            if fieldCode != extension[0]:
                                                                item["name"] += f".{extension[0]}"

                                                                with open(transitionedPath, "w") as f1:
                                                                    json.dump(file, f1, indent=2)

                                        fields = group["fields"][:]

                                        for field in fields:
                                            name = field["name"].split(".")

                                            if len(name) > 2:
                                                fieldCode = name[-1]

                                                if "events" in name:
                                                    formName = self.getFormName(name[-2])

                                                    if formName not in formList:
                                                        formList.append(formName)

                                                    codeFilt = (self.fieldDF[fromEnv.lower()] == fieldCode) & (
                                                        self.fieldDF.formName == formName
                                                    )
                                                    extension = self.fieldDF.loc[codeFilt, toEnv].values[0]

                                                    if not pd.isna(extension[0]):

                                                        if fieldCode != extension[0]:

                                                            field["name"] = (
                                                                ".".join(field["name"].split(".")[:-1])
                                                                + f".{extension[0]}"
                                                            )
                                                            field["baseField"] = (
                                                                ".".join(field["baseField"].split(".")[:-1])
                                                                + f".{extension[0]}"
                                                            )

                                                            with open(transitionedPath, "w") as f1:
                                                                json.dump(file, f1, indent=2)

                                                else:
                                                    codeFilt = self.fieldDF[fromEnv.lower()] == fieldCode

                                                    for extension in self.fieldDF.loc[codeFilt, toEnv].values:

                                                        if not pd.isna(extension[0]):

                                                            if fieldCode != extension[0]:

                                                                field["name"] += f".{extension[0]}"
                                                                field["baseField"] += f".{extension[0]}"

                                                                with open(transitionedPath, "w") as f1:
                                                                    json.dump(file, f1, indent=2)

                                elif line["name"] == "dictionary":
                                    fields = line["data"]["fields"][:]

                                    for item in fields:
                                        name = item["name"].split(".")

                                        if len(name) > 2:
                                            fieldCode = name[-1]

                                            if "events" in name:
                                                formName = self.getFormName(name[-2])

                                                if formName not in formList:
                                                    formList.append(formName)

                                                codeFilt = (self.fieldDF[fromEnv.lower()] == fieldCode) & (
                                                    self.fieldDF.formName == formName
                                                )
                                                extension = self.fieldDF.loc[codeFilt, toEnv].values[0]

                                                if not pd.isna(extension[0]):

                                                    if fieldCode != extension[0]:

                                                        field["name"] = (
                                                            ".".join(field["name"].split(".")[:-1])
                                                            + f".{extension[0]}"
                                                        )
                                                        field["baseField"] = (
                                                            ".".join(field["baseField"].split(".")[:-1])
                                                            + f".{extension[0]}"
                                                        )

                                                        with open(transitionedPath, "w") as f1:
                                                            json.dump(file, f1, indent=2)

                                            else:
                                                codeFilt = self.fieldDF[fromEnv.lower()] == fieldCode

                                                for extension in self.fieldDF.loc[codeFilt, toEnv].values:

                                                    #  Specimen Processing Prior to Distribution
                                                    if not pd.isna(extension[0]):

                                                        if fieldCode != extension[0]:
                                                            item["name"] += f".{extension[0]}"

                                                            with open(transitionedPath, "w") as f1:
                                                                json.dump(file, f1, indent=2)

                                        if "caption" in item.keys():

                                            caption = item["caption"]
                                            captionFilt = self.fieldDF["fieldName"] == caption

                                            for cap in self.fieldDF.loc[captionFilt, "fieldName"].values:

                                                if caption != cap:
                                                    item["caption"] += f".{cap}"

                                                    with open(transitionedPath, "w") as f1:
                                                        json.dump(file, f1, indent=2)

                                        if ("listSource" in item.keys()) and (
                                            "queryParams" in item["listSource"].keys()
                                        ):
                                            sourceVals = item["listSource"]["queryParams"]["static"]

                                            # if "formName" in sourceVals.keys():

                                            #     shortName = sourceVals["formName"]
                                            #     formNameFilt = (self.formDF[f"{fromEnv.lower()}ShortName"] == shortName)

                                            #     for form in self.formDF.loc[formNameFilt, f"{fromEnv.lower()}ShortName"].values:  #  Regex to check for V2 form

                                            #         if shortName != form:

                                            #             sourceVals["formName"] += f".{form}"

                                            #             with open(transitionedPath, "w") as f1:
                                            #                 json.dump(file, f1, indent=2)

                                            if "controlName" in sourceVals.keys():

                                                controlName = sourceVals["controlName"]
                                                controlNameFilt = self.fieldDF[fromEnv.lower()] == controlName

                                                for ctrlName in self.fieldDF.loc[controlNameFilt, toEnv].values:

                                                    if not pd.isna(ctrlName[0]):

                                                        if controlName != ctrlName[0]:

                                                            sourceVals["controlName"] += f".{ctrlName[0]}"
                                                            formName = self.getFormName(sourceVals["formName"])

                                                            if formName not in formList:
                                                                formList.append(formName)

                                                            sourceVals["formName"] += ".verifyFormPresenceInNewEnv"

                                                            with open(transitionedPath, "w") as f1:
                                                                json.dump(file, f1, indent=2)

                            self.getDiffReport(
                                filePaths={"original": origCopyPath, "comparison": transitionedPath},
                                openOnFinish=openDiff,
                            )

                            with open(formsPath, "w", newline="") as reqForms:

                                writer = csv.writer(reqForms)
                                writer.writerow([cp, formList])
