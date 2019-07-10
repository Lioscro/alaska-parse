echo deb http://deb.debian.org/debian stretch-backports main > /etc/apt/sources.list.d/backports.list
apt-get update
apt-get install -y -t stretch-backports certbot python-certbot-nginx
certbot --nginx --non-interactive --agree-tos --email ${EMAIL} --domains ${PUBLICHOST}
service nginx start
