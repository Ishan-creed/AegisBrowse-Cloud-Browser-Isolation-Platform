# AegisBrowse – Cloud Browser Isolation Platform

AegisBrowse is a real-time, cloud-native Secure Browser Isolation (SBI) system that executes untrusted web sessions inside hardened cloud containers and streams a safe visual feed to the user.

It prevents malware, phishing, drive-by downloads, and zero-day browser exploits from ever touching the endpoint.


![Sample][(https://github.com/Ishan-creed/AegisBrowse-Cloud-Browser-Isolation-Platform/blob/main/Screenshot%202025-12-27%20at%2012.13.01.png)]
## 🔐 Architecture

User Browser
   ↓ WebSocket
FastAPI Control Plane
   ↓
AWS SQS → Browser Workers
   ↓
Isolated Chromium + Xvfb
   ↓
Live JPEG Stream
   ↓
User Canvas

Each session runs in its own isolated Chromium instance and is destroyed when closed.

## ✨ Features

- Real-time cloud browser streaming
- Multi-tenant isolation
- Session lifecycle management
- On-demand disposal
- WebSocket video transport
- Postgres audit trail
- AWS-based orchestration

## 🧠 Threats Mitigated

- Drive-by downloads
- Phishing payloads
- Browser exploits
- Malicious JavaScript
- Zero-day attacks
- Watering-hole attacks

## 🚀 Running

1. Start Postgres
2. Start FastAPI session manager
3. Start browser worker
4. Open the web UI


