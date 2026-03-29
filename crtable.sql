PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS charge;
DROP TABLE IF EXISTS service;
DROP TABLE IF EXISTS card_access_log;
DROP TABLE IF EXISTS access_card;
DROP TABLE IF EXISTS room_assignment;
DROP TABLE IF EXISTS stay;
DROP TABLE IF EXISTS billing_party;
DROP TABLE IF EXISTS room_reservation;
DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS event_room;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS host;
DROP TABLE IF EXISTS guest;
DROP TABLE IF EXISTS person_organization;
DROP TABLE IF EXISTS organization;
DROP TABLE IF EXISTS person;
DROP TABLE IF EXISTS suite_details;
DROP TABLE IF EXISTS meeting_room_details;
DROP TABLE IF EXISTS sleeping_room_details;
DROP TABLE IF EXISTS room_adjacency;
DROP TABLE IF EXISTS room_bed;
DROP TABLE IF EXISTS bed_type;
DROP TABLE IF EXISTS room;
DROP TABLE IF EXISTS floor;
DROP TABLE IF EXISTS wing;
DROP TABLE IF EXISTS building;

CREATE TABLE building (
    buildingID      INTEGER PRIMARY KEY,
    buildingName    TEXT NOT NULL
);

CREATE TABLE wing (
    wingID               INTEGER PRIMARY KEY,
    buildingID           INTEGER NOT NULL,
    wingName             TEXT NOT NULL,
    proximityPool        INTEGER,
    proximityParking     INTEGER,
    handicappedAccess    INTEGER,
    FOREIGN KEY (buildingID) REFERENCES building(buildingID)
);

CREATE TABLE floor (
    floorID               INTEGER PRIMARY KEY,
    wingID                INTEGER NOT NULL,
    floorNumber           INTEGER NOT NULL,
    smokingDesignation    TEXT,
    FOREIGN KEY (wingID) REFERENCES wing(wingID)
);

CREATE TABLE room (
    roomID         INTEGER PRIMARY KEY,
    floorID        INTEGER NOT NULL,
    roomNumber     TEXT NOT NULL,
    baseRate       REAL,
    roomStatus     TEXT,
    FOREIGN KEY (floorID) REFERENCES floor(floorID)
);

CREATE TABLE bed_type (
    bedTypeId      INTEGER PRIMARY KEY,
    size           TEXT NOT NULL
);

CREATE TABLE room_bed (
    bedTypeId      INTEGER NOT NULL,
    roomId         INTEGER NOT NULL,
    quantity       INTEGER NOT NULL,
    PRIMARY KEY (bedTypeId, roomId),
    FOREIGN KEY (bedTypeId) REFERENCES bed_type(bedTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomID),
    CHECK (quantity > 0)
);

CREATE TABLE room_adjacency (
    roomId1           INTEGER NOT NULL,
    roomId2           INTEGER NOT NULL,
    hasPrivateDoor    INTEGER,
    PRIMARY KEY (roomId1, roomId2),
    FOREIGN KEY (roomId1) REFERENCES room(roomID),
    FOREIGN KEY (roomId2) REFERENCES room(roomID),
    CHECK (roomId1 <> roomId2)
);

CREATE TABLE sleeping_room_details (
    roomID        INTEGER PRIMARY KEY,
    capacity      INTEGER,
    smoking       INTEGER,
    hasToilet     INTEGER,
    hasTV         INTEGER,
    hasPhone      INTEGER,
    FOREIGN KEY (roomID) REFERENCES room(roomID)
);

CREATE TABLE meeting_room_details (
    roomID             INTEGER PRIMARY KEY,
    seatingCapacity    INTEGER,
    FOREIGN KEY (roomID) REFERENCES room(roomID)
);

CREATE TABLE suite_details (
    roomID             INTEGER PRIMARY KEY,
    sleepingRoomID     INTEGER,
    meetingRoomID      INTEGER,
    FOREIGN KEY (roomID) REFERENCES room(roomID),
    FOREIGN KEY (sleepingRoomID) REFERENCES room(roomID),
    FOREIGN KEY (meetingRoomID) REFERENCES room(roomID)
);

CREATE TABLE person (
    personId       INTEGER PRIMARY KEY,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    phone          TEXT,
    email          TEXT
);

CREATE TABLE organization (
    organizationId   INTEGER PRIMARY KEY
);

