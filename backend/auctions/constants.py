REGISTRATION_PERIOD = 14  # 2 weeks (REGISTRATION)
AUCTION_START_DELAY = 3  # 3 days after registration ends (UPCOMING)
MAX_ASSETS_PER_AUCTION = 3

MORNING_ASSET_SLOTS = [
    ('09:00:00', '09:50:00'),
    ('10:00:00', '10:50:00'),
    ('11:00:00', '11:50:00'),
]

AFTERNOON_ASSET_SLOTS = [
    ('14:00:00', '14:50:00'),
    ('15:00:00', '15:50:00'),
    ('16:00:00', '16:50:00'),
]

AUCTION_TIME_PERIODS = [
    ('morning', 'Morning'),
    ('afternoon', 'Afternoon'),
]

REGISTRATION_START_TIME = '09:00:00'
REGISTRATION_END_TIME = '17:00:00'

REGISTRATION_FEE = '1000'

DEPOSIT_PERCENTAGES  = {
    'real_estate': 5,
    'vehicles': 10,  
    'artworks_antiques_collectibles': 15,
    'jewelry_luxuries': 20,  
    'technology_electronics_engineering': 10,  
    'others': 15,
}
