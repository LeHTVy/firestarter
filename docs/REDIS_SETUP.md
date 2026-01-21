# Redis Setup Guide

Hướng dẫn cài đặt và cấu hình Redis cho short-term memory buffer.

## Prerequisites

- Linux system (Ubuntu/Debian/CentOS)
- Root hoặc sudo access
- Internet connection để download packages

## Installation

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Redis
sudo apt install -y redis-server

# Start Redis service
sudo systemctl start redis-server

# Enable Redis to start on boot
sudo systemctl enable redis-server

# Check Redis status
sudo systemctl status redis-server
```

### CentOS/RHEL

```bash
# Install EPEL repository (if not already installed)
sudo yum install -y epel-release

# Install Redis
sudo yum install -y redis

# Start Redis service
sudo systemctl start redis

# Enable Redis to start on boot
sudo systemctl enable redis

# Check Redis status
sudo systemctl status redis
```

## Configuration

### Basic Configuration

Redis mặc định chạy trên:
- **Host**: localhost
- **Port**: 6379
- **Password**: Không có (có thể cấu hình nếu cần)

### Optional: Set Password (Recommended for Production)

1. Edit Redis configuration file:

```bash
sudo nano /etc/redis/redis.conf
```

2. Tìm và uncomment dòng `# requirepass` và thêm password:

```
requirepass your_secure_password_here
```

3. Restart Redis:

```bash
sudo systemctl restart redis-server
```

4. Test connection với password:

```bash
redis-cli -a your_secure_password_here ping
```

### Optional: Configure Memory Limits

Để tránh Redis sử dụng quá nhiều memory, có thể set maxmemory:

1. Edit `/etc/redis/redis.conf`:

```
maxmemory 256mb
maxmemory-policy allkeys-lru
```

2. Restart Redis:

```bash
sudo systemctl restart redis-server
```

## Verification

### Test Redis Connection

```bash
# Connect to Redis
redis-cli

# Test ping
127.0.0.1:6379> PING
# Should return: PONG

# Test set/get
127.0.0.1:6379> SET test "Hello Redis"
127.0.0.1:6379> GET test
# Should return: "Hello Redis"

# Exit
127.0.0.1:6379> exit
```

### Test from Python

```python
import redis

# Connect to Redis
r = redis.Redis(
    host='localhost',
    port=6379,
    password=None,  # Set if you configured password
    db=0,
    decode_responses=True
)

# Test connection
r.ping()  # Should return True

# Test set/get
r.set('test', 'Hello Redis')
print(r.get('test'))  # Should print: Hello Redis
```

## Environment Variables

Thêm vào file `.env`:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Leave empty if no password, or set your password
REDIS_DB=0
```

## Troubleshooting

### Redis không start

```bash
# Check Redis logs
sudo journalctl -u redis-server -n 50

# Check if port 6379 is in use
sudo netstat -tulpn | grep 6379

# Restart Redis
sudo systemctl restart redis-server
```

### Connection refused

- Đảm bảo Redis service đang chạy: `sudo systemctl status redis-server`
- Kiểm tra firewall: `sudo ufw allow 6379/tcp` (nếu cần remote access)
- Kiểm tra bind address trong `/etc/redis/redis.conf` (nên là `127.0.0.1` hoặc `0.0.0.0`)

### Memory issues

- Set `maxmemory` trong config
- Monitor memory usage: `redis-cli INFO memory`
- Clear old data: `redis-cli FLUSHDB` (cẩn thận, sẽ xóa tất cả data)

## Production Recommendations

1. **Set password**: Bắt buộc cho production
2. **Configure persistence**: Redis mặc định có RDB persistence, có thể enable AOF nếu cần
3. **Set memory limits**: Tránh Redis sử dụng hết RAM
4. **Monitor**: Sử dụng `redis-cli INFO` để monitor
5. **Backup**: Regular backup Redis data nếu cần persistence

## Additional Resources

- [Redis Official Documentation](https://redis.io/docs/)
- [Redis Configuration Guide](https://redis.io/docs/management/config/)
- [Redis Persistence](https://redis.io/docs/management/persistence/)
