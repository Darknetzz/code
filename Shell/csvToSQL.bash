#!/bin/bash

# ---------------------------------------------------------------------------- #
#                             Initial configuration                            #
# ---------------------------------------------------------------------------- #
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
csvsqlBin=$(which csvsql)                       # csvsql binary
pythonBin=$(which python3)                      # python binary
chunk_size=100000                               # how many rows to import per iteration
pipBin="$pythonBin -m pip"                      # python pip binary
connectionConfigFile="$SCRIPT_DIR/sqlcon.bash"  # sql configuration file
connector="mysql+mysqlconnector"                # type of sql connector
verbose="--verbose"                             # the flag or empty if non-verbose
additionalFlags="--no-create $verbose --insert --blanks"    # csvsql command line parameters
csv_separator=','
c_red="\033[0;31m"
c_yellow="\033[1;33m"
c_green="\033[0;32m"
c_cyan="\033[0;36m"
c_end="\033[0m"

# ---------------------------------------------------------------------------- #
#                                   Functions                                  #
# ---------------------------------------------------------------------------- #
hr() {
    echo "----------------------------"
}

inf() {
    printf "ℹ️ ${c_cyan}%s${c_end}\n" "$1"
}

warn() {
    printf "❗ ${c_yellow}%s${c_end}\n" "$1"
}

err() {
    printf "❌ ${c_red}%s${c_end}\n" "$1"
    exit 1
}

succ() {
    printf "✅ ${c_green}%s${c_end}\n" "$1"
}

dot() {
    printf "🔵 ${c_cyan}%s${c_end}\n" "$1"
}

checkAptPackage() {
    # checkPackage=$(apt-get list "$1")
    checkPackage=$(dpkg -l | grep "$1")
    if [[ ! $checkPackage ]]; then
        inf "Package $1 doesn't seem to be installed. Attempting to install..."
        command=$(apt-get install "$1" -y)
        if [ ! "$command" ]; then
            err "Installing $1 failed. Please run 'apt install $1' manually."
        else
            succ "Package $1 installed!"
        fi
    else
        succ "Package $1 already installed!"
    fi
}


checkPythonPackage() {
    checkPackage=$($pipBin list | grep -F "$1")
    if [[ ! $checkPackage ]]; then
        inf "Python dependency $1 doesn't seem to be installed. Attempting to install..."
        command=$(pip install --upgrade "$1")
        if [ ! "$command" ]; then
            err "Installing $1 failed. Please run 'pip install --upgrade $1' manually."
        else
            succ "Dependency $1 successfully installed!"
        fi
    else
        succ "Python dependency $1 already installed!"
    fi
}

showHelp() {
    hr
    inf "Help"
    echo "You can run this bash script with the following parameters:"
    echo "./csvtosql [FLAGS] [CSVFILE]"
    echo
    echo "Flags:"
    echo "[-h] Help"
    echo "[-f] Fast (skip pre-checks)"
    hr
    exit 0
}

