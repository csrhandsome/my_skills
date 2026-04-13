---
name: wireguard-hub-setup
description: Set up a three-node WireGuard hub-and-spoke network with one public Linux server as the hub, one macOS client, and one Linux client. Use when the goal is stable SSH or VS Code Remote-SSH between two private machines through a public server.
---

# WireGuard Hub Setup

Use this skill when:
- You have a public Linux server and want it to relay traffic between two private machines.
- You want `ssh` or VS Code Remote-SSH to use WireGuard IPs instead of a slow third-party relay network.
- One client is macOS and the other is Linux.

Topology used by this skill:
- Server: `10.66.66.1/24`
- A computer: `10.66.66.2/24`
- B computer: `10.66.66.3/24`
- Server public endpoint: `<server_ip>:51820/udp`

Assumptions:
- Server OS is Ubuntu or Debian-like.
- Linux client is Ubuntu or Debian-like.
- The server has a public IPv4 address.
- The server security group or firewall allows `UDP 51820`.
- SSH on the Linux client is available or will be installed.

## Quick Workflow

1. Install WireGuard on all three machines.
2. Generate one keypair per machine.
3. Configure the server as the hub.
4. Configure A and B as peers of the server.
5. Enable `net.ipv4.ip_forward=1` on the server.
6. Start all three tunnels.
7. Verify handshakes on the server.
8. SSH from A to B using the WireGuard IP.

## Server

Install:

```bash
sudo apt update
sudo apt install -y wireguard
```

Generate keys:

```bash
umask 077
wg genkey | tee ~/server.key | wg pubkey > ~/server.pub
cat ~/server.pub
```

Write `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = <server_private_key>

[Peer]
PublicKey = <a_public_key>
AllowedIPs = 10.66.66.2/32

[Peer]
PublicKey = <b_public_key>
AllowedIPs = 10.66.66.3/32
```

Secure the config:

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
```

Enable forwarding. This is required for A and B to reach each other through the server:

```bash
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-wireguard-forward.conf
sudo sysctl --system
sysctl net.ipv4.ip_forward
```

Expected result:

```text
net.ipv4.ip_forward = 1
```

Start the tunnel:

```bash
sudo systemctl enable --now wg-quick@wg0
sudo systemctl status wg-quick@wg0 --no-pager
sudo wg show
sudo ss -lunp | grep 51820
```

If using `ufw`:

```bash
sudo ufw allow 51820/udp
```

If using a cloud server, also allow `UDP 51820` in the cloud security group.

## A Computer: macOS

Two supported options:
- App Store WireGuard client
- Homebrew CLI tools

Install with Homebrew:

```bash
brew install wireguard-go wireguard-tools bash
```

Generate keys:

```bash
umask 077
wg genkey | tee ~/mac.key | wg pubkey > ~/mac.pub
cat ~/mac.pub
```

If using the App Store client, create a tunnel with this content:

```ini
[Interface]
PrivateKey = <a_private_key>
Address = 10.66.66.2/24

[Peer]
PublicKey = <server_public_key>
AllowedIPs = 10.66.66.0/24
Endpoint = <server_ip>:51820
PersistentKeepalive = 25
```

If using Homebrew CLI, save the same content as a local config such as `/tmp/wg-mac.conf`.

Important:
- `wg-quick` from Homebrew requires Bash 4+, while macOS ships an older Bash.
- Run Homebrew `wg-quick` with Homebrew Bash.

Bring the tunnel up on macOS:

```bash
sudo /opt/homebrew/bin/bash /opt/homebrew/bin/wg-quick up /tmp/wg-mac.conf
```

Check status:

```bash
sudo /opt/homebrew/bin/wg show
ping -c 4 10.66.66.1
```

Expected result:
- A can ping `10.66.66.1`.
- `wg show` on A and on the server both show a recent handshake.

## B Computer: Linux

Install:

```bash
sudo apt update
sudo apt install -y wireguard openssh-server
```

Generate keys:

```bash
umask 077
wg genkey | tee ~/laptop.key | wg pubkey > ~/laptop.pub
cat ~/laptop.pub
```

Write `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.66.66.3/24
PrivateKey = <b_private_key>

[Peer]
PublicKey = <server_public_key>
AllowedIPs = 10.66.66.0/24
Endpoint = <server_ip>:51820
PersistentKeepalive = 25
```

Start the tunnel:

```bash
sudo chmod 600 /etc/wireguard/wg0.conf
sudo systemctl enable --now wg-quick@wg0
sudo systemctl status wg-quick@wg0 --no-pager
sudo wg show
```

Make sure SSH is available:

```bash
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

## Verification

From the server:

```bash
sudo wg show
ping -c 4 10.66.66.2
ping -c 4 10.66.66.3
```

From A:

```bash
ping -c 4 10.66.66.1
ping -c 4 10.66.66.3
ssh <b_username>@10.66.66.3
```

From B:

```bash
ping -c 4 10.66.66.1
ping -c 4 10.66.66.2
```

For VS Code Remote-SSH from A to B, target:

```text
10.66.66.3
```

## Common Failure Modes

### A can reach the server, but A cannot reach B

Most likely causes:
- Server forwarding is off.
- Server `wg0` is up, but `net.ipv4.ip_forward = 0`.

Check on the server:

```bash
sysctl net.ipv4.ip_forward
```

Fix:

```bash
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-wireguard-forward.conf
sudo sysctl --system
```

### Server can talk to both A and B, but A and B cannot talk to each other

Check that the server forwarding policy is not blocking traffic:

```bash
sudo iptables -L FORWARD -n -v
```

If needed:

```bash
sudo iptables -I FORWARD 1 -i wg0 -o wg0 -j ACCEPT
```

### Server sees one peer handshake but not the other

Check:
- Correct peer public key on the server
- Correct server public key on the client
- Correct endpoint `<server_ip>:51820`
- `PersistentKeepalive = 25` on clients
- Cloud security group allows `UDP 51820`

### macOS tunnel starts but there is no handshake

Check:
- The macOS config uses the current server public key.
- You launched `wg-quick` with Homebrew Bash, not the system Bash.

### SSH still fails after WireGuard pings work

WireGuard is fine. Check SSH on B:

```bash
sudo systemctl status ssh --no-pager
ss -tlnp | grep ':22'
```

## Notes

- `PrivateKey` uses the `.key` file for that machine.
- `PublicKey` uses the `.pub` file for the peer machine.
- Do not paste private keys into chat or commit them to git.
- For a simple SSH setup, route only the WireGuard subnet with `AllowedIPs = 10.66.66.0/24`.
- This skill uses a hub-and-spoke topology. Traffic between A and B is relayed by the server unless you later redesign it for direct peer-to-peer routing.
