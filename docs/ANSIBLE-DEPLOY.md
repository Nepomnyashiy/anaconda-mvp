# Anaconda MVP Deployment via Ansible

## Installation

```bash
# Install Ansible
pip install ansible
```

## Usage

### 1. Using Python deployment script (recommended)

```bash
# Deploy to production
python3 deploy.py --hosts infrastructure/inventory.yml --env production

# Deploy to single host
python3 deploy.py --hosts 192.168.1.100 --user nsadmin --env production

# Dry run (no changes)
python3 deploy.py --hosts infrastructure/inventory.yml --dry-run

# Deploy only specific component
python3 deploy.py --hosts infrastructure/inventory.yml --tags docker

# Skip specific tasks
python3 deploy.py --hosts infrastructure/inventory.yml --skip-tags cleanup
```

### 2. Direct Ansible command

```bash
# Deploy to all hosts in inventory
ansible-playbook infrastructure/deploy-playbook.yml -i infrastructure/inventory.yml -e env=production

# Deploy to single host
ansible-playbook infrastructure/deploy-playbook.yml -i "192.168.1.100," -u nsadmin

# Verbose output
ansible-playbook infrastructure/deploy-playbook.yml -i inventory.yml -vvv

# Check mode (no changes)
ansible-playbook infrastructure/deploy-playbook.yml -i inventory.yml --check

# Deploy with specific tags
ansible-playbook infrastructure/deploy-playbook.yml -i inventory.yml --tags build,deploy
```

## Deployment Workflow

1. **Git Update** — Pull latest code from main branch
2. **Configure** — Setup environment variables
3. **Build** — Build Docker images
4. **Deploy** — Stop old, start new containers
5. **Health Check** — Verify API is responding
6. **Cleanup** — Remove unused resources

## Options

| Option | Description |
|--------|-------------|
| `--hosts` / `-i` | Inventory file or host address |
| `--user` / `-u` | SSH user (default: nsadmin) |
| `--port` / `-p` | SSH port (default: 22) |
| `--env` / `-e` | Environment: development, staging, production |
| `--tags` / `-t` | Only run tasks with these tags |
| `--skip-tags` | Skip tasks with these tags |
| `--dry-run` | Simulate without changes |
| `--check` / `-c` | Check mode (non-destructive) |
| `--verbose` / `-v` | Verbose output |

## Tags

Available tags for selective deployment:

- `git` — Git clone/update
- `config` — Environment configuration
- `build` — Docker build
- `deploy` — Docker compose up/down
- `health` — Health checks
- `cleanup` — Cleanup tasks
- `post` — Post-deployment
- `docker` — All Docker operations
- `always` — Always run (git, config)

## Examples

```bash
# Production deployment with verbosity
python3 deploy.py -i inventory.yml --env production --verbose

# Quick build-only deployment
python3 deploy.py -i inventory.yml --tags build,deploy

# Check what would happen
python3 deploy.py -i inventory.yml --dry-run --verbose

# Rollback to previous version
cd /home/nsadmin/kip-service/anaconda_mvp
git reset --hard HEAD~1
docker-compose up -d --build
```

## Inventory Setup

File: `infrastructure/inventory.yml`

```yaml
all:
  vars:
    ansible_connection: ssh
    ansible_user: nsadmin
    
  hosts:
    production:
      ansible_host: 192.168.1.100
      environment: production
    
    staging:
      ansible_host: 192.168.1.101
      environment: staging
```

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH connection
ansible all -i inventory.yml -m ping

# Test with specific user
ansible all -i inventory.yml -u nsadmin -m ping

# Debug verbosity
ansible all -i inventory.yml -m ping -vvv
```

### Docker Build Failed

```bash
# Check Docker logs
docker-compose logs -f anaconda_api

# Rebuild without cache
docker-compose build --no-cache

# Run specific service
docker-compose up -d anaconda_api
```

### API Health Check Failed

```bash
# Check if container is running
docker ps | grep anaconda

# Check API logs
docker logs anaconda_mvp_anaconda_api_1 --tail 50

# Manual health check
curl http://localhost:8000/health
```

## Monitoring

```bash
# Watch deployment progress
ssh nsadmin@host
cd /home/nsadmin/kip-service/anaconda_mvp
docker-compose logs -f

# Check resource usage
docker stats

# View deployment history
ls -la deployments/
cat deployments/20260203T120000.log
```

## Best Practices

1. **Always test with dry-run first**
   ```bash
   python3 deploy.py -i inventory.yml --dry-run
   ```

2. **Use check mode for production**
   ```bash
   python3 deploy.py -i inventory.yml --check
   ```

3. **Maintain separate inventories**
   ```
   infrastructure/
   ├── inventory-dev.yml
   ├── inventory-staging.yml
   └── inventory-prod.yml
   ```

4. **Monitor after deployment**
   ```bash
   ssh host "docker-compose logs -f --tail 100"
   ```

5. **Keep deployment logs**
   - Logs stored in `deployments/` directory
   - Named by timestamp for easy tracking
   - Review for issues and auditing

## CI/CD Integration

GitHub Actions automatically runs deployment:

```bash
git push origin main
# → GitHub Actions triggers Python deploy script
# → Ansible playbook executed on server
# → Logs available in GitHub Actions UI
```

---

**Happy Deploying! 🚀**
