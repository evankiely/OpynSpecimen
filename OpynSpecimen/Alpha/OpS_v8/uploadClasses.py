class Participant:
    def __init__(
        self,
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
        extensionDetail,
    ):

        #  Have to use idVal because id is a builtin python function
        self.id = idVal
        self.firstName = firstName
        self.middleName = middleName
        self.lastName = lastName
        self.uid = uid
        self.birthDate = birthDate
        self.vitalStatus = vitalStatus
        self.deathDate = deathDate
        self.gender = gender
        self.races = races
        self.ethnicities = ethnicities
        self.activityStatus = activityStatus
        self.sexGenotype = sexGenotype
        self.pmis = pmis
        self.empi = empi
        self.extensionDetail = extensionDetail


class Registration:
    def __init__(
        self, participant, cpShortTitle, activityStatus, ppid, registrationDate, externalSubjectId, cpId=None
    ):

        self.participant = participant

        #  Only one of the follow required: cpShortTitle, cpId, or cpTitle (not included here because rarely, if ever, used)
        self.cpId = cpId
        self.cpShortTitle = cpShortTitle

        #  Do not enter if CP is set to autogenerate this
        self.ppid = ppid
        self.activityStatus = activityStatus
        self.registrationDate = registrationDate
        self.externalSubjectId = externalSubjectId


class Extension:

    #  needs to default to dict or recieve this error: {"code":"INVALID_REQUEST","message":"JSON parse error: null; nested exception is com.fasterxml.jackson.databind.JsonMappingException: N/A\n at [Source: "}
    def __init__(self, attrsMap=dict):

        self.attrsMap = attrsMap


class Aliquot:
    def __init__(
        self,
        label,
        initialQty,
        availableQty,
        collectionStatus,
        createdOn,
        extensionDetail,
        comments,
        vistId=None,
        parentId=None,
        lineage="Aliquot",
        children=[],
        specimenPool=[],
        storageLocation={},
        closeAfterChildrenCreation=False,
    ):

        self.label = label
        self.initialQty = initialQty
        self.availableQty = availableQty
        self.vistId = vistId
        self.parentId = parentId
        self.lineage = lineage
        self.status = collectionStatus
        self.createdOn = createdOn
        self.extensionDetail = extensionDetail
        self.comments = comments
        self.children = children
        self.specimenPool = specimenPool
        self.storageLocation = storageLocation
        self.closeAfterChildrenCreation = closeAfterChildrenCreation


class Specimen:
    def __init__(
        self,
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
        biohazards=[],
        concentration=None,
        storageLocation={},
    ):

        self.label = label
        self.specimenClass = specimenClass
        self.type = specimenType
        self.anatomicSite = anatomicSite
        self.pathology = pathology
        self.visitId = visitId
        self.lineage = lineage
        self.initialQty = initialQty
        self.availableQty = availableQty
        self.laterality = laterality
        self.status = collectionStatus
        self.extensionDetail = extensionDetail
        self.biohazards = biohazards
        self.concentration = concentration
        self.storageLocation = storageLocation
        self.comments = comments

        self.collectionEvent = collectionEvent
        self.receivedEvent = receivedEvent


class UpdateSpecimen:
    def __init__(
        self,
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
        visitId=None,
        parentId=None,
        visitName=None,
        storageType=None,
    ):

        self.label = label
        self.specimenClass = specimenClass
        self.type = specimenType
        self.anatomicSite = anatomicSite
        self.pathology = pathology
        self.visitId = visitId
        self.lineage = lineage
        self.initialQty = initialQty
        self.availableQty = availableQty
        self.laterality = laterality
        self.status = collectionStatus
        self.extensionDetail = extensionDetail
        self.biohazards = biohazards
        self.concentration = concentration
        self.storageLocation = storageLocation
        self.comments = comments

        self.visitName = visitName
        self.activityStatus = activityStatus
        self.createdOn = createdOn
        self.barcode = barcode
        self.parentId = parentId
        self.storageType = storageType


class Visit:
    def __init__(
        self,
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
        code=None,
    ):

        self.eventId = eventId
        self.eventLabel = eventLabel
        self.ppid = ppid
        self.cpTitle = cpTitle
        self.cpShortTitle = cpShortTitle
        self.name = name
        self.clinicalStatus = clinicalStatus
        self.activityStatus = activityStatus
        self.site = site
        self.status = status
        self.extensionDetail = extensionDetail
        self.missedReason = missedReason
        self.missedBy = missedBy
        self.comments = comments
        self.surgicalPathologyNumber = surgicalPathologyNumber
        self.cohort = cohort
        self.visitDate = visitDate
        self.clinicalDiagnoses = clinicalDiagnoses
        self.eventPoint = eventPoint
        self.cprId = cprId
        self.code = code


class Array:
    def __init__(
        self,
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
        idVal=None,
        activityStatus=None,
    ):

        self.name = name
        self.length = length
        self.width = width
        self.thickness = thickness
        self.numberOfRows = numberOfRows
        self.rowLabelingScheme = rowLabelingScheme
        self.numberOfColumns = numberOfColumns
        self.columnLabelingScheme = columnLabelingScheme
        self.coreDiameter = coreDiameter
        self.creationDate = creationDate
        self.status = status
        self.qualityControl = qualityControl
        self.comments = comments
        self.id = idVal
        self.activityStatus = activityStatus


class Cores:
    def __init__(self, cores=[], vacateExisting=False):

        self.cores = cores
        self.vacateExisting = vacateExisting


# class CPEvent:
#     def __init__(
#         self,
#         eventLabel,
#         eventPoint,
#         collectionProtocol,
#         defaultSite,
#         clinicalDiagnosis,
#         clinicalStatus,
#         activityStatus,
#         code=None,
#     ):

#         self.eventLabel = eventLabel
#         self.eventPoint = eventPoint
#         self.collectionProtocol = collectionProtocol
#         self.defaultSite = defaultSite
#         self.clinicalDiagnosis = clinicalDiagnosis
#         self.clinicalStatus = clinicalStatus
#         self.activityStatus = activityStatus
#         self.code = code


# class CPSpecRequirement:
#     def __init__(self, ):
