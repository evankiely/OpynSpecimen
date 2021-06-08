# OpynSpecimen
An object oriented wrapper and additional tooling for the OpenSpecimen API, written in Python

![GitHub](https://img.shields.io/github/license/evankiely/OpynSpecimen) ![GitHub all releases](https://img.shields.io/github/downloads/evankiely/OpynSpecimen/total)

## Introduction
This library is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

**Note**: OpenSpecimen v8 changed some details of the forms/fields api (namely, the JSON formatting), so be sure to select the folder which matches your version of OpS. v8 code should work with v7, though v7 will not work with v8 -- consequently, only the v8 folder will be updated and validated (against v8) from now on. This change also renders the Translator object obsolete, so long as you have never used OpS prior to v8, *and* forms/fields are named consistently across environments, as OpS no longer uses sequentially enumerated field codes, instead opting to use the field name. You can find your version of OpS by selecting the "i" to the left of the "Sign In" button on the landing page, or by selecting the "?" next to the notification icon, then selecting the "About OpenSpecimen" option, after logging in.

## Getting Started

### Requirements
- An OpenSpecimen account with Super Admin privilege
- A Python environment with the tqdm, pytz, NumPy, pandas, Requests, and jsonpickle libraries installed

### Set-Up
- These functions require access to OpenSpecimen to work properly, and will need to reference the **Username**, **Password**, and **Domain** of the chosen account
- Store these credentials in the environmental variables of your operating system
  - For more information on how to do this with [**Windows** see here](https://www.youtube.com/watch?v=IolxqkL7cD8)
  - For more information on how to do this with [**macOS** and **Linux** see here](https://www.youtube.com/watch?v=5iWhQWVXosU)
- Note the variables you associated with these credentials and alter the Settings class's `self.envs` attribute to reflect them
  - You should ideally avoid reusing credentials across your OpenSpecimen instances, which means the environmental variables themselves will need to be named differently in order to distinguish them from one another
  - The Settings class accounts for this by providing three examples that you can modify -- currently set as **test**, **dev**, and **prod**. To alter these, just replace the text in quotes within the `self.getEnVar` function call to reflect the variable names you created previously
  - If you have more than three instances of OpenSpecimen, you can always copy/paste what is already there to add more. However, be mindful that you need to replace the key for the copy/pasted values, because this key is used later to properly format the URL that is used to interface with the API
- Next you should update the `self.baseURL` attribute of the Settings class to reflect the general URL of the OpenSpecimen instances you use
  - As with the environmental variables, the functions contained here have an assumption regarding the formatting of your URL
    - They expect that you include some keyword to distinguish the instances, and that the keyword will be represented by an underscore (as in openspecimen_.openspecimen.com)
    - They expect that the production environment has no URL keyword (as in openspecimen.openspecimen.com)
    - They expect that these, aside from prod, are filled from the key for the environmental variables in the Settings class's `self.envs` attribute (as in openspecimen**test**.openspecimen.com and openspecimen**dev**.openspecimen.com)

## Documentation

### Core Classes
- **Settings**
- **Translator**
- **Integration**
- **Upload Classes**

### Core Functionality
- The **Settings** class is where all the details of the OpenSpecimen API, and your particular instance(s) of OpenSpecimen, live; it forms the basis for the other classes, which inherit their knowledge of the API endpoints, etc., from it.
  - The intent is to remove the need for users to change things in the core functions of the Translator and Integration objects
  - The content of this class should remain mostly static, since it consists primarily of details of the OpenSpecimen API. The few things that you will need/want to customize are discussed below
- The **Translator** class enables easy, human in the loop transitioning of Collection Protocol Workflows between environments, and a generic Diff Report function to compare Workflows
  - **Note**: This class is no longer necessary as of v8, so long as you've never used an earlier version of OpS (or have since started fresh with v8) and forms/fields are named consistenly across environments
- The **Integration** class provides a robust suite of functions to interface with the OpenSpecimen API, with upload capabilities for all OpenSpecimen provided templates, as well as custom implimentations for Participants, Visits, Specimens, and those items combined into a "Universal" template, for a single document based upload, in addition to Arrays, Cores, and more.
  - It is designed to be easily extensible, by making the core API requirements, such as getting/renewing tokens, making HTTP requests, etc., easy to access/invoke
- The **Upload Classes** are a set of Python objects that are used to organize and store information before being serialized to JSON and passed to the API

### Class Methods and Attributes

#### Settings
- `Settings.baseURL`
  - The generalized form of the URL for your OpenSpecimen instances
- `Settings.envs`
  - A dictionary where the keys are the OpenSpecimen environment names, and the values are dictionaries. The sub-dictionaries consist of keys representing the details of the account used to access a given environment, and the values are the results of retrieving the specified environmental variables
- `Settings.formOutPath`
  - The path used to dictate where the forms Dataframe is saved (as .csv)
- `Settings.fieldOutPath`
  - The path used to dictate where the fields Dataframe is saved (as .csv)
- `Settings.cpOutPath`
  - The path used to dictate where the Collection Protocol Dataframe is saved (as .csv)
- `Settings.dropdownOutpath`
  - The path used to dictate where the dropdowns Dataframe is saved (as .csv)
- `Settings.translatorInputDir`
  - The path used to dictate where the translator object should look for input documents
- `Settings.translatorOutputDir`
  - The path used to dictate where the translator object should save output documents (currently used as the output directory for all outputs)
- `Settings.uploadInputDir`
  - The path used to dictate where the integrations object should look for input documents when doing uploads
- `Settings.auditInputDir`
  - The path used to dictate where the integrations object should look for input documents when performing audits
- `Settings.dateFormat`
  - The format used for dates which do not include a time as well
- `Settings.datetimeFormat`
  - The format used for datetimes
- `Settings.timezone`
  - The timezone of the server
- `Settings.fillerDate`
  - A date that is old enough to be obviously fake in the cases where one is required or would be beneficial, but is not included in the data
- `Settings.templateTypes`
  - A dictionary of codes OpS uses to distinguish between template types; used with the genericBulkUpload function in the Integration object

#### Translator
- `Translator.loadDF(path)`
  - A generic function to load and return a pandas Dataframe by passing in the path to a .csv
  - **path**: The path to the file that is to be read in
- `Translator.getDiffReport(filePaths=None, fileNames=None, directComp=False, openOnFinish=False)`
  - A generic function that compares two JSON files and creates a folder containing the two compared documents and the Diff Report file itself
  - **filePaths**: A dictionary structured like `{"original": pathToOriginal, "comparison": pathToComparison}`
  - **fileNames**: A dictionary structured like `{"original": {"file": fileName, "env": envCode}, "comparison": {"file": fileName, "env": envCode}}`
  - **directComp**: Set `True` if the documents being compared are just from different environments and not translated vs. original
  - **openOnFinish**: Set `True` to open the Diff Report file when the function is done running
- `Translator.getFormName(blockName)`
  - Takes in a value that may be the name of an attached form and attempts to identify the form in the form Dataframe
  - **blockName**: The suspected form name, sourced from the Workflow text
- `Translator.translate(openDiff=False)`
  - The main function of the Translator object. Attempts to translate items specified in the input .csv, based on provided short title and environments
  - **openDiff**: Set `True` to open the Diff Report file when the function is done running

#### Integration
- `Integration.renewTokens()`
  - Retrieves updated API keys
- `Integration.getTokens()`
  - Retrieves initial API keys, upon instantiation
- `Integration.syncAll(envs=None)`
  - Calls the following functions in order: syncWorkflowList, syncWorkflows, syncFormList, syncFieldList, syncDropdownList, syncDropdownPVs
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.getResponse(extension, params=None)`
  - A generic GET request
  - **extension**: The extension to be appended to the default URL
  - **params**: A dictionary of any parameters the GET request may allow/require
- `Integration.postResponse(extension, data, method="POST", matchPPID=False)`
  - A generic request, able to accept various methods, but designed for `"PUT"` and `"POST"`
  - **extension**: The extension to be appended to the default URL
  - **data**: A dictionary of any data the request may allow/require
  - **method**: The type of request; currently tested with `"PUT"` and `"POST"`
  - **matchPPID**: Used when uploading participants; See makeParticipants/uploadParticipants for more details
- `Integration.postFile(extension, files)`
  - A generic function used to upload files via the OpenSpecimen API
  - **extension**: The extension to be appended to the default URL
  - **files**: The file or files to be uploaded
- `Integration.genericBulkUpload(importType="CREATE", checkStatus=False)`
  - A generic function used to upload files via the API rather than the GUI. Behaves exactly the same as if you were doing a bulk upload of data via the OpenSpecimen templates and GUI
  - **importType**: Whether the data is intended to `"CREATE"` new records, or `"UPDATE"` old ones
  - **checkStatus**: Whether or not to check in on the status of an upload every few seconds and print that information to the console
- `Integration.uploadCPJSON()`
  - A generic function used to upload Collection Protocol JSON files via the API rather than the GUI. This is specifically for the full Collection Protocol and not just the Workflow
- `Integration.cleanDateForBulk(date)`
  - A generic function that cleans and formats dates to something the OpenSpecimen bulk upload function will accept
  - **date**: A string corresponding to a date. This is generally implied based on the column this function is applied to with `pd.apply(cleanDateForBulk)`
- `Integration.padDates(date)`
  - A generic function which ensures dates are formatted as 0#/0#/####, where necessary
  - **date**: A string corresponding to a date.
- `Integration.fillQuantities(item)`
  - Applied to a .CSV which includes the "Initial Quantity" and "Available Quantity" fields.
  - Reads in the .CSV, selects Parent Specimens which have an Initial Quantity, identifies the Child Specimens of those Parents, sets the Parent Available Quantity to 0, and distributes the Initial Quantity of the Parent to all identified Children evenly, so long as none of those Children already have an Initial Quantity value. If any Children have an Initial Quantity, the Parent Available Quantity is set to 0, but Children are not updated, since it's not clear how to account for the pre-existing Initial Quantity that was identified. All derivatives/aliquots which have an Initial Quantity and no Available Quantity specified are updated such that the Available Quantity reflects the Initial Quantity.
  - **item**: A file path
- `Integration.matchParticipants(pmis=None, empi=None)`
  - Matches participants against those that already exist in a given environment, based on PMIS (MRN Sites and Values) or EMPI, which are system-wide IDs
  - **pmis**: A dictionary structured like `{"siteName": mrnSite, "mrn": mrnVal}`
  - **empi**: The participant's empi as a string or integer
- `Integration.makeParticipants(matchPPID=False)`
  - Creates the Participant object, populates it with data, and passes it to be uploaded
  - **matchPPID**: If `True`, will match existing participants in a Collection Protocol to those being uploaded, based on PPID, participant's last name, & participant's date of birth, and merge/update them. This is very useful when the upload data has PPIDs, in addition to MRN or EMPI values, but the existing participants have only PPIDs. Set this `True` if there is even a chance that there may already be a profile in the Collection Protocol with a PPID present in the upload data, since it will default to attempting to create the uploaded participant first, and then fall back to matching against existing PPID if the creation fails due to that PPID already being used. If the match fails on last name or date of birth, it will not push data into the profile with the same PPID
- `Integration.uploadParticipants(matchPPID=False)`
  - The function that is called to begin the participant upload process. Looks for a document named in the following format: "participants_[envCode]_miscOtherInfo.csv"
  - **matchPPID**: If `True`, will match existing participants in a Collection Protocol to those being uploaded, based on PPID, participant's last name, & participant's date of birth, and merge/update them. This is very useful when the upload data has PPIDs, in addition to MRN or EMPI values, but the existing participants have only PPIDs. Set this `True` if there is even a chance that there may already be a profile in the Collection Protocol with a PPID present in the upload data, since it will default to attempting to create the uploaded participant first, and then fall back to matching against existing PPID if the creation fails due to that PPID already being used. If the match fails on last name or date of birth, it will not push data into the profile with the same PPID
- `Integration.toUTC(data, col)`
  - Handles datetime conversion for uploads, using the Time Zone specified in the Settings object. For Birth and Death Dates, rearranges the date to fit the expectations of OpS. Otherwise, does a true conversion to UTC using the date and/or datetime formats specified in the Settings object.
  - **data**: A Pandas Series representing a single column of data to be uploaded
  - **col**: The name of the column being operated on
- `Integration.fromUTC(utcVal)`
  - Handles datetime conversion from UTC, using the Time Zone specified in the Settings object.
  - **utcVal**: A string or integer value to be converted from UTC format
- `Integration.universalUpload(matchPPID=False)`
  - The function is our answer to the "Master Specimen" template, and accomodates a modified version of that template or a custom template that has the fields your data requires from each of the supported upload templates (currently: participant, visit, and specimen, including "Additional Fields"), since it approaches this as a sequence of uploading those templates. We also prefer to use the term "Univseral" over "Master" in most cases. It looks for a document named in the following format: "universal_[envCode]_miscOtherInfo.csv"
  - **matchPPID**: If `True`, will match existing participants in a Collection Protocol to those being uploaded, based on PPID, participant's last name, & participant's date of birth, and merge/update them. This is very useful when the upload data has PPIDs, in addition to MRN or EMPI values, but the existing participants have only PPIDs. Set this `True` if there is even a chance that there may already be a profile in the Collection Protocol with a PPID present in the upload data, since it will default to attempting to create the uploaded participant first, and then fall back to matching against existing PPID if the creation fails due to that PPID already being used. If the match fails on last name or date of birth, it will not push data into the profile with the same PPID
- `Integration.matchVisit(visitName)`
  - Matches visits against those that already exist in a given environment, based on that visit's name
  - **visitName**: The name of the visit to be matched. Will match only exact, but will match the first instance of that name, so must be unique within a given Collection Protocol
- `Integration.makeVisits()`
  - Creates the Visit object, populates it with data, and passes it to be uploaded
- `Integration.uploadVisits()`
  - The function that is called to begin the visit upload process. Looks for a document named in the following format: "visits_[envCode]_miscOtherInfo.csv"
- `Integration.recursiveSpecimens(parentSpecimen=None)`
  - A depth-first approach to specimen creation
  - **parentSpecimen**: Parent specimen information to allow for the child specimen to easily match where to be uploaded
- `Integration.uploadSpecimens()`
  - The function that is called to begin the specimen upload process. Looks for a document named in the following format: "specimens_[envCode]_miscOtherInfo.csv"
- `Integration.makeSpecimen(data, referenceSpec={})`
  - Creates the Specimen object, populates it with data, and passes it to be uploaded
  - **data**: The data used to create the Specimen object
  - **referenceSpec**: A matched existing or parent specimen that is used to direct where the child is to be made and fills Parent ID, Storage Type, Visit ID, and Visit Name from the parent
- `Integration.makeAliquot(data, referenceSpec={})`
  - Creates the Aliquot object, populates it with data, and passes it to be uploaded
  - **data**: The data used to create the Aliquot object
  - **referenceSpec**: A matched existing or parent specimen that is used to direct where the child is to be made and fills Parent ID, Storage Type, Visit ID, and Visit Name from the parent
- `Integration.matchArray(arrayName)`
  - Matches arrays against those that already exist in a given environment, based on that array's name
  - **arrayName**: The name of the array to be matched. Will match only exact, but will match the first instance of that name, so must be unique within OpenSpecimen
- `Integration.populateArray(arrayDetails={})`
  - Creates the Core object, populates it with data, and passes it to be uploaded
  - **arrayDetails**: A dictionary structured like `{"name": arrayName, "id": arrayId}`
- `Integration.makeArray(forcePending=False)`
  - Creates the Array object, populates it with data, and passes it to be uploaded
  - **forcePending**: Whether or not to set arrays to pending status before attempting to create/update them. Use this if the array might already exist and could be marked as completed. Always sets the array status to completed after populating with specimens
- `Integration.uploadArrays(forcePending=False)`
  - The function that is called to begin the array upload process. Looks for a document named in the following format: "arrays_[envCode]_miscOtherInfo.csv"
  - **forcePending**: Whether or not to set arrays to pending status before attempting to create/update them. Use this if the array might already exist and could be marked as completed. Always sets the array status to completed after populating with specimens
- `Integration.buildExtensionDetail(formExten, data)`
  - Creates the Extension object, populates it with data, and passes it to be uploaded. Extension Details are things like Participant/Visit/Specimen Additional Fields, and Event Fields
  - **formExten**: A dictionary structured like `{"formId": formId, "formName": formName}`
  - **data**: The data used to create the Extension object
- `Integration.validateInputFiles(location, keyword)`
  - Pulls file paths for all the files in the Input folder which contain a given keyword
  - **location**: Path to the folder or file that is to be examined
  - **keyword**: The search term
- `Integration.auditData(keyword, wantRandSample=False)`
  - Audits data in the audit folder by comparing against what is already in OpS. Operates on .CSVs with a keyword in their name, and outputs a .CSV which logs and discrepancies. Currently only supports auditing participant information
  - **keyword**: The search term
  - **wantRandSample**: Set true if only a random sample of the data in the provided .CSVs should be audited. For record sets of 30 or fewer entries, all 30 will be audited. For record sets of greater than 30, but fewer than 100 entries, 33% will be audited. For record sets of greater than 100 entries, 10% will be audited.
- `Integration.generateRandomSample(numRecords)`
  - Generates a list of random numbers representing either 33% of numRecords, or 10%, if numRecords is less than or equal to 100, or greater than 100, respectively
  - **numRecords**: Integer value representing the total number of records available
- `Integration.setCPDF(envs=None)`
  - Sets the Collection Protocol Dataframe if the .csv exists, or builds a new copy by calling `syncWorkflowList(wantDF=True)`
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncWorkflowList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Collection Protocols which are available in the provided environment(s), as well as their internal reference codes
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe
- `Integration.syncWorkflows(envs=None)`
  - Pulls down copies of the Workflows for all Collection Protocols in the Collection Protocol Dataframe, generated by generated by syncWorkflowList, as long as those Workflows are not empty
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.setFormDF(envs=None)`
  - Sets the Form Dataframe if the .csv exists, or builds a new copy by calling syncFormList
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncFormList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Forms which are available in the provided environment(s), as well as their internal reference codes and when they were last modified/updated
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe.
- `Integration.setFieldDF(envs=None)`
  - Sets the Field Dataframe if the .csv exists, or builds a new copy by calling syncFieldList.
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncFieldList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Fields and Subfields, as well as their internal reference codes, which are available in the provided environment(s), given that environment's forms, which are given in the Dataframe generated by syncFormList
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe
- `Integration.setDropdownDF(envs=None)`
  - Sets the Dropdowns Dataframe if the .csv exists, or builds a new copy by calling syncDropdownList.
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncDropdownList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Dropdowns which are available in the provided environment(s), and their environment specific names
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe
- `Integration.syncDropdownPVs(envs=None)`
  - Creates a new Dataframe of Permissible Values which are available in the provided environment(s), given that environment's dropdowns Dataframe, generated by syncDropdownList
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.updateAll(envs=None)`
  - Calls the following functions in order: updateWorkflows, updateForms
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.updateWorkflows(envs=None)`
  - Updates Workflow Dataframe and Files (i.e. JSON), including removing any no longer in use
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.updateForms(envs=None)`
  - Updates Forms and Fields Dataframes, including removing any that are no longer in use
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.runQuery(env, cpID, AQL)`
  - Runs a query and returns results according to parameters defined in AQL
  - **env**: The env to run the query in/against
  - **cpID**: The internal reference code of the CP to query against. Set as -1 to run against all records (i.e. all CPs). Not technically necessary if CP is specified in AQL, but function requires it even if specified in AQL
  - **AQL**: The actual query to run. For more information on how to write/structure AQL see [here](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/110264471/How%2Bto%2Bdesign%2Band%2Brun%2Bqueries%2Bprogrammatically%2Busing%2BAQL) and [here](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/72024115/Calculated%2Bfields%2BTemporal%2BQueries). It is also possible to inspect the AQL of queries defined in the GUI by watching the network calls, which allows you to avoid, mostly, learning the AQL syntax

#### Upload Classes
- See the entry under [Core Functionality](https://github.com/evankiely/OpynSpecimen/blob/main/README.md#core-functionality) for more information. These objects largely store data you're uploading, so there isn't much to discuss here, since these are just intended to be used as scaffolding

## License
This project is licensed under the [GNU Affero General Public License v3.0](https://github.com/evankiely/OpynSpecimen/blob/main/LICENSE). For more permissive licensing in the case of commercial usage, please contact the [Office of Technology Transfer](http://www.ott.emory.edu/) at Emory University, and reference Emory TechID 21074

## Authors
- Evan Kiely

<p align="center">
Copyright © 2021, Emory University
</p>
