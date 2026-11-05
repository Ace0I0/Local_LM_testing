[Documentation index](../README.md) · [Project README](../../README.md)

# Run llama-server at boot

On the Raspberry Pi, run this installer once from the repository root:

```bash
bash scripts/setup_llama_server.sh
```

It asks for the Pi user, the existing `llama-server` path, and the existing
Qwen GGUF path, then installs and enables `artemis-llama.service`. It asks
for `sudo` once. The service remains bound to `127.0.0.1:8080`, so it is
not exposed to the LAN or Tailscale.

Check it after a reboot with:

```bash
sudo systemctl status artemis-llama.service
sudo journalctl -u artemis-llama.service -n 50 --no-pager
```
