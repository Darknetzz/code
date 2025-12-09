import requests
import json
import time
import sys
import urllib3

# Disable SSL verification warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from auth import NPM_HOST, USERNAME, PASSWORD, NO_ACCESS_LIST_ID

# --- DRY RUN MODE ---
DRY_RUN = False  # Set to False to actually apply changes
TEST_MODE = False  # Set to False to process all hosts; when True, only processes the first host
print(f"{'⚠️  DRY RUN MODE' if DRY_RUN else '🔥 LIVE MODE'} - Changes will {'NOT ' if DRY_RUN else ''}be applied")
if TEST_MODE:
    print("📋 TEST MODE - Only processing first host")
print()

# --- 1. Get Authentication Token ---
try:
    auth_response = requests.post(f"{NPM_HOST}/api/tokens",
                                  json={"identity": USERNAME, "secret": PASSWORD},
                                  verify=False)
    auth_response.raise_for_status()
    response_json = auth_response.json()
    
    # NPMPlus uses session-based auth via cookies
    token = response_json.get('token')

    # Create a persistent session to maintain auth cookies across requests
    session = requests.Session()
    session.cookies.update(auth_response.cookies)
    
    HEADERS = {"Content-Type": "application/json"}
    if token:
        HEADERS["Authorization"] = f"Bearer {token}"
    
    print("✅ Authentication established.")
except requests.exceptions.RequestException as e:
    print(f"❌ Authentication failed: {e}")
    exit(1)

# --- 2. Get All Hosts and Reload Configs ---
try:
    hosts_response = session.get(f"{NPM_HOST}/api/nginx/proxy-hosts", headers=HEADERS, verify=False)
    hosts_response.raise_for_status()
    hosts = hosts_response.json()

    print(f"\n🔄 Found {len(hosts)} hosts. Starting mass configuration reload...")
    if TEST_MODE:
        # Find first enabled host for testing
        enabled_hosts = [h for h in hosts if h.get('enabled', True)]
        if enabled_hosts:
            hosts = enabled_hosts[:1]
            print(f"   (Test mode: processing only first enabled host)")
        else:
            print(f"   (Test mode: no enabled hosts found)")
            hosts = []

    for host in hosts:
        host_id = host['id']
        domain = host['domain_names'][0] if host['domain_names'] else f"ID {host_id}"
        original_access_list_id = host.get('access_list_id') or NO_ACCESS_LIST_ID

        # Skip disabled hosts
        if not host.get('enabled', True):
            print(f"\nSkipping {domain} (ID: {host_id}) - disabled")
            continue

        print(f"\nProcessing {domain} (ID: {host_id})...")

        # Build a payload with only the fields NPMPlus accepts
        # Extract only the editable fields to avoid "additional properties" error
        update_payload = {
            "domain_names": host.get('domain_names', []),
            "forward_scheme": host.get('forward_scheme', 'http'),
            "forward_host": host.get('forward_host', ''),
            "forward_port": host.get('forward_port', 80),
            "certificate_id": host.get('certificate_id'),
            "ssl_forced": host.get('ssl_forced', False),
            "caching_enabled": host.get('caching_enabled', False),
            "block_exploits": host.get('block_exploits', False),
            "advanced_config": host.get('advanced_config', ''),
            "allow_websocket_upgrade": host.get('allow_websocket_upgrade', False),
            "http2_support": host.get('http2_support', False),
            "access_list_id": host.get('access_list_id'),
            "hsts_enabled": host.get('hsts_enabled', False),
            "hsts_subdomains": host.get('hsts_subdomains', False),
            "enabled": host.get('enabled', True),
        }

        # --- Sub-step A: Certificate & Enabled Toggle (Fix 1) ---
        # Toggle 'enabled' off then on to force certificate/config reload
        print("  - Toggling 'enabled' (Disabling/Re-enabling) for cert/config refresh...")
        update_payload['enabled'] = False
        if not DRY_RUN:
            session.put(f"{NPM_HOST}/api/nginx/proxy-hosts/{host_id}",
                         headers=HEADERS, json=update_payload, verify=False).raise_for_status()
        else:
            print(f"    [DRY RUN] PUT {NPM_HOST}/api/nginx/proxy-hosts/{host_id} with enabled=False")
        time.sleep(0.5)

        update_payload['enabled'] = True
        if not DRY_RUN:
            response = session.put(f"{NPM_HOST}/api/nginx/proxy-hosts/{host_id}",
                         headers=HEADERS, json=update_payload, verify=False)
            response.raise_for_status()
        else:
            print(f"    [DRY RUN] PUT {NPM_HOST}/api/nginx/proxy-hosts/{host_id} with enabled=True")


        # --- Sub-step B: Access List Toggle (Fix 2) ---
        # Toggle 'access_list_id' to 0 then back to original value to force ACL rewrite
        if original_access_list_id != NO_ACCESS_LIST_ID:
            print(f"  - Toggling 'access_list_id' (to {NO_ACCESS_LIST_ID} then back to {original_access_list_id}) for ACL refresh...")

            # 1. Change to No Access List (0)
            update_payload['access_list_id'] = NO_ACCESS_LIST_ID
            if not DRY_RUN:
                session.put(f"{NPM_HOST}/api/nginx/proxy-hosts/{host_id}",
                             headers=HEADERS, json=update_payload, verify=False).raise_for_status()
            else:
                print(f"    [DRY RUN] PUT {NPM_HOST}/api/nginx/proxy-hosts/{host_id} with access_list_id={NO_ACCESS_LIST_ID}")
            time.sleep(0.5)

            # 2. Change back to Original Access List ID
            update_payload['access_list_id'] = original_access_list_id
            if not DRY_RUN:
                session.put(f"{NPM_HOST}/api/nginx/proxy-hosts/{host_id}",
                             headers=HEADERS, json=update_payload, verify=False).raise_for_status()
            else:
                print(f"    [DRY RUN] PUT {NPM_HOST}/api/nginx/proxy-hosts/{host_id} with access_list_id={original_access_list_id}")
            
        print(f"  -> Host {domain} {'would be' if DRY_RUN else 'successfully'} reloaded for both Certs and ACLs.")
        time.sleep(1) # Wait briefly before hitting the next host

except requests.exceptions.RequestException as e:
    print(f"\n❌ An API error occurred during processing: {e}")
    print("Please check the host ID or verify the structure of the JSON payload.")

if DRY_RUN:
    print("\n✨ Dry run complete! Review the changes above, then set DRY_RUN = False to apply.")
else:
    print("\n✨ All hosts processed. Check your services now.")