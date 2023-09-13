import os, sys, argparse, json, requests, pkgutil
from urllib import parse

default_apikey = "YOUR_API_KEY" # set your api key here

# equal = None
# equalSigns = [
#     ":",
#     "=",
# ]

# delim = None
# delims = [
#     ",",
#     ";",
#     "&",
# ]

newline = "\n"

curlOpts = {
    "allow_redirects": True,
    "stream": False,
    "timeout": 30,
    "verify": False,
}

defaultHeaders = {
    'Content-Type': 'application/json; charset=utf8',
    'User-Agent': 'api_query',
    'apikey': default_apikey,
}

parser = argparse.ArgumentParser(
                    prog=__file__,
                    description='Queries any API with cURL and returns response in JSON format.',
                    epilog='To simplify your everyday life :)')

parser.add_argument('endpoint', help = "The full URL to the endpoint")
parser.add_argument('-k', '--apikey', help = "Your secret API key", default = default_apikey)
parser.add_argument('-m', '--method', help = "What method you want to use, usually POST or GET", type = str, default = "GET")
parser.add_argument('-a', '--args', help = "Arguments to pass to the API", type = str, default = f"")
parser.add_argument('--args-format', help = "Arguments to pass to the API", type = str, default = "basic", choices = ['basic', 'json'])
parser.add_argument('--headers', help = "Specify request headers for this endpoint in JSON format", type = str, default = defaultHeaders)
parser.add_argument('--delim', help = "Specify params delimiter operator", type = str, default = ",")
parser.add_argument('--equal', help = "Specify params equal operator", type = str, default = "=")
parser.add_argument('--verbose', action = "store_true")

args = parser.parse_args()

url             = args.endpoint
apikey          = args.apikey
method          = args.method
headers         = args.headers
api_args        = args.args
api_args_format = args.args_format
verbosemode     = args.verbose
delim           = args.delim
equal           = args.equal

die = exit

def printv(txt: str):
    if verbosemode == True:
        print(f"[VERBOSE] {txt}")

def curl(url: str, method: str, data: dict, headers: dict):
    printv(f"HEADERS: {headers}")
    printv(f"DATA: {data}")
    requests.packages.urllib3.disable_warnings()
    if method.upper() == "POST":
        req = requests.post(url=url, params=data, headers=headers, **curlOpts)
    elif method.upper() == "GET":
        req = requests.get(url=url, params=data, headers=headers, **curlOpts)
    else:
        req = requests.request(method=method, url=url, params=data, headers=headers, **curlOpts)
    printv(req)
    return req



if api_args != "":
    api_args_dict = {}
    if api_args_format == 'json':
        api_args_dict = json.loads(api_args)
    if api_args_format == "basic":
        # # # determine equal operator
        # for eq in equalSigns:
        #     if eq in api_args:
        #         if equal != None: exit(f"More than one equal operator in your API argument list: {api_args}")
        #         else: equal = eq

        # # determine delim operator
        # for d in delims:
        #     if d in api_args:
        #         if delim != None: exit(f"More than one equal operator in your API argument list: {api_args}")
        #         else: delim = d

        api_args_split = api_args.split(delim)
        for kv in api_args_split:
            var = kv.split(equal)[0]
            val = kv.split(equal)[1]
            api_args_dict[var] = val

    api_args_dict["apikey"] = apikey
else:
    api_args_dict = {"apikey": apikey}

parsed_url = parse.urlsplit(url)
url_params = parse.parse_qsl(parsed_url.query)
for up in url_params:
    k = up[0]
    v = up[1]
    api_args_dict[k] = v

res = curl(url=url, method=method, headers=headers, data=api_args_dict)

http_code = res.status_code
content   = res.content

print(content.decode())