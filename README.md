# OpynSpecimen
An object oriented wrapper and tooling for the OpenSpecimen API, written in Python

## Introduction
This package is designed to help overcome various points of friction discovered while using [OpenSpecimen](https://github.com/krishagni/openspecimen).

## Getting Started

### Requirements
- An OpenSpecimen account with Super Admin privilege
- A Python environment with the NumPy, pandas, Requests, and jsonpickle libraries installed

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
