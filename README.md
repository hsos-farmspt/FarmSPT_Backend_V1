#FarmSPT Backend:
## *still under Construction*




#also check CODE_STRUCTURE.md





#useful commands:
# Migrationen ausführen 1/2
docker compose exec backend python manage.py makemigrations
# Migrationen ausführen 2/2
docker compose exec backend python manage.py migrate

docker compose up --build -d

# Logs checken
docker compose logs -f

# in der VM:
sudo docker ompose etc.....

TOKEN=$(curl -s -X POST "https://api.farmspt.ai.edvsz.hs-osnabrueck.de/api/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"hans","password":"password"}' | jq -r '.access_token')

curl -X GET "https://api.farmspt.ai.edvsz.hs-osnabrueck.de/fieldboundaries/" \
  -H "Authorization: Bearer $TOKEN"


# via wsl for mqtt
mosquitto_pub -h mqtt.farmspt.ai.edvsz.hs-osnabrueck.de -p 443 --tls-use-os-certs -u "herstellera" -P "password" -t "/data/herstellera/test" -m "test"

mosquitto_sub -h mqtt.farmspt.ai.edvsz.hs-osnabrueck.de -p 443 --tls-use-os-certs -u "herstellera" -P "password" -t "/data/herstellera/test" 

start mqtt backend client.
docker compose exec backend python /app/mqtt_backend_client.py

