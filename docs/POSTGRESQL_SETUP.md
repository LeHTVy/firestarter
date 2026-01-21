# PostgreSQL + pgvector Setup Guide

Hướng dẫn cài đặt PostgreSQL với pgvector extension cho semantic memory storage.

## Prerequisites

- Linux system (Ubuntu/Debian/CentOS)
- Root hoặc sudo access
- Internet connection để download packages

## Installation

### Ubuntu/Debian

#### 1. Install PostgreSQL

```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Check PostgreSQL version
psql --version
```

#### 2. Install pgvector Extension

```bash
# Install build dependencies
sudo apt install -y build-essential git postgresql-server-dev-all

# Clone pgvector repository
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# Build and install
make
sudo make install
```

#### 3. Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database
CREATE DATABASE firestarter_pg;

# Create user
CREATE USER firestarter_ad WITH PASSWORD 'your_secure_password_here';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE firestarter_pg TO firestarter_ad;

# Connect to firestarter_pg database
\c firestarter_pg

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify extension
\dx

# Exit
\q
```

### CentOS/RHEL

#### 1. Install PostgreSQL

```bash
# Install PostgreSQL repository
sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# Install PostgreSQL
sudo yum install -y postgresql14-server postgresql14

# Initialize database
sudo /usr/pgsql-14/bin/postgresql-14-setup initdb

# Start and enable PostgreSQL
sudo systemctl enable postgresql-14
sudo systemctl start postgresql-14
```

#### 2. Install pgvector Extension

```bash
# Install build dependencies
sudo yum install -y gcc make git postgresql14-devel

# Clone pgvector repository
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# Build and install
make PG_CONFIG=/usr/pgsql-14/bin/pg_config
sudo make PG_CONFIG=/usr/pgsql-14/bin/pg_config install
```

#### 3. Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database
CREATE DATABASE firestarter_pg;

# Create user
CREATE USER firestarter_ad WITH PASSWORD 'your_secure_password_here';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE firestarter_pg TO firestarter_ad;

# Connect to firestarter_pg database
\c firestarter_pg

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify extension
\dx

# Exit
\q
```

## Configuration

### 1. PostgreSQL Configuration

Edit PostgreSQL configuration file:

```bash
# Ubuntu/Debian
sudo nano /etc/postgresql/14/main/postgresql.conf

# CentOS/RHEL
sudo nano /var/lib/pgsql/14/data/postgresql.conf
```

Add or modify these settings:

```conf
# Connection settings
listen_addresses = 'localhost'
port = 5432

# Memory settings (adjust based on your system)
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
work_mem = 16MB

# WAL settings for better performance
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Logging
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
```

### 2. Authentication Configuration

Edit `pg_hba.conf`:

```bash
# Ubuntu/Debian
sudo nano /etc/postgresql/14/main/pg_hba.conf

# CentOS/RHEL
sudo nano /var/lib/pgsql/14/data/pg_hba.conf
```

Add line for local connections:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   chroma          chroma                                  md5
host    chroma          chroma          127.0.0.1/32            md5
```

### 3. Restart PostgreSQL

```bash
# Ubuntu/Debian
sudo systemctl restart postgresql

# CentOS/RHEL
sudo systemctl restart postgresql-14
```

## Verification

### 1. Test Connection

```bash
# Test connection with psql
psql -h localhost -U firestarter_ad -d firestarter_pg

# If prompted, enter the password you set
```

### 2. Verify pgvector Extension

```sql
-- Connect to database
\c firestarter_pg

-- Check if extension is installed
\dx

-- You should see 'vector' in the list

-- Test vector operations
CREATE TABLE test_vectors (id serial PRIMARY KEY, embedding vector(3));
INSERT INTO test_vectors (embedding) VALUES ('[1,2,3]');
SELECT * FROM test_vectors;
DROP TABLE test_vectors;
```

## Production Considerations

### 1. Security

- Use strong passwords
- Limit network access (only localhost or specific IPs)
- Regularly update PostgreSQL
- Use SSL/TLS for remote connections if needed

### 2. Backup

Set up regular backups:

```bash
# Create backup script
sudo nano /usr/local/bin/backup_firestarter_db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -U firestarter_ad -d firestarter_pg > $BACKUP_DIR/firestarter_$DATE.sql
# Keep only last 7 days
find $BACKUP_DIR -name "firestarter_*.sql" -mtime +7 -delete
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/backup_firestarter_db.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
# Add: 0 2 * * * /usr/local/bin/backup_chroma_db.sh
```

### 3. Monitoring

Monitor PostgreSQL performance:

```bash
# Install pg_stat_statements extension
sudo -u postgres psql -d chroma -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
```

### 4. Performance Tuning

Adjust PostgreSQL settings based on your system resources:

- `shared_buffers`: 25% of RAM
- `effective_cache_size`: 50-75% of RAM
- `work_mem`: Based on concurrent connections
- `maintenance_work_mem`: 1-2GB for large databases

## Troubleshooting

### Issue: Cannot connect to PostgreSQL

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### Issue: pgvector extension not found

```bash
# Verify extension files are installed
ls -la /usr/share/postgresql/14/extension/vector*

# If missing, reinstall pgvector
cd /tmp/pgvector
sudo make install
```

### Issue: Permission denied

```bash
# Check PostgreSQL user permissions
sudo -u postgres psql -c "\du"

# Grant necessary permissions
sudo -u postgres psql -d firestarter_pg -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO firestarter_ad;"
```

## Environment Variables

Add these to your `.env` file:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chroma
POSTGRES_USER=chroma
POSTGRES_PASSWORD=your_secure_password_here
```

## Next Steps

After PostgreSQL is set up, proceed to [Chroma Server Setup](CHROMA_SERVER_SETUP.md).
