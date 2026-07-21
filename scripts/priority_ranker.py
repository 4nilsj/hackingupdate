import sys
import json
import requests
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("priority_ranker")

# Keyword heuristic fallback rules (comprehensive list)
FALLBACK_KEYWORDS = {
    "web": [
        "web", "xss", "csrf", "sqli", "injection", "ssrf", "lfi", "rfi", "rce", "http", "cors", "browser", 
        "wordpress", "drupal", "joomla", "apache", "nginx", "iis", "auth", "jwt", "html", "javascript", 
        "clickjacking", "session fixation", "open redirect", "idor", "xxe", "web shell", "reverse shell", 
        "server-side", "client-side", "websocket", "cookie", "deserialization", "tomcat", "weblogic", "wildfly",
        "php", "jsp", "asp", "aspx", "nodejs", "express", "laravel", "django", "flask"
    ],
    "mobile": [
        "mobile", "android", "ios", "apk", "ipa", "frida", "obfuscation", "intent", "activity", "plist", 
        "keychain", "keystore", "swift", "kotlin", "objc", "jailbreak", "rooting", "root", "deeplink", 
        "deep link", "app link", "universal link", "sqlite", "ipc", "exported", "webview", "ssl pinning", 
        "pinning bypass", "apktool", "dex2jar", "smali", "mdm", "mobile device management"
    ],
    "API": [
        "api", "graphql", "rest", "soap", "json", "swagger", "endpoint", "oauth", "bearer", "token", 
        "apikeys", "restful", "openapi", "postman", "rate limit", "rate limiting", "bola", "bfla", 
        "mass assignment", "api gateway", "apigee", "kong", "wso2", "mulesoft", "xml-rpc", "jwks"
    ],
    "network": [
        "network", "router", "switch", "dns", "dhcp", "tcp", "udp", "port", "ssh", "vpn", "ipsec", 
        "smb", "rdp", "snmp", "wireshark", "protocol", "firewall", "wi-fi", "wpa", "wep", "mitm", 
        "arp", "spoofing", "dns hijacking", "sniffing", "packet", "vlan", "trunking", "routing", 
        "bgp", "ospf", "icmp", "ddos", "syn flood", "metasploit", "nmap", "nessus", "shodan", "censys"
    ],
    "thickclient": [
        "thickclient", "thick-client", "desktop", "dll", "activex", "exe", "binary", "reverse engineering", 
        "decompile", "java fx", "dotnet", ".net", "c++", "c#", "desktop app", "wpf", "electron", 
        "dll hijacking", "dll injection", "process hollowing", "memory dump", "cheat engine", 
        "ollydbg", "x64dbg", "ghidra", "ida pro", "dnspy", "assembly", "binary analysis", "buffer overflow", 
        "stack overflow", "heap overflow", "heap-based", "heap spray", "use-after-free", "double free"
    ],
    "cloud": [
        "cloud", "aws", "azure", "gcp", "s3", "iam", "lambda", "kubernetes", "k8s", "docker", 
        "container", "ec2", "blob", "serverless", "terraform", "s3 bucket", "iam policy", "iam role", 
        "metadata service", "imds", "imdsv2", "ecs", "eks", "gke", "cloudtrail", "cloudwatch", 
        "entra id", "entra", "storage account", "key vault", "kube-apiserver", "docker socket", 
        "container escape", "helm", "dashboard", "fargate"
    ],
    "infra": [
        "infra", "active directory", "domain controller", "ldap", "windows server", "linux", "kernel", 
        "firmware", "cisco", "fortinet", "vmware", "hypervisor", "esxi", "database", "postgres", 
        "mysql", "oracle", "kerberoasting", "as-rep", "golden ticket", "silver ticket", "pass-the-hash", 
        "pth", "pass-the-ticket", "ptt", "mimikatz", "bloodhound", "gpo", "group policy", "dc", 
        "smb signing", "ntlm", "ntlmv2", "relay attack", "responder", "llmnr", "nbt-ns", "wsus", 
        "sccm", "hyper-v", "proxmox", "kvm", "docker-compose", "openssl", "heartbleed"
    ],
    "news": [
        "breach", "cyberattack", "hack", "ransomware", "data leak", "policy", "regulation", "lawsuit",
        "ai security", "threat actor", "apt", "group", "incident", "advisory", "security news", "stolen"
    ]
}

