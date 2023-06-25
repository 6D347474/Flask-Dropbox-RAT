CREATE TABLE Client(
    hwid TEXT PRIMARY KEY NOT NULL,
    lastIP TEXT,
    lastPingTimestampMS INTEGER,
    lastConfig TEXT,
    infectedTimestampMS TEXT
);

CREATE TABLE Command(
    ID INTEGER PRIMARY KEY NOT NULL,
    issuedTimestampMS INTEGER,
    body TEXT,
    clientID TEXT,
    FOREIGN KEY (clientID) REFERENCES Client(hwid)
);