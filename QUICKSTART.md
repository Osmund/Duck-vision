# Quick Reference: Duck-Vision Service

## 🚀 Start Duck-Vision Service

### First Time Setup:
```bash
cd /home/admog/Code/Duck-Vision
./install_service.sh
sudo systemctl start duck-vision
```

### Daily Commands:
```bash
# View status
sudo systemctl status duck-vision

# View live logs
sudo journalctl -u duck-vision -f

# Restart
sudo systemctl restart duck-vision

# Stop
sudo systemctl stop duck-vision
```

## 📁 Important Paths

- **Source code:** `src/`
- **Documentation:** `docs/`
- **Demos & tests:** `demos/`
- **Data storage:** `data/known_faces/`, `data/logs/`
- **Configuration:** `.env`
- **Service file:** `duck-vision.service`

## 🔧 Development

### Manual start (without service):
```bash
./start_duck_vision.sh
```

### Run demos:
```bash
python3 demos/demo_imx500.py
python3 demos/demo_face_detection.py
```

### View configuration:
```bash
cat .env
python3 src/config.py
```

## 📚 Full Documentation

See `docs/` folder for complete documentation:
- `INTEGRATION_GUIDE.md` - Pi 4 integration
- `ARKITEKTUR_ANBEFALINGER.md` - Architecture decisions
- `INSTALLATION_STATUS.md` - Installation checklist
- `CLEANUP_STATUS.md` - Project reorganization details

---

**Quick start:** `./install_service.sh && sudo systemctl start duck-vision` 🦆⚡
