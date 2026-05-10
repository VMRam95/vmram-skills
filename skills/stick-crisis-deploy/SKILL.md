---
name: stick-crisis-deploy
description: Run Stick Crisis deploy workflow to itch.io using distribute_itch.sh, with optional build.
---

# Stick Crisis Deploy

## Pre-check

Ask user if Unity is closed before starting build/deploy.

## Commands

- Deploy using existing builds:
```bash
./distribute_itch.sh
```

- Full build + deploy:
```bash
./distribute_itch.sh --build
```

- Single platform:
```bash
./distribute_itch.sh --mac
./distribute_itch.sh --windows
```

## Project info

- URL: `https://vmram95.itch.io/stick-crisis`
- Channels: `mac-prebeta`, `windows-prebeta`
- Mode: Restricted
