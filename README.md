# OpynSpecimen
An object oriented wrapper and tooling for the OpenSpecimen API, written in Python

## Introduction
This package is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

### Use Cases
- The original problem this project set out to solve is how to transition customized objects across OpenSpecimen instances, and maintain version control
  - Like many cases where there is a distinct Production environment, we begin modifying and optimizing our approach to problems and features in our Test and Dev environments
  - As we converge on a standard set of approaches to things in those environments, we start thinking about transitioning them into Production
  - However, when we first attempted to do this via the provided JSON import/export functionality, it became apparent rather quickly that there is no inbuilt way for OpenSpecimen to account for the divergence in reference codes used to point to a particular field of a given form across environments
    - For instance, if you create a form in OpenSpecimen, and that form has a dropdown menu, the first dropdown menu in that environment, OpenSpecimen will use `DD1` to refer to it (DD for dropdown, 1 because it's the first)
    - If you later decide that it would actually be a better idea for that field to be in a different form, the dropdown added to that form will have the code `DD2`
    - Once you are ready to transition a Collection Protocol Workflow from one environment to another, if that Workflow references a field via `DD2`, but that field is actually `DD1` in the other environment, that part of the Workflow will break
  - We approached this problem by using the OpenSpecimen API to pulldown all Collection Protocol Workflows from across our various environments, along with relevant form and field data
  - We then created a function to read in a .csv which specifies the Collection Protocol(s) of interest, their starting environment, and the environment you would like for them to be modified for
  - The function then opens the Workflow file, parses it to identify places where there are codes that might need to be changed, and appends the codes it thinks should replace what is there
  - Finally, it produces a folder which contains a copy of the original Workflow, the modified Workflow, a list of forms that will need to be attached in the new environment, and a Diff file, which highlights the suggested changes so that a human can make the final determination by referencing against the field data pulled via the API

- Shortly after beginning to work on the above, we realized that the bulk data upload capabilities of OpenSpecimen are quite fragile. This is a big problem for us for a few reasons
  - We are transitioning to OpenSpecimen from a number of different legacy systems, so we will need to use it quite a lot
  - Uploads are not enacted if a single record fails, unless the number of records in the upload is larger than a size specified in settings
  - Failed uploads often provide a single reason for failure, so a record may fail for one reason, which is then addressed, then fail for some other reason on the next attempt
  - The templates used for specimen uploads encourage/require significant redundant data entry
  - Even fairly small datasets take a while to load
  - Large datasets may cause server issues, since the data is held in memory while being validated
  - So we built a more robust suite of upload functions to address these concerns

## Getting Started

### Requirements
- An OpenSpecimen account with Super Admin privilege
- A Python environment with the NumPy, pandas, Requests, tqdm, and jsonpickle libraries installed

### Set-Up
- These functions require access to OpenSpecimen to work properly, and will need to reference the **Username**, **Password**, and **Domain** of the chosen account
- Store these credentials in the environmental variables of your operating system
  - For more information on how to do this with [**Windows** see here](https://www.youtube.com/watch?v=IolxqkL7cD8)
  - For more information on how to do this with [**macOS** and **Linux** see here](https://www.youtube.com/watch?v=5iWhQWVXosU)
- Note the variables you associated with these credentials and alter the Settings class's `self.envs` attribute to reflect them
  - You should ideally avoid reusing credentials across your OpenSpecimen instances, which means the environmental variables themselves will need to be named differently in order to distinguish them from one another
  - The Settings class accounts for this by providing three examples that you can modify -- currently set as **test**, **dev**, and **prod**. To alter these, just replace the text in quotes within the `self.getEnVar` function call to reflect the variable names you created previously
  - If you have more than three instances of OpenSpecimen, you can always copy/paste what is already there to add more. However, be mindful that you need to replace the key for the copy/pasted values, as dictionaries may only have a single instance of a given key, and because this key is used later to properly format the URL that is used to interface with the API
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
- The **Settings** class is where all the details of the OpenSpecimen API, and your particular instance(s) of OpenSpecimen, live; it forms the basis for the other classes, which inherit their knowledge of the API, etc., from it.
  - The intent is to remove the need for non-technical folks to change things in the core functions of the Translator and Integration objects
  - The content of this class should remain mostly static, since it consists primarily of details of the OpenSpecimen API. The few things that you will need/want to customize are discussed below
- The **Translator** class enables easy, human in the loop transitioning of Collection Protocol Workflows between environments, and a generic Diff Report function to compare Workflows
- The **Integration** class provides a robust suite of functions to interface with the OpenSpecimen API, including pulling down internal IDs of Collection Protocols, Forms, Fields, etc., along with upload capabilities for Participants, Visits, Specimens, and those items combined into a "Universal" template, for a single document upload.
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
  - The path used to dictate where the collection protocol Dataframe is saved (as .csv)
- `Settings.dropdownOutpath`
  - The path used to dictate where the dropdowns Dataframe is saved (as .csv)
- `Settings.translatorInputDir`
  - The path used to dictate where the translator object should look for input documents
- `Settings.translatorOutputDir`
  - The path used to dictate where the translator object should save output documents (currently used as the output directory for all outputs)
- `Settings.uploadInputDir`
  - The path used to dictate where the integrations object should look for input documents when doing uploads

#### Translator
- `Translator.loadDF(path)`
  - A generic function to load and return a pandas Dataframe by passing in the path to a .csv
  - **path**: The path to the file that is to be read in
- `Translator.getDiffReport(filePaths=None, fileNames=None, directComp=False, openOnFinish=False)`
  - A generic function that compares two JSON files and creates a folder containing the two compared documents and the diff file itself
  - **filePaths**: 
  - **fileNames**: 
  - **directComp**: Set `True` if the documents being compared are just from different environments and not translated vs. original
  - **openOnFinish**: Set `True` to open the diff file when the function is done running
- `Translator.getFormName(blockName)`
  - Takes in a value that may be the name of an attached form and attempts to identify the form in the form Dataframe
  - **blockName**: The suspected form name, sourced from the workflow text
- `Translator.translate(openDiff=False)`
  - The main function of the Translator object. Attempts to translate items specified in the input .csv, based on provided short title and environments
  - **openDiff**: Set `True` to open the diff file when the function is done running

#### Integration
- `Integration.renewTokens()`
  - Retrieves updated API keys
- `Integration.getTokens()`
  - Retrieves initial API keys, upon instantiation
- `Integration.syncAll(envs=None)`
  - Calls the following functions in order: syncWorkflowList, syncWorkflows, syncFormList, syncFieldList, syncDropdownList, syncDropdownPVs
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.getResponse(env, extension, params=None)`
  - A generic GET request
  - **env**: The environment this request is targeted at
  - **extension**: The extension to be appended to the default URL
  - **params**: A dictionary of any parameters the GET request may allow/require
- `Integration.postResponse(env, extension, data, method="POST", matchPPID=False)`
  - A generic request, able to accept various methods, but designed for `"PUT"` and `"POST"`
  - **env**: The environment this request is targeted at
  - **extension**: The extension to be appended to the default URL
  - **data**: A dictionary of any data the request may allow/require
  - **method**: The type of request; currently tested with `"PUT"` and `"POST"`
  - **matchPPID**: Used when uploading participants; if `True`, will match existing participants in a collection protocol to those being uploaded based on PPID and merge/update them. This is very useful when the upload data has MRN or EMPI values, but the existing participants do not
- `Integration.postFile(env, extension, files)`
  - A generic function used to upload files via the OpenSpecimen API
  - **env**: The environment this upload is targeted at
  - **extension**: The extension to be appended to the default URL
  - **files**: The file or files to be uploaded
- `Integration.genericBulkUpload(importType="CREATE", checkStatus=False)`
  - A generic function used to upload files via the API rather than the GUI. Behaves exactly the same as if you were doing a bulk upload of data via the OpenSpecimen templates and GUI
  - **importType**: Whether the data is intended to `"CREATE"` new records, or `"UPDATE"` old ones
  - **checkStatus**: Whether or not to check in on the status of an upload every few seconds and print that information to the console
- `Integration.cleanDateForBulk(date)`
  - A generic function that cleans and formats dates to something the OpenSpecimen bulk upload function will accept
  - **date**: A piece of data corresponding to a date. This is generally implied based on the column this function is applied to with pd.apply(cleanDateForBulk)
- `Integration.cleanDateForAPI(date)`
  - A generic function that cleans and formats dates to something the OpenSpecimen API will accept
  - **date**: A piece of data corresponding to a date. This is generally implied based on the column this function is applied to with pd.apply(cleanDateForAPI)
- `Integration.cleanVal(val)`
  - A generic function that cleans and formats pandas data types to something the OpenSpecimen API will accept
  - **val**: A piece of data. This is generally implied based on the column this function is applied to with pd.apply(cleanVal)
- `Integration.matchParticipants(env, pmis=None, empi=None)`
  - Matches participants against those that already exist in a given environment, based on PMIS (MRN Sites and Values) or EMPI, which are system-wide IDs
  - **env**: The environment this function is targeted at
  - **pmis**: A dictionary structured like `{"siteName": mrnSite, "mrn": mrnVal}`
  - **empi**: The participant's empi as a string or integer
- `Integration.makeParticipants(env, matchPPID=False)`
  - Creates the Participant object, populates it with data, and passes it to be uploaded
  - **env**: The environment this function is targeted at
  - **matchPPID**: If `True`, will match existing participants in a collection protocol to those being uploaded, based on PPID, and merge/update them. This is very useful when the upload data has MRN or EMPI values, but the existing participants do not
- `Integration.uploadParticipants(matchPPID=False)`
  - The function that is called to begin the participant upload process. Looks for a document named in the following format: "participants_[envCode]_miscOtherInfo.csv"
  - **matchPPID**: If `True`, will match existing participants in a collection protocol to those being uploaded, based on PPID, and merge/update them. This is very useful when the upload data has MRN or EMPI values, but the existing participants do not
- `Integration.universalUpload()`
  - The function is our answer to the "Master Specimen" template, and accomodates either that template or a custom template that has the fields your data requires from each of the supported upload templates (currently: participant, visit, and specimen), since it approaches this as a sequence of uploading those templates. We also prefer to use the term "Univseral" over "Master" in most cases. It looks for a document named in the following format: "universal_[envCode]_miscOtherInfo.csv"
- `Integration.matchVisit(env, visitName)`
  - Matches visits against those that already exist in a given environment, based on that visit's name
  - **env**: The environment this function is targeted at
  - **visitName**: The name of the visit to be matched. Will match only exact, but will match the first instance of that name, so must be unique within an given collection protocol
- `Integration.makeVisits(env, universal=False)`
  - Creates the Visit object, populates it with data, and passes it to be uploaded
  - **env**: The environment this function is targeted at
  - **universal**: Set `True` to indicate this visit is part of a "Universal" upload
- `Integration.uploadVisits()`
  - The function that is called to begin the visit upload process. Looks for a document named in the following format: "visits_[envCode]_miscOtherInfo.csv"
- `Integration.recursiveSpecimens(env, parentSpecimen=None)`
  - A depth-first approach to specimen creation
  - **env**: The environment this function is targeted at
  - **parentSpecimen**: Parent specimen information to allow for the child specimen to easily match where to be uploaded and, eventually, fill missing information from the parent as needed
- `Integration.uploadSpecimens()`
  - The function that is called to begin the specimen upload process. Looks for a document named in the following format: "specimens_[envCode]_miscOtherInfo.csv"
- `Integration.makeSpecimen(env, data, referenceSpec={})`
  - Creates the Specimen object, populates it with data, and passes it to be uploaded
  - **env**: The environment this function is targeted at
  - **data**: The data used to create the Specimen object
  - **referenceSpec**: A parent specimen that is used to direct where the child is to be made and, eventually, fill missing information from the parent as needed
- `Integration.makeAliquot(env, data, referenceSpec={})`
  - Creates the Aliquot object, populates it with data, and passes it to be uploaded
  - **env**: The environment this function is targeted at
  - **data**: The data used to create the Aliquot object
  - **referenceSpec**: A parent specimen that is used to direct where the child is to be made and, eventually, fill missing information from the parent as needed
- `Integration.buildExtensionDetail(env, formExten, data)`
  - Creates the Extension object, populates it with data, and passes it to be uploaded. Extension Details are things like Participant/Visit/Specimen Additional Fields, and Event Fields
  - **env**: The environment this function is targeted at
  - **formExten**: A dictionary structured like `{"formId": formId, "formName": formName}`
  - **data**: The data used to create the Extension object
- `Integration.validateInputFiles(keyword)`
  - Pulls file paths for all the files in the Input folder which contain a given keyword
  - **keyword**: The search term
- `Integration.setCPDF(envs=None)`
  - Sets the Collection Protocol Dataframe if the .csv exists, or builds a new copy by calling syncWorkflowList. Since it sets `wantDF=True` when calling syncWorkflowList the .csv copy of the Collection Protocol Dataframe is not updated when this is invoked
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncWorkflowList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Collection Protocols which are available in the provided environment(s), as well as their internal reference codes
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe. If so, the Dataframe is returned before the call to write to .csv is invoked, and the .csv is not updated
- `Integration.syncWorkflows(envs=None)`
  - Pulls down copies of the Workflows for all Collection Protocols in the Collection Protocol Dataframe, generated by generated by syncWorkflowList, as long as those Workflows are not empty
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.setFormDF(envs=None)`
  - Sets the Form Dataframe if the .csv exists, or builds a new copy by calling syncFormList. Since it sets `wantDF=True` when calling syncFormList the .csv copy of the Form Dataframe is not updated when this is invoked
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncFormList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Forms which are available in the provided environment(s), as well as their internal reference codes and when they were last modified/updated
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe. If so, the Dataframe is returned before the call to write to .csv is invoked, and the .csv is not updated
- `Integration.setFieldDF(envs=None)`
  - Sets the Field Dataframe if the .csv exists, or builds a new copy by calling syncFieldList. Since it sets `wantDF=True` when calling syncFieldList the .csv copy of the Field Dataframe is not updated when this is invoked
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncFieldList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Fields and Subfields, as well as their internal reference codes, which are available in the provided environment(s), given that environment's forms, which are given in the Dataframe generated by syncFormList
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe. If so, the Dataframe is returned before the call to write to .csv is invoked, and the .csv is not updated
- `Integration.setDropdownDF(envs=None)`
  - Sets the Dropdowns Dataframe if the .csv exists, or builds a new copy by calling syncDropdownList. Since it sets `wantDF=True` when calling syncDropdownList the .csv copy of the Dropdowns Dataframe is not updated when this is invoked
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
- `Integration.syncDropdownList(envs=None, wantDF=False)`
  - Creates a new Dataframe of Dropdowns which are available in the provided environment(s), and their environment specific names
  - **envs**: A list of the environments these actions should be done for/applied to. If `None`, default is to use all specified in Settings.envs
  - **wantDF**: Indicates if the user wants the function to return the new Dataframe. If so, the Dataframe is returned before the call to write to .csv is invoked, and the .csv is not updated
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

#### Upload Classes
- See the entry under Core Functionality for more information. These objects largely store data you're uploading, so there isn't much to discuss here, since these are just intended to be used as scaffolding

## License
This project is licensed under the [GNU Affero General Public License v3.0](https://github.com/evankiely/OpynSpecimen/blob/main/LICENSE). For more permissive licensing in the case of commercial usage, please contact the [Office of Technology Transfer](http://www.ott.emory.edu/) at Emory University, and reference Emory TechID 21074

## Authors
- Evan Kiely

Copyright © 2021, Emory University
