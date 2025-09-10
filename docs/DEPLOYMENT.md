# Deployment Guide

This guide covers various deployment options for the Telegive Bot Service.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Railway Deployment](#railway-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Manual Deployment](#manual-deployment)
6. [Production Considerations](#production-considerations)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)

## Prerequisites

### System Requirements

- **CPU**: 1+ cores
- **RAM**: 512MB minimum, 1GB recommended
- **Storage**: 5GB minimum
- **Network**: Stable internet connection with HTTPS support

### Dependencies

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- SSL certificate (for webhook endpoints)

### External Services

Ensure the following services are accessible:

- Telegive Auth Service
- Telegive Channel Service
- Telegive Giveaway Service
- Telegive Participant Service
- Telegive Media Service

## Environment Configuration

### Required Environment Variables

Create a `.env` file with the following variables:

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Redis Configuration
REDIS_URL=redis://host:port/db

# Service URLs
TELEGIVE_AUTH_URL=https://auth.telegive.com
TELEGIVE_CHANNEL_URL=https://channel.telegive.com
TELEGIVE_GIVEAWAY_URL=https://giveaway.telegive.com
TELEGIVE_PARTICIPANT_URL=https://participant.telegive.com
TELEGIVE_MEDIA_URL=https://media.telegive.com

# Webhook Configuration
WEBHOOK_BASE_URL=https://your-bot-domain.com
SERVICE_PORT=5000

# Bot Configuration
MAX_MESSAGE_LENGTH=4096
BULK_MESSAGE_BATCH_SIZE=50
MESSAGE_RETRY_ATTEMPTS=3
```

### Optional Environment Variables

```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Performance
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=120

# Security
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ORIGINS=https://your-frontend.com
```

## Railway Deployment

Railway provides an easy deployment platform with automatic scaling.

### Step 1: Prepare Railway Configuration

The `railway.json` file is already configured:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn --bind 0.0.0.0:$PORT --workers 4 app:app",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Step 2: Deploy to Railway

1. **Install Railway CLI:**
```bash
npm install -g @railway/cli
```

2. **Login to Railway:**
```bash
railway login
```

3. **Initialize Project:**
```bash
railway init
```

4. **Add PostgreSQL Database:**
```bash
railway add postgresql
```

5. **Add Redis:**
```bash
railway add redis
```

6. **Set Environment Variables:**
```bash
railway variables set FLASK_ENV=production
railway variables set WEBHOOK_BASE_URL=https://your-app.railway.app
# Set other required variables
```

7. **Deploy:**
```bash
railway up
```

### Step 3: Configure Domain (Optional)

1. Add custom domain in Railway dashboard
2. Update `WEBHOOK_BASE_URL` environment variable
3. Configure DNS records

## Docker Deployment

### Step 1: Build Docker Image

```bash
# Build the image
docker build -t telegive-bot .

# Or use Docker Compose
docker-compose build
```

### Step 2: Run with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f bot-service
```

### Step 3: Initialize Database

```bash
# Run database initialization
docker-compose exec bot-service python database_init.py
```

### Step 4: Configure Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Manual Deployment

### Step 1: Server Setup

1. **Update system:**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Install dependencies:**
```bash
sudo apt install python3.11 python3.11-venv python3-pip postgresql redis-server nginx
```

3. **Create application user:**
```bash
sudo useradd -m -s /bin/bash telegive
sudo su - telegive
```

### Step 2: Application Setup

1. **Clone repository:**
```bash
git clone <repository-url>
cd telegive-bot
```

2. **Create virtual environment:**
```bash
python3.11 -m venv venv
source venv/bin/activate
```

3. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Step 3: Database Setup

1. **Create PostgreSQL database:**
```bash
sudo -u postgres createdb telegive_bot
sudo -u postgres createuser telegive
sudo -u postgres psql -c "ALTER USER telegive WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE telegive_bot TO telegive;"
```

2. **Initialize database:**
```bash
python database_init.py
```

### Step 4: Service Configuration

1. **Create systemd service:**
```bash
sudo nano /etc/systemd/system/telegive-bot.service
```

```ini
[Unit]
Description=Telegive Bot Service
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=telegive
Group=telegive
WorkingDirectory=/home/telegive/telegive-bot
Environment=PATH=/home/telegive/telegive-bot/venv/bin
ExecStart=/home/telegive/telegive-bot/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. **Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegive-bot
sudo systemctl start telegive-bot
```

### Step 5: Configure Nginx

1. **Create nginx configuration:**
```bash
sudo nano /etc/nginx/sites-available/telegive-bot
```

2. **Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/telegive-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Production Considerations

### Security

1. **SSL/TLS Configuration:**
   - Use Let's Encrypt for free SSL certificates
   - Configure strong cipher suites
   - Enable HSTS headers

2. **Firewall Configuration:**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

3. **Database Security:**
   - Use strong passwords
   - Restrict database access
   - Enable SSL for database connections

### Performance Optimization

1. **Gunicorn Configuration:**
```bash
# Calculate workers: (2 x CPU cores) + 1
gunicorn --workers 4 --worker-class gevent --worker-connections 1000 app:app
```

2. **Database Optimization:**
   - Configure connection pooling
   - Set appropriate shared_buffers
   - Enable query optimization

3. **Redis Configuration:**
   - Set appropriate memory limits
   - Configure persistence settings
   - Enable compression

### Backup Strategy

1. **Database Backups:**
```bash
# Daily backup script
#!/bin/bash
pg_dump telegive_bot | gzip > /backups/telegive_bot_$(date +%Y%m%d).sql.gz
```

2. **Application Backups:**
```bash
# Backup application files
tar -czf /backups/app_$(date +%Y%m%d).tar.gz /home/telegive/telegive-bot
```

3. **Automated Backup:**
```bash
# Add to crontab
0 2 * * * /path/to/backup-script.sh
```

## Monitoring and Maintenance

### Health Monitoring

1. **Setup monitoring script:**
```bash
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ $response != "200" ]; then
    echo "Service is down" | mail -s "Bot Service Alert" admin@example.com
fi
```

2. **Add to crontab:**
```bash
*/5 * * * * /path/to/health-check.sh
```

### Log Management

1. **Configure log rotation:**
```bash
sudo nano /etc/logrotate.d/telegive-bot
```

```
/home/telegive/telegive-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 telegive telegive
    postrotate
        systemctl reload telegive-bot
    endscript
}
```

### Updates and Maintenance

1. **Update application:**
```bash
cd /home/telegive/telegive-bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegive-bot
```

2. **Database migrations:**
```bash
# Run any necessary database migrations
python database_migrate.py
```

### Troubleshooting

1. **Check service status:**
```bash
sudo systemctl status telegive-bot
```

2. **View logs:**
```bash
sudo journalctl -u telegive-bot -f
tail -f /home/telegive/telegive-bot/logs/app.log
```

3. **Test connectivity:**
```bash
curl http://localhost:5000/health
```

4. **Database connectivity:**
```bash
psql -h localhost -U telegive -d telegive_bot -c "SELECT 1;"
```

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer Configuration:**
   - Use nginx or HAProxy
   - Configure session affinity if needed
   - Health check endpoints

2. **Database Scaling:**
   - Read replicas for read-heavy workloads
   - Connection pooling (PgBouncer)
   - Database sharding if necessary

3. **Redis Scaling:**
   - Redis Cluster for high availability
   - Separate Redis instances for different data types

### Vertical Scaling

1. **Resource Monitoring:**
   - CPU usage
   - Memory consumption
   - Disk I/O
   - Network bandwidth

2. **Performance Tuning:**
   - Optimize database queries
   - Implement caching strategies
   - Use async processing for heavy operations

## Disaster Recovery

### Backup Verification

1. **Test backup restoration:**
```bash
# Test database restore
pg_restore -d test_db backup.sql
```

2. **Verify application functionality:**
```bash
# Run health checks on restored environment
curl http://test-environment/health
```

### Recovery Procedures

1. **Database Recovery:**
   - Restore from latest backup
   - Apply transaction logs if available
   - Verify data integrity

2. **Application Recovery:**
   - Deploy from version control
   - Restore configuration files
   - Restart services

3. **Service Recovery:**
   - Update DNS records if necessary
   - Reconfigure webhooks
   - Notify stakeholders

