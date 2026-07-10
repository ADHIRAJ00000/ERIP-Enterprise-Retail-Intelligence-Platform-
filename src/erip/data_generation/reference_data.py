"""
Reference Data
==============
Hand-curated realistic lookup data used by the synthetic data generators:
names, geography (country -> cities/currency/timezone), product taxonomy,
store types, payment methods, etc.

No external dependency (e.g. Faker) is required - everything needed to
produce convincing enterprise retail data lives here.
"""

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Margaret", "Anthony", "Betty", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Neha", "Arjun", "Divya",
    "Liam", "Olivia", "Noah", "Emma", "Oliver", "Ava", "Elijah", "Sophia",
    "Hiroshi", "Yuki", "Kenji", "Sakura", "Mohammed", "Fatima", "Ahmed", "Aisha",
    "Lucas", "Mia", "Henry", "Isabella", "Felix", "Anna", "Pierre", "Camille",
    "Hans", "Greta", "Klaus", "Ingrid", "Carlos", "Maria", "Diego", "Sofia",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Sharma", "Patel", "Kumar", "Singh", "Gupta", "Reddy", "Nair", "Iyer",
    "Tanaka", "Suzuki", "Watanabe", "Yamamoto", "Mueller", "Schmidt", "Schneider",
    "Dubois", "Bernard", "Rousseau", "Khan", "Ali", "Hussain", "Park", "Kim", "Chen",
]

# Country -> (currency, timezone, list of major cities, ISO code)
COUNTRY_DATA = {
    "United States":        {"currency": "USD", "iso": "US", "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Dallas", "Seattle", "Miami"]},
    "United Kingdom":       {"currency": "GBP", "iso": "GB", "cities": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool"]},
    "Germany":              {"currency": "EUR", "iso": "DE", "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart"]},
    "France":               {"currency": "EUR", "iso": "FR", "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes"]},
    "India":                {"currency": "INR", "iso": "IN", "cities": ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata"]},
    "Canada":               {"currency": "CAD", "iso": "CA", "cities": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"]},
    "Australia":            {"currency": "AUD", "iso": "AU", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"]},
    "Brazil":               {"currency": "BRL", "iso": "BR", "cities": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza"]},
    "Japan":                {"currency": "JPY", "iso": "JP", "cities": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Sapporo"]},
    "United Arab Emirates": {"currency": "AED", "iso": "AE", "cities": ["Dubai", "Abu Dhabi", "Sharjah"]},
}

# Product taxonomy: category -> subcategory -> [brand pool]
PRODUCT_TAXONOMY = {
    "Electronics": {
        "subcategories": ["Smartphones", "Laptops", "Headphones", "Smart Home", "Cameras", "Tablets", "Wearables"],
        "brands": ["Nova", "ZenTech", "Pulsar", "OrbitX", "Quantix", "Vertex", "Hyperion"],
        "price_range": (50, 2500),
    },
    "Apparel": {
        "subcategories": ["Men's Clothing", "Women's Clothing", "Kids Clothing", "Footwear", "Accessories"],
        "brands": ["Urban Thread", "Maple & Co", "Stride", "LuxeLine", "Northfield", "Aria"],
        "price_range": (8, 300),
    },
    "Home & Kitchen": {
        "subcategories": ["Cookware", "Furniture", "Decor", "Bedding", "Appliances", "Storage"],
        "brands": ["HearthCraft", "Domora", "NestWell", "Coral Home", "Aspen Living"],
        "price_range": (10, 1800),
    },
    "Grocery": {
        "subcategories": ["Beverages", "Snacks", "Dairy", "Bakery", "Organic", "Frozen Foods"],
        "brands": ["FreshFields", "PureHarvest", "GreenLeaf", "Golden Valley", "Daily Table"],
        "price_range": (1, 60),
    },
    "Beauty & Personal Care": {
        "subcategories": ["Skincare", "Haircare", "Makeup", "Fragrance", "Bath & Body"],
        "brands": ["Lumin", "Velora", "PureGlow", "Belle Aire", "EssenceCo"],
        "price_range": (4, 220),
    },
    "Sports & Outdoors": {
        "subcategories": ["Fitness Equipment", "Camping", "Cycling", "Team Sports", "Footwear"],
        "brands": ["Summit Gear", "ProActive", "TrailBlaze", "IronCore", "Velocity"],
        "price_range": (10, 1200),
    },
    "Toys & Games": {
        "subcategories": ["Action Figures", "Board Games", "Educational", "Puzzles", "Outdoor Play"],
        "brands": ["PlayNest", "Wonderkid", "BrightMinds", "FunForge"],
        "price_range": (5, 250),
    },
    "Books & Media": {
        "subcategories": ["Fiction", "Non-Fiction", "Children's Books", "Movies", "Music"],
        "brands": ["Inkwell Press", "Northstar Media", "Pageturner"],
        "price_range": (3, 90),
    },
    "Automotive": {
        "subcategories": ["Car Care", "Accessories", "Tools", "Electronics", "Tires"],
        "brands": ["DriveCore", "AutoForge", "RoadMaster", "Torque+"],
        "price_range": (5, 2000),
    },
    "Health & Wellness": {
        "subcategories": ["Vitamins", "Medical Supplies", "Fitness Trackers", "Personal Care"],
        "brands": ["VitaCore", "WellPath", "PureLife", "NutriBalance"],
        "price_range": (5, 450),
    },
}

STORE_TYPES = ["Flagship", "Mall Outlet", "Standalone", "Express", "Warehouse Club", "Online-Only Fulfillment"]

PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Apple Pay", "Google Pay", "Bank Transfer", "Cash on Delivery", "Buy Now Pay Later"]

ORDER_STATUSES = ["Completed", "Shipped", "Processing", "Cancelled", "Returned", "Refunded"]

SHIPPING_CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "BlueDart", "Royal Mail", "Local Courier"]

MARKETING_CHANNELS = ["Email", "Social Media", "Search Ads", "Display Ads", "Influencer", "TV", "Affiliate", "SMS"]

CAMPAIGN_TYPES = ["Seasonal Sale", "Flash Sale", "Loyalty Reward", "New Launch", "Clearance", "Holiday Promo", "Win-back"]

EMPLOYEE_ROLES = [
    "Store Manager", "Assistant Manager", "Sales Associate", "Cashier", "Inventory Specialist",
    "Customer Service Rep", "Regional Director", "Visual Merchandiser", "Loss Prevention", "Warehouse Staff",
]

RETURN_REASONS = [
    "Defective Item", "Wrong Item Shipped", "Changed Mind", "Better Price Found",
    "Item Not as Described", "Late Delivery", "Damaged in Transit", "Size/Fit Issue",
]

CUSTOMER_SEGMENTS = ["New", "Regular", "Loyal", "VIP", "At Risk", "Churned"]

WEATHER_CONDITIONS = ["Sunny", "Rainy", "Cloudy", "Snowy", "Stormy", "Foggy", "Windy"]

US_HOLIDAYS = [
    ("New Year's Day", "01-01"), ("Valentine's Day", "02-14"), ("Memorial Day", "05-27"),
    ("Independence Day", "07-04"), ("Labor Day", "09-02"), ("Halloween", "10-31"),
    ("Thanksgiving", "11-27"), ("Black Friday", "11-28"), ("Cyber Monday", "12-01"),
    ("Christmas", "12-25"), ("New Year's Eve", "12-31"),
]
