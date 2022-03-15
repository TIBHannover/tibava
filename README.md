wget https://tib.eu/cloud/s/t6MfTpHgmNccrA6/download/models.tar.gz
tar -xf models.tar.gz --directory data

sudo docker compose exec backend python3 manage.py migrate
sudo docker compose exec frontend npm install  
sudo docker compose exec frontend npm run build
