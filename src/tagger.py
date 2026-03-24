REGION_KEYWORDS = {
    "Europe": [
        "ukraine","poland","nato","romania","baltic","russia",
        "europe","eastern flank"
    ],
    "Indo-Pacific": [
        "taiwan","japan","south china sea","philippines","korea",
        "china","indo-pacific"
    ],
    "Middle East": [
        "middle east","iran","israel","gaza","red sea","syria",
        "iraq","houthi","saudi","uae","gulf","yemen"
    ],
    "Africa": [
        "sahel","sudan","somalia","niger","mali","burkina faso"
    ],
}

REGION_TO_COMMAND = {
    "Europe": "EUCOM",
    "Middle East": "CENTCOM",
    "Indo-Pacific": "INDOPACOM",
    "Africa": "AFRICOM",
}

DOMAIN_KEYWORDS = {
    "Counter-UAS": ["drone","uav","counter-uas","counter drone"],
    "Air Defense": ["air defense","missile defense","integrated air defense"],
    "ISR": ["surveillance","reconnaissance","sensor","intelligence","isr"],
    "Cyber": ["cyber","hacking","malware","network intrusion","cyber attack"],
    "Space": ["satellite","space","orbital"],
    "Maritime": ["naval","fleet","submarine","maritime","patrols"],
}

CONFLICT_AREAS = {
    "Ukraine War": ["ukraine","crimea","black sea"],
    "Taiwan Strait": ["taiwan","taiwan strait"],
    "South China Sea": ["south china sea","spratly","paracel"],
    "Red Sea Crisis": ["red sea","houthi","bab el-mandeb"],
    "Gaza Conflict": ["gaza","hamas","israel"],
}

RISK_TYPES = {
    "Military Escalation": [
        "attack","strike","escalation","offensive","deployment",
        "incursion","mobilization","conflict"
    ],
    "Defense Modernization": [
        "modernization","upgrade","procurement","acquisition","contract"
    ],
    "Alliance Activity": [
        "nato","alliance","joint exercise","coalition","partner"
    ],
    "Technology Competition": [
        "ai","hypersonic","cyber","autonomy","counter-uas","satellite"
    ],
}

def detect_category(text, mapping):
    text = text.lower()
    for category, keywords in mapping.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return None

def tag_article(article):
    text = f"{article.get('title','')} {article.get('summary','')}".lower()

    region = detect_category(text, REGION_KEYWORDS)
    command = REGION_TO_COMMAND.get(region) if region else None
    domain = detect_category(text, DOMAIN_KEYWORDS)
    conflict_area = detect_category(text, CONFLICT_AREAS)
    risk_type = detect_category(text, RISK_TYPES)

    return {
        "region": region,
        "combatant_command": command,
        "domain": domain,
        "conflict_area": conflict_area,
        "risk_type": risk_type,
    }
