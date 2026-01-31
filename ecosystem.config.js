module.exports = {
  apps: [{
    name: "ai-telegram-bot",
    script: "./run.py",
    interpreter: "./venv/bin/python", // Adjust path for Linux
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      PYTHONUNBUFFERED: "1"
    }
  }]
};