def fallback_rank_and_tag(article):
    title_lower = article["title"].lower()
    content_lower = article["content_text"].lower()
    combined = f"{title_lower} {content_lower}"
    
    assigned_tags = []
    for tag, keywords in FALLBACK_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                assigned_tags.append(tag)
                break
                
    # Comprehensive ranking heuristic based on critical keywords
    rank = 3
    critical_kws = [
        "exploit", "poc", "rce", "zero-day", "0-day", "critical", "bypass", "unauthenticated", 
        "remote code execution", "privilege escalation", "proof of concept", "proof-of-concept", 
        "active exploitation", "actively exploited", "wild", "0day", "cve-", "unauth", "writeup", 
        "write-up", "root access", "arbitrary code", "command injection", "cisa kev", "known exploited",
        "malware", "ransomware", "backdoor", "cred", "leak", "authenticator", "key leakage"
    ]
    for kw in critical_kws:
        if kw in combined:
            rank += 1
            
    # Cap rank at 10
    rank = min(rank, 10)
    
    # If no tag is found, tag as network or infra if standard terms appear, else network
    if not assigned_tags:
        assigned_tags.append("network")
        
    return {
        "id": article["id"],
        "rank": rank,
        "tags": list(set(assigned_tags)),
        "reason": f"Fallback: Tagged via keyword heuristics matching {[t for t in assigned_tags]}."
    }

def rank_batch_with_llm(batch):
    if not config.OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set. Using keyword-based fallback ranking.")
        return [fallback_rank_and_tag(art) for art in batch]

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/google/antigravity",
        "X-Title": "HackingUpdate Agent"
    }

    # Prepare lightweight payload for LLM to rank
    simplified_articles = []
    for art in batch:
        # Keep title and first 400 chars of content to save tokens
        content_preview = art["content_text"][:400] + ("..." if len(art["content_text"]) > 400 else "")
        simplified_articles.append({
            "id": art["id"],
            "title": art["title"],
            "source": art["source"],
            "content_preview": content_preview
        })

    prompt = f"""
Analyze the following security updates/vulnerabilities.
For each article:
1. Assign a priority rank from 1 to 10 (1 = low interest news, 10 = highly actionable vulnerability, zero-day, exploitation TTP, or tool release of critical interest to a professional pentester).
2. Assign one or more tags from this list to classify it: {config.PENTEST_TAGS}.
3. Provide a brief 1-sentence explanation of why it was ranked this way.

Articles:
{json.dumps(simplified_articles, indent=2)}

You MUST return ONLY a valid JSON object in the following format (do not wrap in markdown code blocks, just raw JSON):
{{
  "rankings": [
    {{
      "id": "article_id",
      "rank": 8,
      "tags": ["web", "API"],
      "reason": "Description of why..."
    }}
  ]
}}
"""

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional Cyber Security Threat Intelligence analyst specializing in penetration testing and vulnerability analysis."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        res_data = response.json()
        
        choices = res_data.get("choices", [])
        if not choices:
            raise ValueError(f"Empty choices from OpenRouter response: {res_data}")
            
        content_str = choices[0]["message"]["content"].strip()
        # Parse JSON
        results = json.loads(content_str)
        rankings = results.get("rankings", [])
        
        # Build dictionary by ID for quick mapping
        rankings_map = {r["id"]: r for r in rankings if "id" in r}
        
        final_batch = []
        for art in batch:
            art_id = art["id"]
            if art_id in rankings_map:
                final_batch.append({
                    "id": art_id,
                    "rank": int(rankings_map[art_id].get("rank", 5)),
                    "tags": rankings_map[art_id].get("tags", ["network"]),
                    "reason": rankings_map[art_id].get("reason", "Ranked by LLM.")
                })
            else:
                logger.warning(f"LLM missed ranking for article ID: {art_id}. Using fallback.")
                final_batch.append(fallback_rank_and_tag(art))
                
        return final_batch

    except Exception as e:
        logger.error(f"OpenRouter API call failed: {e}. Falling back to keyword ranking.")
        return [fallback_rank_and_tag(art) for art in batch]

def main():
    if not config.DEDUPED_CACHE_FILE.exists():
        logger.error(f"Deduped cache file not found: {config.DEDUPED_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.DEDUPED_CACHE_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load deduped cache file: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(articles)} articles for priority ranking.")
    ranked_results = []
    
    # Process in batches of 15 articles to optimize performance and prevent rate limiting
    batch_size = 15
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        logger.info(f"Ranking batch {i//batch_size + 1} of {(len(articles)-1)//batch_size + 1} ({len(batch)} articles)...")
        batch_ranked = rank_batch_with_llm(batch)
        
        # Combine ranking metadata with original article details
        for art, rank_meta in zip(batch, batch_ranked):
            combined_art = art.copy()
            combined_art["rank"] = rank_meta["rank"]
            combined_art["tags"] = rank_meta["tags"]
            combined_art["rank_reason"] = rank_meta["reason"]
            ranked_results.append(combined_art)

    # Sort results by rank (descending order, highest first)
    ranked_results.sort(key=lambda x: x.get("rank", 0), reverse=True)

    try:
        with open(config.RANKED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ranked_results, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved {len(ranked_results)} ranked articles to {config.RANKED_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save ranked cache: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
