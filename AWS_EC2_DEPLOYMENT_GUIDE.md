# 🌩️ AWS EC2 배포 완전 가이드

## 📋 개요

Docker Hub에 업로드된 JOBS 프로젝트를 AWS EC2에 배포하는 완전한 가이드입니다.

## 🛠️ 필요한 것들

- ✅ AWS 계정
- ✅ Docker Hub에 업로드된 이미지 (`chanerdy/jobs-api`, `chanerdy/jobs-mcp`)
- ✅ OpenRouter API 키
- ✅ SSH 클라이언트 (PuTTY, 터미널 등)

## 📌 전체 과정

```
1. AWS EC2 인스턴스 생성
2. 보안 그룹 설정 (포트 오픈)
3. EC2 접속 및 환경 설정
4. Docker & Docker Compose 설치
5. 프로젝트 파일 업로드
6. 환경변수 설정
7. 서비스 실행
8. 도메인 연결 (선택사항)
```

## 🚀 1단계: EC2 인스턴스 생성

### **1.1 AWS 콘솔 접속**
- AWS 콘솔 로그인: https://console.aws.amazon.com
- EC2 서비스 선택

### **1.2 인스턴스 시작**
1. **"Launch Instance" 클릭**
2. **이름**: `jobs-production-server`
3. **AMI 선택**: `Ubuntu Server 22.04 LTS (Free tier eligible)`
4. **인스턴스 타입**: `t2.medium` (권장) 또는 `t3.medium`
   - t2.micro는 메모리 부족으로 권장하지 않음
5. **키 페어**: 
   - 기존 키 사용 또는 새로 생성
   - `.pem` 파일 다운로드 후 안전하게 보관

### **1.3 네트워크 설정**
1. **"Edit" 클릭** (Network settings)
2. **보안 그룹 생성**:
   - 이름: `jobs-security-group`
   - 설명: `JOBS project security group`

### **1.4 인바운드 규칙 추가**
| 타입 | 포트 | 소스 | 설명 |
|------|------|------|------|
| SSH | 22 | My IP | SSH 접속 |
| Custom TCP | 8000 | 0.0.0.0/0 | FastAPI 서버 |
| Custom TCP | 8001 | 0.0.0.0/0 | MCP 서버 |
| Custom TCP | 8080 | 0.0.0.0/0 | pgAdmin (선택) |
| Custom TCP | 8081 | 0.0.0.0/0 | MongoDB Express (선택) |
| HTTP | 80 | 0.0.0.0/0 | HTTP (향후 Nginx용) |
| HTTPS | 443 | 0.0.0.0/0 | HTTPS (향후 SSL용) |

### **1.5 스토리지 설정**
- **크기**: 20GB (최소) ~ 30GB (권장)
- **타입**: gp3 (권장)

### **1.6 인스턴스 시작**
- **"Launch Instance" 클릭**
- 인스턴스 ID 기록해두기

## 🔌 2단계: EC2 접속

### **2.1 SSH 접속 (Windows)**
```cmd
# PuTTY 사용 또는 Windows Terminal
ssh -i "your-key.pem" ubuntu@[EC2-PUBLIC-IP]
```

### **2.2 SSH 접속 (Mac/Linux)**
```bash
chmod 400 your-key.pem
ssh -i "your-key.pem" ubuntu@[EC2-PUBLIC-IP]
```

### **2.3 접속 확인**
```bash
# 성공하면 이런 프롬프트가 나타남
ubuntu@ip-172-31-xx-xx:~$
```

## 🐳 3단계: Docker 환경 설정

### **3.1 자동 설치 스크립트 다운로드**
```bash
# 설치 스크립트 다운로드 (GitHub에서)
wget https://raw.githubusercontent.com/your-username/your-repo/main/ec2-setup.sh
chmod +x ec2-setup.sh
./ec2-setup.sh
```

