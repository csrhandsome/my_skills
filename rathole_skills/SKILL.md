---
name: rathole-ssh-relay
description: Set up SSH access from a Mac to a private Ubuntu machine through a public Ubuntu relay with rathole. Use when B cannot accept public inbound traffic and A should connect with a simple SSH alias such as `ssh three`.
---

# Rathole SSH Relay

Use this skill when:
- A is a Mac client.
- B is a private Ubuntu machine such as a home server or gaming host.
- C is a public Ubuntu server used as the relay.
- B can make outbound connections, but cannot accept stable public inbound SSH.
- The goal is to let A run a simple command such as `ssh three` and land on B.

Important:
- The project name is `rathole`, not `rathhole`.
- Do not store live tokens or private keys in this repository.
- Put real secrets only on the target machines, usually under `/etc/rathole/`.

Topology used by this skill:
- A: local Mac
- B: private Ubuntu host
- C: public Ubuntu relay

Traffic flow:

```text
A ssh -> C:<ssh_entry_port> -> rathole server on C -> rathole client on B -> B:22
```

Typical port plan:
- `2333/tcp`: B connects to C's `rathole` server
- `2201/tcp`: A SSH entry point for B

## Assumptions

- C has a public IPv4 address.
- C security group allows `2333/tcp` and `2201/tcp`.
- B has `openssh-server` running on `127.0.0.1:22`.
- A already has an SSH key or can initially log in with a password.

## Quick Workflow

1. Install `rathole` on C and B.
2. On C, generate a token and a Noise keypair.
3. Configure C as the `rathole` server.
4. Configure B as the `rathole` client.
5. Start both services with `systemd`.
6. On A, add an SSH alias such as `Host three`.
7. Verify that `ssh three` reaches B.

## C: Public Ubuntu Relay

Install `rathole`:

```bash
sudo apt update
sudo apt install -y curl unzip
cd /tmp
curl -L https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip -o rathole.zip
unzip -o rathole.zip
sudo install -m 755 rathole /usr/local/bin/rathole
rathole --version
```

Generate a shared token and a Noise keypair:

```bash
openssl rand -hex 16
rathole --genkey
```

Save:
- `TOKEN`
- `SERVER_PRIVATE_KEY`
- `SERVER_PUBLIC_KEY`

Write `/etc/rathole/server.toml`:

```toml
[server]
bind_addr = "0.0.0.0:2333"

[server.transport]
type = "noise"

[server.transport.noise]
local_private_key = "<SERVER_PRIVATE_KEY>"

[server.services.b_ssh]
token = "<TOKEN>"
bind_addr = "0.0.0.0:2201"
```

Secure it:

```bash
sudo chmod 600 /etc/rathole/server.toml
sudo cat /etc/rathole/server.toml
```

Create `/etc/systemd/system/rathole-server.service`:

```ini
[Unit]
Description=Rathole Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/rathole -s /etc/rathole/server.toml
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

Start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rathole-server
sudo systemctl status rathole-server --no-pager
```

If `ufw` is enabled:

```bash
sudo ufw allow 2333/tcp
sudo ufw allow 2201/tcp
sudo ufw reload
```

Also allow the same ports in the cloud security group.

## B: Private Ubuntu Host

Make sure SSH is available:

```bash
sudo apt update
sudo apt install -y openssh-server curl unzip
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

If the login user should be `three`, make sure that account exists:

```bash
id three || sudo adduser three
```

Optional but useful if you want a `three@three` shell prompt:

```bash
sudo hostnamectl set-hostname three
```

Install `rathole`:

```bash
cd /tmp
curl -L https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip -o rathole.zip
unzip -o rathole.zip
sudo install -m 755 rathole /usr/local/bin/rathole
rathole --version
```

Write `/etc/rathole/client.toml`:

```toml
[client]
remote_addr = "<SERVER_PUBLIC_IP>:2333"

[client.transport]
type = "noise"

[client.transport.noise]
remote_public_key = "<SERVER_PUBLIC_KEY>"

[client.services.b_ssh]
token = "<TOKEN>"
local_addr = "127.0.0.1:22"
```

Secure it:

```bash
sudo chmod 600 /etc/rathole/client.toml
sudo cat /etc/rathole/client.toml
```

Create `/etc/systemd/system/rathole-client.service`:

```ini
[Unit]
Description=Rathole Client
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/rathole -c /etc/rathole/client.toml
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

Start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rathole-client
sudo systemctl status rathole-client --no-pager
```

Healthy client output usually includes `Control channel ... established`.

## A: Mac SSH Alias

The alias is local SSH configuration, not DNS. `ssh three` works because `~/.ssh/config` maps `three` to the relay IP, port, and user.

Append to `~/.ssh/config` without overwriting existing entries:

```sshconfig
Host three
  HostName <SERVER_PUBLIC_IP>
  Port 2201
  User three
  IdentityFile ~/.ssh/id_ed25519
  AddKeysToAgent yes
  UseKeychain yes
```

After that, this:

```bash
ssh three
```

Expands to the equivalent of:

```bash
ssh -p 2201 three@<SERVER_PUBLIC_IP>
```

## Verification

From A:

```bash
nc -vz <SERVER_PUBLIC_IP> 2201
ssh -o BatchMode=yes -o ConnectTimeout=5 three hostname
```

Expected result:
- `nc` reports success.
- `ssh ... hostname` prints B's hostname.

From C:

```bash
sudo journalctl -u rathole-server -n 50 --no-pager
```

From B:

```bash
sudo journalctl -u rathole-client -n 50 --no-pager
```

## Common Failure Modes

- `ssh three` times out:
  `2201/tcp` is blocked by the cloud security group or firewall.
- `rathole-client` cannot connect:
  `2333/tcp` is blocked, or the token or Noise public key is wrong.
- `Permission denied` after reaching B:
  the B-side SSH user is wrong, the password is wrong, or the public key is missing from `~/.ssh/authorized_keys`.
- `ssh three` works but does not land on the expected host:
  C and B are not using the same service name or config pair.

## Security Notes

- Prefer SSH public-key login on B.
- After key login works, consider disabling password login in B's SSH config.
- Prefer restricting `2201/tcp` in the cloud security group to A's public IP.
- Keep real tokens and private keys out of git-tracked files.

## Session-Proven Values

This session successfully used:
- alias name: `three`
- B-side login user: `three`
- relay port for client control: `2333`
- relay SSH entry port: `2201`

Keep those values if you want the same user experience. Change them only if there is a port conflict or naming conflict.
