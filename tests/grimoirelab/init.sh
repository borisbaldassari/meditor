# First step is to create a python virtual env from which to work
VENV_DIR=~/venvs/prosoul
WD=`pwd`
mkdir -p $VENV_DIR
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate
cd ../../django-prosoul/
pip3 install -r requirements.txt
cd $WD

# And now, collect the raw data, generate enriched index, aliases and import the quality model
P2O="p2o.py"
KIDASH='kidash'
ES="http://localhost:9200"

# init.sh <github api token>
if [ -z "$1" ]
  then
    echo "init.sh <GITHUB_API_TOKEN>"
    exit
fi

echo "Loading the metrics data"
$P2O --enrich --db-host localhost --json-projects-map projects.json --index git-raw --index-enrich git git https://github.com/chaoss/grimoirelab-elk.git
$P2O --enrich --db-host localhost --json-projects-map projects.json --index git-raw --index-enrich git git https://github.com/chaoss/perceval.git
$P2O --enrich --db-host localhost --json-projects-map projects.json --index github-raw --index-enrich github_issues github chaoss perceval -t $1
$P2O --enrich --db-host localhost --json-projects-map projects.json --index github-raw --index-enrich github_issues github chaoss grimoirelab-elk -t $1

echo "Generating grimoirelab alias"
curl -XPOST -H "Content-Type: application/json" $ES/_aliases -d '
  {
  "actions" : [
                  {"add" : { "index" : "git",
                         "alias" : "grimoirelab" }},
                  {"add" : { "index" : "github_issues",
                         "alias" : "grimoirelab" }}
              ]
  }
'

echo "Loading the Quality Model"
PYTHONPATH=../../django-prosoul ../../django-prosoul/manage.py makemigrations
PYTHONPATH=../../django-prosoul ../../django-prosoul/manage.py migrate
PYTHONPATH=../../django-prosoul ../../django-prosoul/prosoul/prosoul_import.py -f ../../django-prosoul/prosoul/data/developer_model.json
