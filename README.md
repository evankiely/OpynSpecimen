# OpynSpecimen
An object oriented wrapper and tooling for the OpenSpecimen API, written in Python

## Introduction
This package is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

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
  - The Settings class accounts for this by providing three examples that you can modify -- currently set as Test, Dev, and Prod. To alter these, just replace the text in quotes within the `self.getEnVar` function call to reflect the variable names you created previously
  - If you have more than three instances, you can always copy/paste what is already there to add more. However, be mindful to replace the key for the copy/pasted values, as dictionaries may only have a single instance of a given key, and because this key is used later to properly format the URL that gets used to interface with the API
- Next you should update the `self.baseURL` attribute of the Settings class to reflect the general URL of the OpenSpecimen instances you use
  - As with the environmental variables, these functions have an assumption regarding the formatting of your URL
    - They expect that you include some keyword to distinguish the instances, and that the keyword will be represented by an underscore (as in openspecimen_.openspecimen.com)
    - They expect that the production environment has no keyword to distinguish it
    - For example: production would be openspecimen.openspecimen.com, test would be openspecimentest.openspecimen.com, and development would be openspecimendev.openspecimen.com
    - These, aside from prod, are filled from the key for the environmental variables in the Settings class

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
