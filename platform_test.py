import os, platform

info = {}

# OS info
info["platform"] = platform.platform()
info["system"] = platform.system()
info["release"] = platform.release()
info["version"] = platform.version()

# Check for docker/container clues
cgroup = ""
try:
    with open("/proc/1/cgroup", "r") as f:
        cgroup = f.read()
except:
    pass

info["cgroup"] = cgroup

# Check for docker env file
info["docker_env_exists"] = os.path.exists("/.dockerenv")

print(info)
