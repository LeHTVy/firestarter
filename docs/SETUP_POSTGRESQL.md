# Hướng dẫn Setup PostgreSQL Database và User

## Vấn đề

Nếu database `firestarter_pg` và user `firestarter_ad` chưa tồn tại, bạn cần tạo chúng trước khi chạy Chroma Server.

## Giải pháp tự động (Khuyến nghị)

### Bước 1: Đảm bảo PostgreSQL đã được cài đặt

```bash
# Kiểm tra PostgreSQL
sudo systemctl status postgresql

# Nếu chưa cài đặt, xem docs/POSTGRESQL_SETUP.md
```

### Bước 2: Cấu hình .env file

Đảm bảo `.env` file có các thông tin sau:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=firestarter_pg
POSTGRES_USER=firestarter_ad
POSTGRES_PASSWORD=your_secure_password_here
```

### Bước 3: Chạy setup script

```bash
cd /home/hellrazor/firestarter
./scripts/setup_postgresql.sh
```

Script này sẽ:
- ✅ Kiểm tra PostgreSQL connection
- ✅ Tạo user `firestarter_ad` nếu chưa có
- ✅ Tạo database `firestarter_pg` nếu chưa có
- ✅ Cấp quyền cho user
- ✅ Cài đặt pgvector extension

## Giải pháp thủ công

Nếu muốn setup thủ công:

### Bước 1: Kết nối PostgreSQL

```bash
# Với sudo user (Ubuntu/Debian)
sudo -u postgres psql

# Hoặc với password
psql -h localhost -U postgres
```

### Bước 2: Tạo user

```sql
CREATE USER firestarter_ad WITH PASSWORD '1d252d@firestarter';
```

### Bước 3: Tạo database

```sql
CREATE DATABASE firestarter_pg OWNER firestarter_ad;
```

### Bước 4: Cấp quyền

```sql
GRANT ALL PRIVILEGES ON DATABASE firestarter_pg TO firestarter_ad;
```

### Bước 5: Kết nối database và cài pgvector

```bash
# Kết nối vào database
psql -h localhost -U firestarter_ad -d firestarter_pg

# Hoặc từ postgres user
sudo -u postgres psql -d firestarter_pg
```

```sql
-- Cài đặt pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
\dx
```

### Bước 6: Verify

```bash
# Test connection
psql -h localhost -U firestarter_ad -d firestarter_pg -c "SELECT 1;"
```

## Troubleshooting

### Lỗi: Cannot connect to PostgreSQL

```bash
# Kiểm tra PostgreSQL có chạy không
sudo systemctl status postgresql

# Khởi động PostgreSQL nếu cần
sudo systemctl start postgresql
```

### Lỗi: pgvector extension not found

```bash
# Cài đặt pgvector (xem docs/POSTGRESQL_SETUP.md)
# Sau đó chạy lại:
psql -h localhost -U firestarter_ad -d firestarter_pg -c "CREATE EXTENSION vector;"
```

### Lỗi: Permission denied

```bash
# Đảm bảo user postgres có quyền tạo database và user
# Hoặc dùng sudo:
sudo -u postgres psql
```

## Sau khi setup xong

Sau khi database và user đã được tạo, bạn có thể:

1. **Start Chroma Server:**
   ```bash
   ./scripts/start_chroma_server.sh
   ```

2. **Run Firestarter:**
   ```bash
   ./run.sh
   ```
