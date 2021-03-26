# OpynSpecimen
An object oriented wrapper and tooling for the OpenSpecimen API, written in Python

## Introduction
This package is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

### Use Cases
- The original problem this project set out to solve is how to transition customized objects across the various OpenSpecimen instances we run
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
- A Python environment with the NumPy, pandas, Requests, and jsonpickle libraries installed

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
- Settings
- Translator
- Integrations
- Upload Classes

### Core Functionality
- The **Settings** class is where all the details of the OpenSpecimen API, and your particular instance of OpenSpecimen, live. It forms the basis for the other classes, which inherit their knowledge of the API, etc., from it. The intent here is to remove the need for non-technical folks to change things in the core functions of the Translator and Integrations objects. This approach does not always lead to the cleanest, most efficient code, but is often better for use in a business environment.

### Class Methods and Attributes

## License
This project is licensed under the [GNU Affero General Public License v3.0](https://github.com/evankiely/OpynSpecimen/blob/main/LICENSE). For more permissive licensing in the case of commercial usage, please contact the [Office of Technology Transfer](http://www.ott.emory.edu/) at Emory University, and reference Emory TechID 21074

## Authors
- Evan Kiely

Copyright © 2021, Emory University
