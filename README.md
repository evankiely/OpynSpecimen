# OpynSpecimen
### An object oriented wrapper and tooling for the OpenSpecimen API, written in Python

![GitHub](https://img.shields.io/github/license/evankiely/OpynSpecimen?label=license) ![GitHub stars](https://img.shields.io/github/stars/evankiely/OpynSpecimen) ![GitHub issues](https://img.shields.io/github/issues/evankiely/OpynSpecimen)

## Introduction
This library is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

**Note**: The Beta version is the most recent and up to date revision. All Alpha code in this repository should be considered deprecated. It may still work, but contains a number of bugs and should not be used, except as a tool to build understandings.

## Getting Started

### Requirements
- An OpenSpecimen (>= v8.1.RC8) account with Super Admin privilege and/or API permissions
- A Python environment (>= 3.7.10) with the tqdm, pytz, httpx, pandas, jsonpickle libraries installed
  - You can easily create this env with the OpS_Env.yml, located in the setUpFiles folder, using the following command from within the directory: `conda env create -f OpS_Env.yml`

### Set-Up
- These functions require access to OpenSpecimen to work properly, and will need to reference the **Username**, **Password**, and **Domain** of the chosen account
- Store these credentials in the environmental variables of your operating system
  - For more information on how to do this with [**Windows** see here](https://www.youtube.com/watch?v=IolxqkL7cD8)
  - For more information on how to do this with [**macOS** and **Linux** see here](https://www.youtube.com/watch?v=5iWhQWVXosU)
- Note the variables you associated with these credentials and alter the Settings class' `self.envs` attribute to reflect them
  - You should avoid reusing credentials across your OpenSpecimen instances, which means the environmental variables themselves will need to be named differently in order to distinguish them from one another
  - The Settings class accounts for this by providing three examples that you can modify -- currently set as **test**, **dev**, and **prod**. To alter these, just replace the text in quotes within the `self.getEnVar` function call to reflect the variable names you created previously
  - If you have more than three instances of OpenSpecimen, you can always copy/paste what is already there to add more. However, be mindful that you need to replace the key for the copy/pasted values, because this key is used later to properly format the URL that is used to interface with the API
- Next you should update the `self.baseURL` attribute of the Settings class to reflect the general URL of the OpenSpecimen instances you use
  - As with the environmental variables, the library has an assumption regarding the formatting of your URL
    - It expects that you include some keyword to distinguish the instances, and that the keyword will be represented by an underscore (as in openspecimen_.openspecimen.com)
    - It expects that the production environment has no URL keyword (as in openspecimen.openspecimen.com)
    - It expects that these, aside from prod, are filled from the key for the environmental variables in the Settings class's `self.envs` attribute (as in openspecimen**test**.openspecimen.com and openspecimen**dev**.openspecimen.com)

## Documentation

### API Endpoints
 - See knownEndpoints.py (in the OpynSpecimen folder) for a set of endpoints I have used/discovered while putting this together. For Krishagni's documentation, [see here](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/1116035/REST+APIs)

### Templates
 - Within the Templates folder you will find a set of Excel files. These files illustrate the differences between the standard OpS templates, and the templates used by this library. The un-annotated templates are ready to be used, once they are converted to .CSV (this library only supports .CSVs currently). They are provided as Excel to ensure the formatting is retained, as that is quite helpful when transitioning from the standard templates to the new ones. The annotated templates provide a direct field to field comparison between the standard template and the template used by this library, as well as a description of what data that field is intended to accept.
 - With the transition from Alpha to Beta, this library has done away with individual folders as context for functions. That is, it no longer relies on upload data going into the Upload folder, or audit data going into the Audit folder. Now context is derived almost exclusively from the file naming conventions. Examples below.
   - **Context**: Upload of Participant Template into Development
     - **File Name**: participants_dev_[misc. info].csv
   - **Context**: Audit of Universal Template data as it exists in Production
     - **File Name**: audit_universal_prod_[misc. info].csv

### Core Classes
- **Settings**
- **Translator**
- **Integration**
- **Generic**

### Core Functionality
- The **Settings** class is where all the details of the OpenSpecimen API, and your particular instance(s) of OpenSpecimen, live; it forms the basis for the other classes, which inherit their knowledge of the API endpoints, etc., from it.
  - The intent is to remove the need for users to change things in the core functions of the Translator and Integration objects
  - The content of this class should remain mostly static, since it consists primarily of details of the OpenSpecimen API. The few things that you will need/want to customize are clearly indicated in the file, and discussed explicitly below
- The **Translator** class enables easy, human in the loop transitioning of Collection Protocol Workflows between environments, and a generic Diff Report function to compare Workflows
  - **Note**: OpS no longer uses sequentially enumerated field codes, instead opting to use the field name. As such, this class is no longer necessary as of v8, so long as you've never used an earlier version of OpS (or have since rebuilt all forms/fields with v8), and forms/fields are named consistenly across environments. You can find your version of OpS by selecting the "i" to the left of the "Sign In" button on the landing page, or by selecting the "?" next to the notification icon, then selecting the "About OpenSpecimen" option, after logging in.
  - **Refactor of this class is/was planned, but is currently on hold.**
- The **Integration** class provides a robust suite of functions to interface with the OpenSpecimen API, with upload capabilities for all OpenSpecimen provided templates, as well as custom implimentations for a subset of those templates.
  - Those which have custom implimentations use unique templates, enabling more comprehensive data capture, more robust error checking, faster turn-around times, etc.
  - This class also includes audit functions, which directly compare the data in the provided template against what is already in OpS and reports any discrepancies.
  - Finally, it is designed to be easily extensible, by making the core API requirements, such as getting/renewing tokens, making HTTP requests, etc., easy to access/invoke
  - **Note**: The upload functions were originally written to use asynchronous requests, but this overwhlemed OpS extremely quickly. These asynchronous implimentations are still in the code (but are commented out), because uploads using this approach see a significant boost in speed (before crashing the server). Hopefully we will see a more robust OpS in the near future (see [Future Directions](https://github.com/evankiely/OpynSpecimen/blob/main/README.md#future-directions) below for another potential workaround)
- **Generic** is a set of two Python classes which are used to organize and store information before being serialized to JSON and passed to the API. They are "generic" because they have few/no standard attributes, and are built up dynamically based on the record they are built for.

### Class Methods and Attributes

#### Settings
- `Settings.baseURL`
  - The generalized form of the URL for your OpenSpecimen instances
- `Settings.envs`
  - A dictionary where the keys are the OpenSpecimen environment names, and the values are dictionaries. The sub-dictionaries consist of keys representing the details of the account used to access a given environment, and the values are the results of retrieving the specified environmental variables
- `Settings.translatorInputDir`
  - The path used to dictate where the translator object should look for input documents
- `Settings.inputDir`
  - The path used to dictate where to look for input documents; Document context is provided by naming convention
- `Settings.outputDir`
  - The path used to dictate where to save output documents
- `Settings.formOutPath`
  - The path used to dictate where the forms Dataframe is saved (as .csv)
- `Settings.fieldOutPath`
  - The path used to dictate where the fields Dataframe is saved (as .csv)
- `Settings.cpOutPath`
  - The path used to dictate where the Collection Protocol Dataframe is saved (as .csv)
- `Settings.dropdownOutpath`
  - The path used to dictate where the dropdowns Dataframe is saved (as .csv)
- `Settings.dateFormat`
  - The format used for dates which do not include a time as well
- `Settings.datetimeFormat`
  - The format used for datetimes
- `Settings.timezone`
  - The timezone of the server
- `Settings.fillerDate`
  - A date that is old enough to be obviously fake in the cases where one is required or would be beneficial, but is not included in the data
- `Settings.asyncChunkSize`
  - Number of records to send as asynchronous requests at one time
- `Settings.lookUpChunkSize`
  - Number of records to look up via AQL at one time
- `Settings.participanteMPIMatchAQL`
  - AQL which is used when looking up participants based on eMPI
- `Settings.participantMRNMatchAQL`
  - AQL which is used when looking up participants based on MRN Site and Number
- `Settings.participantPPIDMatchAQL`
  - AQL which is used when looking up participants based on PPID
- `Settings.participantIDMatchAQL`
  - AQL which is used when looking up participants based on their OpS internal ID
- `Settings.visitMatchAQL`
  - AQL which is used to match visits based on visit name
- `Settings.specimenMatchAQL`
  - AQL which is used to match specimens based on specimen label
- `Settings.parentMatchAQL`
  - AQL which is used to match parent specimens based on parent specimen label
- `Settings.participantAuditAQL`
  - AQL which is used to retreive comprehensive participant data from OpS for audit purposes
- `Settings.visitAuditAQL`
  - AQL which is used to retreive comprehensive visit data from OpS for audit purposes
- `Settings.specimenAuditAQL`
  - AQL which is used to retreive comprehensive specimen data from OpS for audit purposes
- `Settings.templateTypes`
  - A dictionary of codes OpS uses to distinguish between template types; used with the genericBulkUpload function in the Integration object
- `Settings.requiredPaths`
  - List of files and folders which must exist in order for this library to function
- `Settings.buildEnv()`
  - Function which verifies if all required paths exist, and creates them if they are not found
- `Settings.getEnVar()`
  - Function which retrieves data associated with the environmental variables given in Settings.envs

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
- `Integration.profileFunc(func)`
  - Profiles the function passed into it
  - **func**: A string representing the function to be profiled.
  - Example: `Integration.profileFunc("self.upload()")`
- `Integration.renewTokens()`
  - Retrieves updated API keys
- `Integration.getTokens()`
  - Retrieves initial API keys, upon instantiation
- `Integration.genericGetRequest(env, extension, params=None)`
  - A generic GET request
  - **env**: The environment the request is intended for
  - **extension**: The extension to be appended to the default URL
  - **params**: A dictionary of any parameters the request may allow/require
- `Integration.getFormExtension(extension, params)`
  - Gets the extension used to reference a particular "Additional Fields" form associated with the current CP of interest
  - **extension**: The extension to be appended to the default URL
  - **params**: A dictionary of any parameters the request may allow/require
- `Integration.buildExtensionDetail(formExten, data)`
  - Creates the Extension object, populates it with data, and passes it to be uploaded. Extension Details are things like Participant/Visit/Specimen Additional Fields, and Event Fields
  - **formExten**: A dictionary structured like `{"formId": formId, "formName": formName}`
  - **data**: The data used to create the Extension object
- `Integration.syncDropdowns()`
  - Creates a csv of all dropdowns and their permissible values for each env given in Settings
- `Integration.getDropdownsAsList(env)`
  - Creates a list of Dropdowns which are available in the provided environment, and their environment specific names
  - **env**: The environment the request is intended for
- `Integration.getDropdownVals(env, dropdown)`
  - Creates a list of Permissible Values which are available in the specified dropdown within the provided environment
  - **env**: The environment the request is intended for
- `Integration.setCPDF(refresh=False)`
  - Returns cpDF
  - **refresh**: If true, rebuilds the cpDF by calling `Integration.syncWorkflowList(wantDF=True)`
- `Integration.syncAll()`
  - Calls the following functions in order: syncWorkflowList, syncWorkflows, syncFormList, syncFieldList, syncDropdownList, syncDropdownPVs
- `Integration.syncWorkflowList(wantDF=False)`
  - Creates a new Dataframe of Collection Protocols which are available in the provided environment(s), as well as their internal reference codes
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe
- `Integration.syncWorkflows()`
  - Pulls down copies of the Workflows for all Collection Protocols in the Collection Protocol Dataframe, generated by generated by syncWorkflowList, as long as those Workflows are not empty
- `Integration.getWorkflows(env, data)`
  - Fetches workflow JSON for the CPs associated with a given env in the cpDF
  - **env**: The environment the request is intended for
  - **data**: Dataframe containing the requisite information, such as URL, to fetch CP JSON
- `Integration.writeWorkflow(env, shortTitle, workflow, isGroup=False)`
  - Writes workflow JSON to a file
  - **env**: The environment the request is intended for
  - **shortTitle**: Short title of the CP the workflow is associated with
  - **workflow**: Workflow JSON
  - **isGroup**: Whether the workflow JSON is for a group or individual CP
- `Integration.setFormDF(refresh=False)`
  - Returns formDF
  - **refresh**: If true, rebuilds the formDF by calling `Integration.syncFormList(wantDF=True)`
- `Integration.syncFormList(wantDF=False)`
  - Creates a new Dataframe of Forms which are available in the provided environment(s), as well as their internal reference codes and when they were last modified/updated
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe.
- `Integration.setFieldDF(refresh=False)`
  - Returns fieldDF
  - **refresh**: If true, rebuilds the fieldDF by calling `Integration.syncFieldList(wantDF=True)`
- `Integration.syncFieldList(wantDF=False)`
  - Creates a new Dataframe of Fields and Subfields, as well as their internal reference codes, which are available in the provided environment(s), given that environment's forms, which are given in the Dataframe generated by syncFormList
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe
- `Integration.updateAll(envs=None)`
  - Calls the following functions in order: updateWorkflows, updateForms
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.updateWorkflows(envs=None)`
  - Updates Workflow Dataframe and Files (i.e. JSON), including removing any no longer in use
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.updateForms(envs=None)`
  - Updates Forms and Fields Dataframes, including removing any that are no longer in use
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.fromUTC(utcVal)`
  - Handles datetime conversion from UTC, using the Time Zone specified in the Settings object.
  - **utcVal**: A string or integer value to be converted from UTC format
- `Integration.chunkDF(df, chunkSize=None)`
  - Returns a chunked dataframe.
  - **df**: Dataframe to be chunked
  - **chunkSize**: Number of rows per chunk (defaults to Integration.asyncChunkSize)
- `Integration.runQuery(env, cpID, AQL)`
  - Runs a query via OpS and returns the response JSON, otherwise returns error message from the server
  - **env**: The environment the request is intended for
  - **cpID**: The internal reference code of the CP to query against. Set as -1 to run against all records (i.e. all CPs). Not technically necessary if CP is specified in AQL, but function requires it even if specified in AQL
  - **AQL**: For more information on how to write/structure AQL see [here](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/110264471/How%2Bto%2Bdesign%2Band%2Brun%2Bqueries%2Bprogrammatically%2Busing%2BAQL) and [here](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/72024115/Calculated%2Bfields%2BTemporal%2BQueries). It is also possible to inspect the AQL of queries defined in the GUI by watching the network calls, which allows you to avoid, mostly, learning the AQL syntax
- `Integration.cpDefJSONUpload()`
  - Creates a new collection protocol by uploading the CP Def JSON (*NOT* Workflow JSON)
- `Integration.genericGUIFileUpload(importType="CREATE", checkStatus=False)`
  - A generic function used to upload files via the API rather than the GUI. Behaves exactly the same as if you were doing a bulk upload of data via the OpenSpecimen templates and GUI
  - **importType**: Whether the data is intended to `"CREATE"` new records, or `"UPDATE"` old ones
  - **checkStatus**: Whether or not to check in on the status of an upload every few seconds and print that information to the console
- `Integration.fileUploadPrep(file)`
  - Prepares a file for upload via genericGUIFileUpload
  - **file**: Path to file being uploaded
- `Integration.cleanDateForFileUpload(date)`
  - A generic function that cleans and formats dates to something the OpenSpecimen bulk upload function will accept
  - **date**: A string corresponding to a date. This is generally implied based on the column this function is applied to with `pd.apply(cleanDateForBulk)`
- `Integration.pushFile(file, templateType, env, importType, checkStatus)`
  - Pushes the file from genericGUIFileUpload to OpS and provides updates on import
  - **file**: Path to file being uploaded
  - **templateType**: Template being uploaded
  - **env**: The environment the request is intended for
  - **importType**: Whether the import is meant to create or update records
  - **checkStatus**: Whether or not to provide updates on upload progress
- `Integration.upload(matchPPID=False)`
  - Generic upload function which attempts to upload as many files in the input folder as possible
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.dfImport(file, env)`
  - Imports DF from CSV and performs initial pre-processing/pre-validation of data
  - **file**: Path to file being uploaded
  - **env**: The environment the request is intended for
- `Integration.universalUpload(dfDict, matchPPID=False)`
  - Wrapper around the upload functions for the three main import types which compose the OpS "Master Specimen" template; Uploads data from a universal template. It looks for a document named in the following format: "universal_[envCode]_miscOtherInfo.csv"
  - **dfDict**: A dictionary of dataframes which represent data in the Universal Template format
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.participantUpload(dfDict,matchPPID=False)`
  - Performs upload of participant data from a participant template. Looks for a document named in the following format: "participants_[envCode]_miscOtherInfo.csv"
  - **dfDict**: A dictionary of dataframes which represent data in the Participant Template format
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.participantPreMatchValidation(df, env)`
  - Performs validation of participant specific data to catch any errors and/or duplicates
  - **df**: Dataframe of participant data
  - **env**: The environment the request is intended for
- `Integration.matchParticipants(participantDF, shortTitle, matchPPID)`
  - Attempts to match participants in the data to existing profile for that participant in OpS
  - **participantDF**: Dataframe of participant data
  - **shortTitle**: Short Title of the CP of interest
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.matchParticipantEMPI(data, shortTitle)`
  - Uses participant EMPI to attempt to match an existing profile in OpS
  - **data**: Participant data
  - **shortTitle**: Short Title of the CP of interest
- `Integration.matchParticipantMRN(data, shortTitle, site, mrnCol)`
  - Uses participant MRN to attempt to match an existing profile in OpS
  - **data**: Participant data
  - **shortTitle**: Short Title of the CP of interest
  - **site**: MRN site of interest
  - **mrnCol**: MRN column of interest
- `Integration.matchParticipantPPID(data, shortTitle)`
  - Uses participant PPID to attempt to match an existing profile in OpS
  - **data**: Participant data
  - **shortTitle**: Short Title of the CP of interest
- `Integration.participantNoMatchValidation(df)`
  - Enforces the more stringent rules that come with needing to create a participant (i.e. if they fail to match an existing OpS profile)
  - **df**: Dataframe of participants which failed to match
- `Integration.getPPIDByParticipantID(data, shortTitle)`
  - Uses participant ID and the CP short title where the matched profile resides to look up the associated PPID
  - **data**: Participant data
  - **shortTitle**: Short Title of the CP of interest
- `Integration.buildParticipantObj(data)`
  - Creates the Participant object and populates it with data
  - **data**: Participant data
- `Integration.updateParticipants(data)`
  - Pushes data associated with participants matched in the CP of interest (hence update)
  - **data**: Participant data
- `Integration.createParticipants(data)`
  - Pushes data associated with participants which failed to match in CP of interest, or OpS in general, in order to create them
  - **data**: Participant data
- `Integration.populatePPIDs(data)`
  - Finds participants in the data which are missing PPIDs and updates the records to include them (for newly created participants)
  - **data**: Participant data
- `Integration.visitUpload(dfDict)`
  - Performs upload of visit data from a visit template. Looks for a document named in the following format: "visits_[envCode]_miscOtherInfo.csv"
  - **dfDict**: A dictionary of dataframes which represent data in the Visit Template format
- `Integration.visitPreMatchValidation(df, env)`
  - Performs validation of visit specific data to catch any errors and/or duplicates
  - **df**: Dataframe of visit data
  - **env**: The environment the request is intended for
- `Integration.matchVisits(visitDF)`
  - Attempts to match visits in the data to existing visit in OpS
  - **visitDF**: Dataframe of visit data
- `Integration.matchVisitName(data)`
  - Uses visit name to attempt to match an existing visit in OpS
  - **data**: Visit data
- `Integration.visitNoMatchValidation(df)`
  - Enforces the more stringent rules that come with needing to create a visit (i.e. if they fail to match an existing visit in OpS)
  - **df**: Dataframe of visits which failed to match
- `Integration.buildVisitObj(data)`
  - Creates the Visit object and populates it with data
  - **data**: Visit data
- `Integration.updateVisits(data)`
  - Pushes data associated with visits matched in the CP of interest (hence update)
  - **data**: Visit data
- `Integration.createVisits(data)`
  - Pushes data associated with visits which failed to match in CP of interest, or OpS in general, in order to create them
  - **data**: Visit data
- `Integration.populateVisitNames(data)`
  - Finds visits in the data which are missing Visit Name and updates the records to include them (for newly created visits)
  - **data**: Visit data
- `Integration.specimenUpload(dfDict)`
  - Performs upload of specimen data from a specimen template. Looks for a document named in the following format: "specimens_[envCode]_miscOtherInfo.csv"
  - **dfDict**: A dictionary of dataframes which represent data in the Specimen Template format
- `Integration.specimenPreMatchValidation(df, env)`
  - Performs validation of specimen specific data to catch any errors and/or duplicates
  - **df**: Dataframe of specimen data
  - **env**: The environment the request is intended for
- `Integration.matchSpecimens(specimenDF)`
  - Attempts to match specimens in the data to existing specimen in OpS
  - **specimenDF**: Dataframe of specimen data
- `Integration.matchSpecimenLabel(data)`
  - Uses specimen label to attempt to match an existing specimen in OpS
  - **data**: Specimen data
- `Integration.matchParentSpecimenLabel(data)`
  - Uses parent specimen label to attempt to match an existing parent specimen in OpS
  - **data**: Specimen data
- `Integration.populateParentInfo(data, specimenDF)`
  - Populates the required parent specimen info into the child specimen's record
  - **data**: Specimen data
  - **specimenDF**: Dataframe of specimen data
- `Integration.specimenNoMatchValidation(df)`
  - Enforces the more stringent rules that come with needing to create a specimen (i.e. if they fail to match an existing specimen in OpS)
  - **df**: Dataframe of specimens which failed to match
- `Integration.buildSpecimenObj(data)`
  - Creates the Specimen object and populates it with data
  - **data**: Specimen data
- `Integration.updateSpecimens(data)`
  - Pushes data associated with specimens matched in the CP of interest (hence update)
  - **data**: Specimen data
- `Integration.createSpecimens(data)`
  - Pushes data associated with specimens which failed to match in CP of interest, or OpS in general, in order to create them
  - **data**: Specimen data
- `Integration.arrayUpload(dfDict)`
  - Performs upload of array data from an array template. Looks for a document named in the following format: "arrays_[envCode]_miscOtherInfo.csv"
  - **dfDict**: A dictionary of dataframes which represent data in the Array Template format
- `Integration.arrayPreMatchValidation(df)`
  - Performs validation of array specific data to catch any errors and/or duplicates
  - **df**: Dataframe of array data
- `Integration.matchArray(arrayName)`
  - Attempts to match arrays in the data to existing arrays in OpS
  - **arrayName**: The name of the array to be matched. Will match only exact, and will match the first instance of that name, so must be unique within OpenSpecimen
- `Integration.buildArrayObj(data)`
  - Creates the Array object and populates it with data
  - **data**: Array data
- `Integration.updateArray(arrayObj, url)`
  - Pushes data associated with arrays matched in OpS (hence update)
  - **arrayObj**: Array object to be uploaded
  - **url**: URL associated with existing array
- `Integration.createArray(arrayObj, base)`
  - Pushes data associated with arrays which failed to match in OpS in order to create them
  - **arrayObj**: Array object to be uploaded
  - **base**: Base URL on to which the arrayExtension is appended
- `Integration.populateArray(coreList, url, arrayName)`
  - Populates array object with the required core specimens
  - **coreList**: A list of cores which are contained within the specified array
  - **url**: URL specific to the array of interest
  - **arrayName**: Name of the array of interest
- `Integration.audit(matchPPID=False)`
  - Generic audit function which attempts to audit as many files in the input folder as possible
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.universalAudit(dfDict, matchPPID)`
  - Wrapper around the audit functions for the three main import types which compose the OpS "Master Specimen" template; Audits data from a universal template
  - **dfDict**: A dictionary of dataframes which represent data in the Universal Template format
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.participantAudit(dfDict, matchPPID)`
  - Performs audit of participant data given in the participant template being audited
  - **dfDict**: A dictionary of dataframes which represent data in the Participant Template format
  - **matchPPID**: Whether to match participant PPID in the case where records have no MRN or eMPI
- `Integration.getOpSParticipantData(data, env)`
  - Retrieves the OpS data associated with participants given in the participant template being audited
  - **data**: Dataframe of participant data
  - **env**: The environment the request is intended for
- `Integration.generatePAFAQL(data, env)`
  - Constructs the AQL used in the getOpSParticipantData function
  - **data**: Dataframe of participant data
  - **env**: The environment the request is intended for
- `Integration.visitAudit(dfDict)`
  - Performs audit of visit data given in the visit template being audited
  - **dfDict**: A dictionary of dataframes which represent data in the Visit Template format
- `Integration.getOpSVisitData(data, env)`
  - Retrieves the OpS data associated with visits given in the visit template being audited
  - **data**: Dataframe of visit data
  - **env**: The environment the request is intended for
- `Integration.generateVAFAQL(data, env)`
  - Constructs the AQL used in the getOpSVisitData function
  - **data**: Dataframe of visit data
  - **env**: The environment the request is intended for
- `Integration.specimenAudit(dfDict)`
  - Performs audit of specimen data given in the specimen template being audited
  - **dfDict**: A dictionary of dataframes which represent data in the Specimen Template format
- `Integration.getOpSSpecimenData(data, env)`
  - Retrieves the OpS data associated with specimens given in the specimen template being audited
  - **data**: Dataframe of specimen data
  - **env**: The environment the request is intended for
- `Integration.generateSAFAQL(data, env)`
  - Constructs the AQL used in the getOpSSpecimenData function
  - **data**: Dataframe of specimen data
  - **env**: The environment the request is intended for


#### Generic
- See the entry under [Core Functionality](https://github.com/evankiely/OpynSpecimen/blob/main/README.md#core-functionality) for more information. These objects mostly used to store data for a particular record in the requisite format, so there isn't much to discuss here, since these are just intended to be used as scaffolding

## Future Directions

### In No Particular Order Unless Otherwise Noted
- Impliment checking of limitless column order and match the template order to what is in OpS (highest priority)
  - If `Race#1` for participant A in OpS is "Asian", but `Race#1` for participant A in the upload template is "Black or African American," OpS will not create a new entry under Race (i.e. `Race#2`: "Black or African American"). It will, instead, overwrite the content of `Race#1` in OpS with the content of `Race#1` in the upload. This is true in all "limitless" fields (MRN, Ethnicity, Clinical Diagnosis, etc.), and has been a source of a lot of data integrity issues when updating records in bulk, as well as causing false positives when auditing
- User reported bugs/bug fixes (high priority)
- Integration with APIs of other systems (such as PPMS)
- Ability for OpS to trigger code as an [External Job](https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/1491435565/External+jobs)
  - Enables more complex queries, data analysis/reporting, dashboards/visualizations, and highly customized emails for PIs and stakeholders
- Compatibility check with Python 3.10 and greater
  - Addition of more robust typing/type hinting
  - Addition of more, and more helpful, comments in code
- Development of (unit & integration) test suite for more test-driven development
- Remove Print statements and replace with more helpful progress messages (ideally via/in addition to tqdm)
- Further revision and improvement of documentation
- More robust record validation (automatically catching cases where records are obviously fake/entered as tests)
- Ability for user to specify audit to run immediately after upload (i.e. verify data was uploaded to OpS as expected)
- Add token renewal once server response time drops below n seconds (some potentially promising results indicating that this approach might make asynchronous requests feasible)
- Refactor of Translator class (low priority)
- Direct SQL interface with OpS backend (lowest priority)

## License
This project is licensed under the [GNU Affero General Public License v3.0](https://github.com/evankiely/OpynSpecimen/blob/main/LICENSE). For more permissive licensing in the case of commercial usage, please contact the [Office of Technology Transfer](http://www.ott.emory.edu/) at Emory University, and reference TechID 21074

## Authors
- Evan Kiely

<p align="center">
Copyright © 2021, Emory University
</p>
