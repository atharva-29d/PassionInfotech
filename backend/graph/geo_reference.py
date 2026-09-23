"""
geo_reference.py

Fixed synthetic geographic reference data. Contains real public CIDR blocks 
for a small set of representative countries across 5 continents. 
Used to deterministically assign plausible geographic data to synthetic hosts.
"""
import ipaddress
import hashlib

# Real public allocated CIDR ranges for these countries to make IPs look realistic.
# These are small chunks of publicly known IP spaces.
GEO_REFERENCE = {
    "North America": {
        "United States": {
            "regions": ["California", "New York"],
            "cidr": "104.16.0.0/14" # Cloudflare US-ish range
        },
        "Canada": {
            "regions": ["Ontario", "British Columbia"],
            "cidr": "142.250.0.0/15" # Google-ish block
        },
        "Mexico": {
            "regions": ["Mexico City", "Jalisco"],
            "cidr": "200.33.0.0/16" 
        }
    },
    "Europe": {
        "United Kingdom": {
            "regions": ["London", "Manchester"],
            "cidr": "51.140.0.0/14" # Azure UK-ish range
        },
        "Germany": {
            "regions": ["Berlin", "Bavaria"],
            "cidr": "85.214.0.0/15" # Strato DE
        },
        "France": {
            "regions": ["Île-de-France", "Provence-Alpes-Côte d'Azur"],
            "cidr": "212.27.0.0/16" # Free SAS FR
        }
    },
    "Asia": {
        "Japan": {
            "regions": ["Tokyo", "Osaka"],
            "cidr": "133.0.0.0/12" # Japan academic/commercial
        },
        "India": {
            "regions": ["Maharashtra", "Karnataka"],
            "cidr": "14.139.0.0/16" # NKN India
        },
        "Singapore": {
            "regions": ["Central Region", "East Region"],
            "cidr": "118.200.0.0/16" # StarHub SG
        }
    },
    "Oceania": {
        "Australia": {
            "regions": ["New South Wales", "Victoria"],
            "cidr": "1.128.0.0/11" # Telstra AU
        },
        "New Zealand": {
            "regions": ["Auckland", "Wellington"],
            "cidr": "122.56.0.0/14" # Spark NZ
        },
        "Fiji": {
            "regions": ["Central", "Western"],
            "cidr": "103.24.196.0/22" 
        }
    },
    "Africa": {
        "South Africa": {
            "regions": ["Gauteng", "Western Cape"],
            "cidr": "105.236.0.0/14" # Vodacom ZA
        },
        "Nigeria": {
            "regions": ["Lagos", "Abuja"],
            "cidr": "197.210.0.0/16" # MTN NG
        },
        "Egypt": {
            "regions": ["Cairo", "Alexandria"],
            "cidr": "41.32.0.0/14" # Telecom Egypt
        }
    }
}

# Flatten into a deterministically ordered list for hashing purposes
COUNTRY_LIST = []
for continent, countries in sorted(GEO_REFERENCE.items()):
    for country, details in sorted(countries.items()):
        COUNTRY_LIST.append({
            "continent": continent,
            "country": country,
            "regions": sorted(details["regions"]),
            "cidr": details["cidr"]
        })

def get_deterministic_geo(host_id: str) -> dict:
    """
    Given a host_id, deterministically derives continent, country, region, and IP address.
    """
    # 1. Deterministic index for country
    country_hash = int(hashlib.md5(f"{host_id}_country".encode()).hexdigest(), 16)
    country_data = COUNTRY_LIST[country_hash % len(COUNTRY_LIST)]
    
    # 2. Deterministic index for region
    region_hash = int(hashlib.md5(f"{host_id}_region".encode()).hexdigest(), 16)
    region = country_data["regions"][region_hash % len(country_data["regions"])]
    
    # 3. Deterministic IP address within CIDR
    network = ipaddress.IPv4Network(country_data["cidr"], strict=False)
    ip_hash = int(hashlib.md5(f"{host_id}_ip".encode()).hexdigest(), 16)
    # Get total number of hosts in network
    num_hosts = network.num_addresses
    # Pick a deterministic offset (skip network and broadcast if possible)
    offset = (ip_hash % (num_hosts - 2)) + 1 if num_hosts > 2 else ip_hash % num_hosts
    ip_address = str(network[offset])
    
    return {
        "host_id": host_id,
        "continent": country_data["continent"],
        "country": country_data["country"],
        "region": region,
        "ip_address": ip_address
    }