str_split() {
    if [ ! "$1" ]  ||  [ ! "$2" ]; then
        warn "str_split was used without 2 parameters."
        exit 1
    fi
    input="$1"
    delimiter="$2"
    arr=(${input//delimiter/ })
    echo ${arr[@]}
}

prompt() {
    read -p "$1 [Y/n] " -n 1 -r
    killonno="$2"

    echo
    if [[ $REPLY =~ ^[Yy]$ || $REPLY == "" ]]; then
        reply=true
    else
        reply=false
        if [ "$killonno" == true ]; then
            err "Exiting..."
        fi
    fi
}


hr

# ---------------------------------------------------------------------------- #
#                                 Custom flags                                 #
# ---------------------------------------------------------------------------- #
if [ $# -eq 0 ]; then
    inf "You ran this script without any parameters. You will be prompted for input.
To avoid this next time, run this script with the -[h]elp parameter."
else
    while getopts hf flag
    do
        case "${flag}" in
            h) 
                showHelp
            ;;
            f) 
                fast=true # skip pre-checks
            ;;
        esac
    done
fi

if [ "$fast" != true ]; then
    inf "Checking environment..."
    # ---------------------------------------------------------------------------- #
    #                        Check that current user is root                       #
    # ---------------------------------------------------------------------------- #
    if [ "$USER" != "root" ]; then
        err "This script must be run as root."
    else
        succ "Script is running as root"
    fi

    # ---------------------------------------------------------------------------- #
    #                                 Check Python                                 #
    # ---------------------------------------------------------------------------- #
    if [[ ! -f "$pythonBin" ]]; then
        err "Unable to find Python binary"
    else
        succ "Python located ($($pythonBin -V))"
    fi

    # ---------------------------------------------------------------------------- #
    #                              Check dependencies                              #
    # ---------------------------------------------------------------------------- #
    checkAptPackage "python3-dev"
    checkAptPackage "python3-pip"
    checkAptPackage "python3-setuptools"
    checkAptPackage "build-essential"

    checkPythonPackage "setuptools"
    checkPythonPackage "csvkit"

    # ---------------------------------------------------------------------------- #
    #                                  CSVSQL info                                 #
    # ---------------------------------------------------------------------------- #
    hr
    inf "CSVSQL Info:"
    succ "Binary: $csvsqlBin"
    succ "Options: $additionalFlags"
else
    inf "Skipping environment check because [-f] flag was present."
fi

# ---------------------------------------------------------------------------- #
#                  Prompt for CSV if not supplied in parameter                 #
# ---------------------------------------------------------------------------- #
csvFile="${@: -1}"
if [[ $csvFile == *.csv ]]; then
    inf "CSV file assumed to be parameter $csvFile"
else
    inf "No CSV file seems to have been supplied to the script."
    read -r -p "Type full path to CSV file you want to import: " csvFile
fi

# ---------------------------------------------------------------------------- #
#                              File does not exist                             #
# ---------------------------------------------------------------------------- #
if [[ ! -f "$csvFile" ]]; then
    err "File $csvFile does not exist."
fi


# ---------------------------------------------------------------------------- #
#                             CSV File information                             #
# ---------------------------------------------------------------------------- #
hr
inf "CSV file information:"
filesize=$(wc -c "$csvFile" | awk '{print $1}')
filesize=$((filesize / 1000 / 1000))
tableName=$(basename "$csvFile" .csv)
succ "File: $csvFile"
succ "Chunk size: $chunk_size"

if [[ "$filesize" -gt 1000 ]]; then
    warn "Filesize: $filesize MB (this could take some time)"
else
    succ "Filesize: $filesize MB"
fi

lines=$(sed -n '$=' "$csvFile")

if [[ "$lines" -gt 1000000 ]]; then
    warn "Lines: $lines (this could take some time)"
else
    succ "Lines: $lines"
fi

# ---------------------------------------------------------------------------- #
#                           Database connection info                           #
# ---------------------------------------------------------------------------- #
hr
inf "Database connection info:"
if [[ -f "$connectionConfigFile" ]]; then
    succ "Configuration file $connectionConfigFile found!"
    source "$connectionConfigFile"
    if [ -z "$host" ] || [ -z "$database" || -z "$username" || -z "$password" ]; then
        err "Connection config file ($connectionConfigFile) was sourced but it doesn't contain the neccessary connection info.
        Please delete this file and try again."
    fi
else
    inf "Configuration file not found. Prompting for database connection info"
    echo "Database connection config file not found (expected $connectionConfigFile)"
    echo "Please enter database connection info below"
    read -r -i "localhost" -p "Host [default localhost]: " host
    read -r -p "Database: " db
    read -r -i "root" -p "Username [default root]: " username
    read -r -i "" -s -p "Password [default blank]: " password
    
    touch "$connectionConfigFile"
    echo "host='$host'" > "$connectionConfigFile"
    echo "db='$database'" > "$connectionConfigFile"
    echo "username='$username'" > "$connectionConfigFile"
    echo "password='$password'" > "$connectionConfigFile"
    echo
fi

connectionString="$connector://$username:$password@$host/$db"

checkConnection="MYSQL_PWD='$password' mysql -u '$username' -e '\q'"
checkConnection=$(eval "$checkConnection"; echo $?)

if [[ "$checkConnection" != 0 ]]; then
    err "Unable to connect to MySQL on $host as user $username."
    exit 1
else
    succ "Connection established!"
fi

exists_query=$(printf 'SHOW TABLES LIKE "%s"' "$tableName")
exists_check=$(MYSQL_PWD="$password" mysql -u "$username" -e "$exists_query" "$db")
# empty_query=$(printf 'SELECT COUNT(*) as records FROM %s' "$tableName")
# empty_check=$(MYSQL_PWD="$password" mysql -u "$username" -e "$empty_query" "$db")

succ "Connector: $connector"
succ "Host: $host"
succ "Database: $db"

if [[ "$exists_check" ]]; then
    warn "Table: $tableName (Already exists!)"
else
    succ "Table: $tableName"
fi

succ "Username: $username"
succ "Password: [HIDDEN]"

prompt "Do you want to empty the table before importing?" false
if [ "$reply" == true ]; then
    warn "Table $tableName will be deleted and recreated! (all data will be lost)"
    prompt "Please confirm your choice " true
else
    inf "Table will be appended to"
fi

# ---------------------------------------------------------------------------- #
#                 Get headers and create table if doesn't exist                #
# ---------------------------------------------------------------------------- #
# inf "Fetching headers..."
# headers=$(head -n 1 "$csvFile")

# commandToRun=$(echo "$headers" | tee /dev/tty | $csvsqlBin --db "$connectionString" --tables "$tableName" --insert --verbose)
# # commandToRun="echo '$headers' | $csvsqlBin --db $connectionString --tables $tableName --insert"
# inf "Creating table $tableName with headers:"
# echo "$headers"
# if [ ! "$commandToRun" ]; then
#     err "Failed to create headers: $commandToRun"
# else
#     succ "Headers created!"
# fi
# exit 0

# cat foo.csv | awk 'FNR==1 { printf "$headers\n" } { print $0 }'

# headers
headers=$(head -n 1 "$csvFile")
headersNoQuotes=$(echo $headers | tr -d '"')
echo "$headersNoQuotes"

prompt "Do you want to create table '$tableName' with the above columns?" true


hr
inf "Creating table from CSV..."

dataDef=""
while IFS="$csv_separator" read -ra ADDR; do
  for i in "${ADDR[@]}"; do
    if [ "$i" == "id" ]; then
        dataDef+="$i int,\n"
    else
        dataDef+="$i varchar(255),\n"
    fi
  done
done <<< "$headersNoQuotes"

# TODO: Please fix this...
search='[,\n\s]'
dataDef=${dataDef%$search}
search='[\n\s]'
dataDef=${dataDef%$search}
search='[,\\]'
dataDef=${dataDef%$search}
search='[,\n)]'
dataDef=${dataDef%$search}

if [ "$reply" == true ]; then
    # empty table
    createTable=$(
        echo -e "DROP TABLE $tableName;"; 
        echo -e "
CREATE TABLE IF NOT EXISTS $tableName (
${dataDef}
);")
else
    createTable=$(
    echo -e "
CREATE TABLE IF NOT EXISTS $tableName (
${dataDef}
)")
fi

inf "Running queries: $createTable"

createTable=$(MYSQL_PWD="$password" mysql -u "$username" -e "$createTable" "$db")

inf "Fetching preview with sample values..."

# data
sampleCommand="sed -n 5,15p $csvFile"
sampleValues=$($sampleCommand)
sampleValuesNoQuotes=$($sampleCommand | tr -d '"')

# type check
sampleTypes=$(echo "$sampleValuesNoQuotes" | awk -F"$csv_separator" \
'
{
    printf("[%s],", typeof($1))
}
')

(echo "$sampleTypes"; echo "$sampleValuesNoQuotes") | column -t --separator "$csv_separator" --output-separator " " --table-columns "$headersNoQuotes"
hr


inf "Importing '$csvFile' to $db -> $tableName"

startTime=$(date +%s.%N | awk '{printf "%.2f",$0}')
csvsqlFullCommand="$csvsqlBin --db $connectionString --tables $tableName $additionalFlags"
for ((from=2; from <= lines; from=from+chunk_size))
do
    to=$((from+chunk_size))
    (echo "$headers"; sed -n "${from},${to}p" "$csvFile") | $csvsqlFullCommand
    endTime=$(date +%s.%N | awk '{printf "%.2f",$0}')
    totalTime=$(echo "${endTime} - ${startTime}" | bc -l)
    percentage=$(( (from*100) / lines ))
    succ "[${totalTime}s] [$percentage%] Imported lines $to / $lines!"
done
succ "[${totalTime}s] [100%] Successfully imported $csvFile to $tableName!"
inf "Remember to modify the columns (to ensure unique values and indexing etc...)"
exit 0