### **3.2 수동 설치 (스크립트 사용 안 할 경우)**
```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Docker 권한 적용
newgrp docker

# 설치 확인
docker --version
docker-compose --version
```

## 📁 4단계: 프로젝트 파일 업로드

### **4.1 프로젝트 디렉토리 생성**
```bash
mkdir -p ~/jobs-project
cd ~/jobs-project
```

### **4.2 파일 업로드 방법**

#### **방법 A: SCP로 업로드 (로컬에서)**
```bash
# Windows (PowerShell)
scp -i "your-key.pem" ec2-docker-compose.yml ubuntu@[EC2-IP]:~/jobs-project/
scp -i "your-key.pem" env.production.example ubuntu@[EC2-IP]:~/jobs-project/

# Mac/Linux
scp -i "your-key.pem" ec2-docker-compose.yml ubuntu@[EC2-IP]:~/jobs-project/
scp -i "your-key.pem" env.production.example ubuntu@[EC2-IP]:~/jobs-project/
```

#### **방법 B: 직접 생성 (EC2에서)**
```bash
# ec2-docker-compose.yml 생성
nano ec2-docker-compose.yml
# 위에서 작성한 내용 복사&붙여넣기

# env.production.example 생성
nano env.production.example
# 위에서 작성한 내용 복사&붙여넣기
```

#### **방법 C: GitHub 사용**
```bash
# GitHub에 파일들을 업로드 후
git clone https://github.com/your-username/your-repo.git
cp your-repo/ec2-docker-compose.yml .
cp your-repo/env.production.example .
```

## 🔐 5단계: 환경변수 설정

### **5.1 환경변수 파일 생성**
```bash
cp env.production.example .env
nano .env
```

### **5.2 필수 값들 수정**
```env
# 실제 API 키로 변경
OPENROUTER_API_KEY=sk-or-v1-your-actual-api-key

# 강력한 시크릿 키로 변경 (32자 이상)
SECRET_KEY=your-super-strong-secret-key-for-production-32chars

# 데이터베이스 비밀번호들 변경 (선택사항)
POSTGRES_PASSWORD=strong-postgres-password
MONGO_PASSWORD=strong-mongo-password
```

## 🚀 6단계: 서비스 실행

### **6.1 Docker 이미지 다운로드**
```bash
# 이미지 미리 다운로드 (선택사항)
docker pull chanerdy/jobs-api:latest
docker pull chanerdy/jobs-mcp:latest
docker pull postgres:15-alpine
docker pull mongo:7.0
docker pull redis:7-alpine
```

### **6.2 서비스 시작**
```bash
# 백그라운드로 시작
docker-compose -f ec2-docker-compose.yml up -d

# 또는 포그라운드로 시작 (로그 보면서)
docker-compose -f ec2-docker-compose.yml up
```

### **6.3 서비스 상태 확인**
```bash
# 컨테이너 상태 확인
docker-compose -f ec2-docker-compose.yml ps

# 로그 확인
docker-compose -f ec2-docker-compose.yml logs -f

# 특정 서비스 로그
docker-compose -f ec2-docker-compose.yml logs fastapi
docker-compose -f ec2-docker-compose.yml logs mcp-server
```

## 🌐 7단계: 접속 테스트

### **7.1 서비스 접속 확인**
```bash
# EC2 퍼블릭 IP 확인
curl http://169.254.169.254/latest/meta-data/public-ipv4

# 로컬에서 접속 테스트
curl http://[EC2-PUBLIC-IP]:8000/docs
curl http://[EC2-PUBLIC-IP]:8001/health
```

### **7.2 브라우저에서 확인**
- 📖 **FastAPI 문서**: http://[EC2-PUBLIC-IP]:8000/docs
- 🔧 **MCP 서버**: http://[EC2-PUBLIC-IP]:8001
- 🗄️ **pgAdmin**: http://[EC2-PUBLIC-IP]:8080 (설정한 경우)
- 📊 **MongoDB Express**: http://[EC2-PUBLIC-IP]:8081 (설정한 경우)

