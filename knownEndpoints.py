# API details provided by Krishagni are pretty sparse and not well documented
# (see here: https://openspecimen.atlassian.net/wiki/spaces/CAT/pages/1116035/REST+APIs)
# Plus API support is not offered by Krishagni, so I imagine this will be helpful to someone else too

baseURL = "https://openspecimen_.domain.domain.domain/rest/ng/"

getEndpoints = {
    "Arrays": "specimen-arrays/",
    "Cores in Array": "specimen-arrays/[Array ID]/cores",
    "CP Events List": "collection-protocol-events/?cpId=[CPID]",
    "CP Extension Forms": "[Object Type]/extension-form?cpId=[CPID]",  # where object type is participants, specimens, etc.
    "CP Group List": "collection-protocol-groups/",
    "CP Group Workflow": "collection-protocol-groups/[CPGroupID]/workflows",
    "CP Group Workflow as File": "collection-protocol-groups/[CPGroupID]/workflows-file",
    "CP List": "collection-protocols",
    "CP Workflow": "collection-protocols/[CPID]/workflows",
    "Dropdown List": "/permissible-values/attributes",
    "Dropdown Permissible Values": "permissible-values/?attribute=[Dropdown Attribute]&maxResults=[Integer]",
    "Form List": "forms",
    "Query Folders List": "query-folders",
    "Query List": "saved-queries",
    "Single Array Details": "specimen-arrays/[Array ID]",
    "Single CP Details": "collection-protocols/[CPID]",
    "Single Form Details": "forms/[formID]/definition",  # for v7 can (also?) use: "de-forms/[formID]/true"
    "Single Query Details": "saved-queries/[queryID]",
    "Single Specimen Details": "specimens/[Specimen ID]",
    "Single Specimen Events": "specimens/[Specimen ID]/events",
    "Specimen Event Data": "forms/[Form ID]/data/[Form Record ID]?includeMetadata=true",
    "Single Container Details": "storage-containers/[CONTAINER ID]",
    "Get Matching Participants": "participants/match",
    "Get Participant by Registration ID": "collection-protocol-registrations/[ParticipantInternalID]",
}

# Most of the below rely on using the proper verb (Post vs. Put) and JSON formatting in order to function as expected
# I intend to add generic example JSON for the below in the future, but for the time being, review the uploadClasses.py file for hints as to how the JSON is structured
# Or you can peek at the network traffic while performing functions via the GUI to discover the structures, verbs, and endpoints,
# Which is how I found a lot of the above and below, as well as some AQL details not documented elsewhere
# See here for additional info on how to do this: https://developer.chrome.com/docs/devtools/network/reference/
# Generally, you can filter the XHR traffic by pasting part of the API Base URL (like: rest/ng/) into the search bar to narrow to only API calls

putAndPostEndpoints = {
    "Add/Remove Cores in Array": "specimen-arrays/[ARRAY ID]/cores",
    "Make Container Hierarchy": "storage-containers/create-hierarchy",
    "Delete Container": "storage-containers/?forceDelete=true&id=[CONTAINER ID]",
    "Review Containers of Specific Site": "storage-containers/?name=&onlyFreeContainers=true&site=[SITE NAME]&usageMode=STORAGE",
    "Make CP by Import": "collection-protocols/definition",
    "Make Array": "specimen-arrays/",
    "Make Derivative": "sde-samples/",
    "Create Participant Registration": "collection-protocol-registrations/",
    "Populate Form": "forms/[Form ID]",
}