CREATE TABLE person_organization (
    personId         INTEGER NOT NULL,
    organizationId   INTEGER NOT NULL,
    PRIMARY KEY (personId, organizationId),
    FOREIGN KEY (personId) REFERENCES person(personId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId)
);

CREATE TABLE guest (
    guestId      INTEGER PRIMARY KEY,
    FOREIGN KEY (guestId) REFERENCES person(personId)
);

CREATE TABLE host (
    hostId       INTEGER PRIMARY KEY,
    FOREIGN KEY (hostId) REFERENCES person(personId)
);

CREATE TABLE billing_party (
    billingPartyId   INTEGER PRIMARY KEY,
    personId         INTEGER,
    organizationId   INTEGER,
    FOREIGN KEY (personId) REFERENCES person(personId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId),
    CHECK (personId IS NOT NULL OR organizationId IS NOT NULL)
);

CREATE TABLE reservation (
    reservationId      INTEGER PRIMARY KEY,
    billingPartyId     INTEGER NOT NULL,
    reservationDate    TEXT NOT NULL,
    depositRequired    INTEGER,
    estimatedGuests    INTEGER,
    FOREIGN KEY (billingPartyId) REFERENCES billing_party(billingPartyId)
);

CREATE TABLE room_reservation (
    reservationId    INTEGER NOT NULL,
    roomId           INTEGER NOT NULL,
    startDateTime    TEXT NOT NULL,
    endDateTime      TEXT NOT NULL,
    PRIMARY KEY (reservationId, roomId),
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId),
    FOREIGN KEY (roomId) REFERENCES room(roomID),
    CHECK (endDateTime > startDateTime)
);

CREATE TABLE stay (
    stayId        INTEGER PRIMARY KEY,
    guestId       INTEGER NOT NULL,
    checkIn       TEXT NOT NULL,
    checkOut      TEXT NOT NULL,
    FOREIGN KEY (guestId) REFERENCES guest(guestId),
    CHECK (checkOut > checkIn)
);

CREATE TABLE room_assignment (
    stayId           INTEGER NOT NULL,
    roomId           INTEGER NOT NULL,
    assignedFrom     TEXT NOT NULL,
    assignedTo       TEXT,
    PRIMARY KEY (stayId, roomId, assignedFrom),
    FOREIGN KEY (stayId) REFERENCES stay(stayId),
    FOREIGN KEY (roomId) REFERENCES room(roomID),
    CHECK (assignedTo IS NULL OR assignedTo > assignedFrom)
);

CREATE TABLE access_card (
    cardId       INTEGER PRIMARY KEY,
    guestId      INTEGER NOT NULL,
    pin          TEXT NOT NULL,
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
);

CREATE TABLE card_access_log (
    logId         INTEGER PRIMARY KEY,
    cardId        INTEGER NOT NULL,
    roomId        INTEGER NOT NULL,
    accessTime    TEXT NOT NULL,
    direction     TEXT,
    FOREIGN KEY (cardId) REFERENCES access_card(cardId),
    FOREIGN KEY (roomId) REFERENCES room(roomID),
    CHECK (direction IN ('enter', 'exit'))
);

CREATE TABLE event (
    eventId                 INTEGER PRIMARY KEY,
    hostId                  INTEGER NOT NULL,
    startDate               TEXT NOT NULL,
    endDate                 TEXT NOT NULL,
    estimatedAttendance     INTEGER,
    estimatedGuestRooms     INTEGER,
    FOREIGN KEY (hostId) REFERENCES host(hostId),
    CHECK (endDate > startDate)
);

CREATE TABLE event_room (
    eventId       INTEGER NOT NULL,
    roomId        INTEGER NOT NULL,
    usageSlot     TEXT NOT NULL,
    PRIMARY KEY (eventId, roomId, usageSlot),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (roomId) REFERENCES room(roomID)
);

CREATE TABLE service (
    serviceId      INTEGER PRIMARY KEY,
    serviceType    TEXT NOT NULL
);

CREATE TABLE charge (
    chargeId          INTEGER PRIMARY KEY,
    serviceId         INTEGER NOT NULL,
    billingPartyId    INTEGER NOT NULL,
    roomId            INTEGER,
    amount            REAL NOT NULL,
    chargeDateTime    TEXT NOT NULL,
    description       TEXT,
    FOREIGN KEY (serviceId) REFERENCES service(serviceId),
    FOREIGN KEY (billingPartyId) REFERENCES billing_party(billingPartyId),
    FOREIGN KEY (roomId) REFERENCES room(roomID),
    CHECK (amount >= 0)
);