## 🛠️ 8단계: 운영 관리

### **8.1 서비스 관리 명령어**
```bash
# 서비스 중지
docker-compose -f ec2-docker-compose.yml down

# 서비스 재시작
docker-compose -f ec2-docker-compose.yml restart

# 이미지 업데이트
docker-compose -f ec2-docker-compose.yml pull
docker-compose -f ec2-docker-compose.yml up -d

# 로그 확인
docker-compose -f ec2-docker-compose.yml logs -f --tail=100
```

### **8.2 시스템 리소스 모니터링**
```bash
# 디스크 사용량
df -h

# 메모리 사용량
free -h

# CPU 사용량
top

# Docker 리소스 사용량
docker stats
```

### **8.3 백업 설정**
```bash
# 데이터베이스 백업 스크립트 생성
nano backup.sh

# 내용:
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec jobs_postgres_prod pg_dump -U myuser jobs > postgres_backup_$DATE.sql
docker exec jobs_mongo_prod mongodump --out mongo_backup_$DATE
tar -czf backup_$DATE.tar.gz postgres_backup_$DATE.sql mongo_backup_$DATE

# 실행 권한 부여
chmod +x backup.sh

# 크론탭으로 자동 백업 (매일 새벽 2시)
crontab -e
# 추가: 0 2 * * * /home/ubuntu/jobs-project/backup.sh
```

## 🌐 9단계: 도메인 연결 (선택사항)

### **9.1 도메인 구매 및 DNS 설정**
1. **도메인 구매** (Route 53, Cloudflare, 가비아 등)
2. **A 레코드 추가**:
   - `your-domain.com` → EC2 퍼블릭 IP
   - `api.your-domain.com` → EC2 퍼블릭 IP

### **9.2 Nginx 리버스 프록시 설정**
```bash
# Nginx 설치
sudo apt install nginx -y

# 설정 파일 생성
sudo nano /etc/nginx/sites-available/jobs

# 내용:
server {
    listen 80;
    server_name your-domain.com api.your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /mcp/ {
        proxy_pass http://localhost:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 설정 활성화
sudo ln -s /etc/nginx/sites-available/jobs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### **9.3 SSL 인증서 설정 (Let's Encrypt)**
```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx -y

# SSL 인증서 발급
sudo certbot --nginx -d your-domain.com -d api.your-domain.com

# 자동 갱신 확인
sudo crontab -l
```

## 🚨 문제 해결

### **일반적인 문제들**

1. **포트 접속 불가**
   - 보안 그룹 설정 확인
   - 방화벽 설정 확인: `sudo ufw status`

2. **메모리 부족**
   - 인스턴스 타입 업그레이드 (t2.medium → t3.large)
   - 스왑 메모리 추가

3. **디스크 공간 부족**
   - EBS 볼륨 확장
   - 불필요한 Docker 이미지 정리: `docker system prune`

4. **컨테이너 시작 실패**
   - 로그 확인: `docker-compose logs [service-name]`
   - 환경변수 확인

### **로그 위치**
- **Docker Compose**: `docker-compose logs`
- **Nginx**: `/var/log/nginx/`
- **시스템**: `/var/log/syslog`

## 📞 지원

문제 발생 시 확인할 것들:
1. EC2 인스턴스 상태
2. 보안 그룹 설정
3. Docker 서비스 상태
4. 환경변수 설정
5. 로그 파일

## 🎉 완료!

축하합니다! JOBS 프로젝트가 AWS EC2에서 운영되고 있습니다.

**접속 정보:**
- 🌐 **메인 서비스**: http://[EC2-IP]:8000
- 🔧 **MCP 서버**: http://[EC2-IP]:8001
- 📊 **관리 도구**: http://[EC2-IP]:8080, :8081

**다음 단계:**
- 모니터링 설정 (CloudWatch)
- 백업 자동화
- CI/CD 파이프라인 구축
- Load Balancer 설정 (확장 시) 