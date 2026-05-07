#FarmSPT Backend:
## *still Under Construction*




#also check CODE_STRUCTURE.md





#useful commands:
# Migrationen ausführen 1/2
docker-compose exec backend python manage.py makemigrations
# Migrationen ausführen 2/2
docker-compose exec backend python manage.py migrate

docker-compose up --build -d

# Logs checken
docker-compose logs -f

# in der VM:
sudo docker-compose etc.....

