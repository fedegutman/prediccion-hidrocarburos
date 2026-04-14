MOCK_WELLS = [
    {"id_well": "POZO-001", "nombre": "Pozo Norte 1", "lugar": "Neuquén", "active": True},
    {"id_well": "POZO-002", "nombre": "Pozo Norte 2", "lugar": "Neuquén", "active": True},
    {"id_well": "POZO-003", "nombre": "Pozo Sur 1",   "lugar": "Mendoza", "active": False},
    {"id_well": "POZO-004", "nombre": "Pozo Este 1",  "lugar": "Chubut",  "active": True},
    {"id_well": "POZO-005", "nombre": "Pozo Norte 3", "lugar": "Neuquén", "active": True},
]

MOCK_BASE_PRODUCTION = {
    "POZO-001": 150.0,
    "POZO-002": 210.5,
    "POZO-003": 98.3,
    "POZO-004": 175.0,
    "POZO-005": 320.8,
}

DAILY_DECLINE: float = 0.5